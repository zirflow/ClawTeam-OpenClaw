"""Plan approval workflow for team agents."""

from __future__ import annotations

import uuid
from pathlib import Path

from clawteam.team.mailbox import MailboxManager
from clawteam.team.models import MessageType, get_data_dir


def _plans_root() -> Path:
    d = get_data_dir() / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return d


class PlanManager:
    """Manages plan submission and approval between team members and leader."""

    def __init__(self, team_name: str, mailbox: MailboxManager):
        self.team_name = team_name
        self.mailbox = mailbox

    def submit_plan(
        self,
        agent_name: str,
        leader_name: str,
        plan_content: str,
        summary: str = "",
    ) -> str:
        plan_id = uuid.uuid4().hex[:12]
        plan_path = _plans_root() / f"{agent_name}-{plan_id}.md"
        plan_path.write_text(plan_content, encoding="utf-8")

        self.mailbox.send(
            from_agent=agent_name,
            to=leader_name,
            msg_type=MessageType.plan_approval_request,
            request_id=plan_id,
            plan_file=str(plan_path),
            summary=summary or plan_content[:200],
            plan=plan_content,
        )
        return plan_id

    def approve_plan(
        self,
        leader_name: str,
        plan_id: str,
        agent_name: str,
        feedback: str = "",
    ) -> None:
        self.mailbox.send(
            from_agent=leader_name,
            to=agent_name,
            msg_type=MessageType.plan_approved,
            request_id=plan_id,
            feedback=feedback or None,
        )

    def reject_plan(
        self,
        leader_name: str,
        plan_id: str,
        agent_name: str,
        feedback: str = "",
    ) -> None:
        self.mailbox.send(
            from_agent=leader_name,
            to=agent_name,
            msg_type=MessageType.plan_rejected,
            request_id=plan_id,
            feedback=feedback or None,
        )

    @staticmethod
    def get_plan(plan_id: str, agent_name: str) -> str | None:
        plan_path = _plans_root() / f"{agent_name}-{plan_id}.md"
        if plan_path.exists():
            return plan_path.read_text(encoding="utf-8")
        return None
