"""File-based task store: each task is a JSON file on disk."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from clawteam.paths import ensure_within_root, validate_identifier
from clawteam.store.base import BaseTaskStore, TaskLockError
from clawteam.team.models import TaskItem, TaskPriority, TaskStatus, get_data_dir


def _tasks_root(team_name: str) -> Path:
    d = ensure_within_root(
        get_data_dir() / "tasks",
        validate_identifier(team_name, "team name"),
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def _team_dir(team_name: str) -> Path:
    from clawteam.paths import ensure_within_root as _eur, validate_identifier as _vi
    from clawteam.team.manager import _teams_root as _tr
    return _eur(_tr(), _vi(team_name, "team name"))


def _resolution_manifest_path(team_name: str, task_id: str) -> Path:
    return _team_dir(team_name) / f"resolution-{task_id}.json"


def _task_path(team_name: str, task_id: str) -> Path:
    return _tasks_root(team_name) / f"task-{task_id}.json"


def _tasks_lock_path(team_name: str) -> Path:
    return _tasks_root(team_name) / ".tasks.lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileTaskStore(BaseTaskStore):

    def __init__(self, team_name: str):
        super().__init__(team_name)
        self._replay_pending_resolutions()
    """Task store backed by the local filesystem.

    Each task is stored as a separate JSON file:
    ``{data_dir}/tasks/{team}/task-{id}.json``

    Concurrent access is serialised with an OS-specific advisory lock.
    """

    @contextmanager
    def _write_lock(self):
        lock_path = _tasks_lock_path(self.team_name)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            if sys.platform == "win32":
                pos = lock_file.tell()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                lock_file.seek(pos)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if sys.platform == "win32":
                    pos = lock_file.tell()
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    lock_file.seek(pos)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def create(
        self,
        subject: str,
        description: str = "",
        owner: str = "",
        priority: TaskPriority | None = None,
        blocks: list[str] | None = None,
        blocked_by: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> TaskItem:
        task = TaskItem(
            subject=subject,
            description=description,
            owner=owner,
            priority=priority or TaskPriority.medium,
            blocks=blocks or [],
            blocked_by=blocked_by or [],
            metadata=metadata or {},
            idempotency_key=idempotency_key,
        )
        self._validate_blocked_by_unlocked(task.id, task.blocked_by)
        if task.blocked_by:
            task.status = TaskStatus.blocked
        with self._write_lock():
            # Idempotency check inside lock to prevent TOCTOU race
            if idempotency_key:
                existing = self._find_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing
            self._save_unlocked(task)
        return task

    def _find_by_idempotency_key(self, key: str) -> TaskItem | None:
        """Return existing task with matching idempotency key, if any."""
        root = _tasks_root(self.team_name)
        for f in root.glob("task-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                task = TaskItem.model_validate(data)
                if task.idempotency_key == key:
                    return task
            except (json.JSONDecodeError, OSError, ValueError):
                continue
        return None

    def get(self, task_id: str) -> TaskItem | None:
        return self._get_unlocked(task_id)

    def _get_unlocked(self, task_id: str) -> TaskItem | None:
        path = _task_path(self.team_name, task_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TaskItem.model_validate(data)
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def update(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        owner: str | None = None,
        subject: str | None = None,
        description: str | None = None,
        priority: TaskPriority | None = None,
        add_blocks: list[str] | None = None,
        add_blocked_by: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        caller: str = "",
        force: bool = False,
    ) -> TaskItem | None:
        with self._write_lock():
            task = self._get_unlocked(task_id)
            if not task:
                return None

            if status == TaskStatus.in_progress:
                self._acquire_lock(task, caller, force)
                if not task.started_at:
                    task.started_at = _now_iso()

            if status in (TaskStatus.completed, TaskStatus.pending):
                task.locked_by = ""
                task.locked_at = ""

            # duration tracking
            if status == TaskStatus.completed and task.started_at:
                try:
                    start = datetime.fromisoformat(task.started_at)
                    duration_secs = (datetime.now(timezone.utc) - start).total_seconds()
                    task.metadata["duration_seconds"] = round(duration_secs, 2)
                except (ValueError, TypeError):
                    pass

            if status is not None:
                task.status = status
                # BUG-1 fix: force-setting a blocked task to in_progress implies
                # the operator wants to skip the dependency, so clear blocked_by
                if status == TaskStatus.in_progress and task.blocked_by:
                    task.blocked_by = []
            if owner is not None:
                task.owner = owner
            if subject is not None:
                task.subject = subject
            if description is not None:
                task.description = description
            if priority is not None:
                task.priority = priority
            if add_blocks:
                for b in add_blocks:
                    if b not in task.blocks:
                        task.blocks.append(b)
            if add_blocked_by:
                proposed_blocked_by = list(task.blocked_by)
                for b in add_blocked_by:
                    if b not in proposed_blocked_by:
                        proposed_blocked_by.append(b)
                self._validate_blocked_by_unlocked(task.id, proposed_blocked_by)
                task.blocked_by = proposed_blocked_by
                if task.blocked_by and task.status == TaskStatus.pending:
                    task.status = TaskStatus.blocked
            if metadata:
                task.metadata.update(metadata)
            task.updated_at = _now_iso()

            if task.status == TaskStatus.completed:
                self._resolve_dependents_unlocked(task_id)

            self._save_unlocked(task)
            return task

    def _acquire_lock(self, task: TaskItem, caller: str, force: bool) -> None:
        if task.locked_by and task.locked_by != caller and not force:
            from clawteam.spawn.registry import is_agent_alive
            alive = is_agent_alive(self.team_name, task.locked_by)
            if alive is not False:
                raise TaskLockError(
                    f"Task '{task.id}' is locked by '{task.locked_by}' "
                    f"(since {task.locked_at}). Use --force to override."
                )
        task.locked_by = caller or ""
        task.locked_at = _now_iso() if caller else ""

    def release_stale_locks(self) -> list[str]:
        from clawteam.spawn.registry import is_agent_alive

        released = []
        with self._write_lock():
            for task in self._list_tasks_unlocked():
                if not task.locked_by:
                    continue
                alive = is_agent_alive(self.team_name, task.locked_by)
                if alive is False:
                    task.locked_by = ""
                    task.locked_at = ""
                    task.updated_at = _now_iso()
                    self._save_unlocked(task)
                    released.append(task.id)
        return released

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        owner: str | None = None,
        priority: TaskPriority | None = None,
        sort_by_priority: bool = False,
    ) -> list[TaskItem]:
        return self._list_tasks_unlocked(
            status=status,
            owner=owner,
            priority=priority,
            sort_by_priority=sort_by_priority,
        )

    def _list_tasks_unlocked(
        self,
        status: TaskStatus | None = None,
        owner: str | None = None,
        priority: TaskPriority | None = None,
        sort_by_priority: bool = False,
    ) -> list[TaskItem]:
        root = _tasks_root(self.team_name)
        tasks = []
        for f in sorted(root.glob("task-*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                task = TaskItem.model_validate(data)
                if status and task.status != status:
                    continue
                if owner and task.owner != owner:
                    continue
                if priority and task.priority != priority:
                    continue
                tasks.append(task)
            except (json.JSONDecodeError, OSError, ValueError):
                continue
        if sort_by_priority:
            priority_order = {
                TaskPriority.urgent: 0,
                TaskPriority.high: 1,
                TaskPriority.medium: 2,
                TaskPriority.low: 3,
            }
            tasks.sort(key=lambda task: (priority_order.get(task.priority, 2), task.created_at, task.id))
        return tasks

    def _validate_blocked_by_unlocked(self, task_id: str, blocked_by: list[str]) -> None:
        if task_id in blocked_by:
            raise ValueError(f"Task '{task_id}' cannot be blocked by itself")

        graph: dict[str, list[str]] = {
            task.id: list(task.blocked_by)
            for task in self._list_tasks_unlocked()
        }
        graph[task_id] = list(blocked_by)

        visiting: set[str] = set()
        visited: set[str] = set()

        def _visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in graph.get(node, []):
                if dep in graph and _visit(dep):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        for node in graph:
            if _visit(node):
                raise ValueError("Task dependencies cannot contain cycles")

    def _save_unlocked(self, task: TaskItem) -> None:
        path = _task_path(self.team_name, task.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f"{path.stem}-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(task.model_dump_json(indent=2, by_alias=True))
            Path(tmp_name).replace(path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------ #
    # Resolution manifest (atomic dependent unblocking)                        #
    # ------------------------------------------------------------------ #

    def _begin_resolution_manifest(
        self, completed_task_id: str, dependent_ids: list[str]
    ) -> None:
        """Write a resolution manifest so the operation can be replayed on crash."""
        path = _resolution_manifest_path(self.team_name, completed_task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "completed_task_id": completed_task_id,
            "dependent_ids": dependent_ids,
            "timestamp": _now_iso(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _complete_resolution(self, completed_task_id: str) -> None:
        """Delete the manifest to signal successful completion."""
        path = _resolution_manifest_path(self.team_name, completed_task_id)
        path.unlink(missing_ok=True)

    def _resolve_dependents_unlocked(self, completed_task_id: str) -> None:
        # Collect all dependent task IDs first (before any saves)
        dependent_ids: list[str] = []
        root = _tasks_root(self.team_name)
        for f in root.glob("task-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                task = TaskItem.model_validate(data)
                if completed_task_id in task.blocked_by:
                    dependent_ids.append(task.id)
            except (json.JSONDecodeError, OSError, ValueError):
                continue

        if not dependent_ids:
            return

        # Write manifest before any saves (allows replay on crash)
        self._begin_resolution_manifest(completed_task_id, dependent_ids)

        try:
            for task_id in dependent_ids:
                task = self._get_unlocked(task_id)
                if task is None:
                    continue
                if completed_task_id in task.blocked_by:
                    task.blocked_by.remove(completed_task_id)
                    if not task.blocked_by and task.status == TaskStatus.blocked:
                        task.status = TaskStatus.pending
                    task.updated_at = _now_iso()
                    self._save_unlocked(task)
        finally:
            # Delete manifest only after all saves succeed
            self._complete_resolution(completed_task_id)

    def _replay_pending_resolutions(self) -> None:
        """Replay any orphaned resolution manifests left over from a crashed process."""
        team_dir = _team_dir(self.team_name)
        for f in team_dir.glob("resolution-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                completed_id = data.get("completed_task_id", "")
                dependent_ids = data.get("dependent_ids", [])
                if not completed_id or not dependent_ids:
                    f.unlink(missing_ok=True)
                    continue
                # Re-resolve: run the unblocking logic for each dependent
                for task_id in dependent_ids:
                    task = self._get_unlocked(task_id)
                    if task is None:
                        continue
                    if completed_id in task.blocked_by:
                        task.blocked_by.remove(completed_id)
                        if not task.blocked_by and task.status == TaskStatus.blocked:
                            task.status = TaskStatus.pending
                        task.updated_at = _now_iso()
                        self._save_unlocked(task)
                f.unlink(missing_ok=True)
            except (json.JSONDecodeError, OSError, ValueError):
                # Corrupt manifest – remove it
                f.unlink(missing_ok=True)
                continue
