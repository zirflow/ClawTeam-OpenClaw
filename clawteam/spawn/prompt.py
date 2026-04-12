"""Agent prompt builder — full worker prompt with mission, coordination, self-evaluation."""


def build_agent_prompt(
    agent_name: str,
    agent_id: str,
    agent_type: str,
    team_name: str,
    leader_name: str,
    task: str,
    user: str = "",
    workspace_dir: str = "",
    workspace_branch: str = "",
    memory_scope: str = "",
    intent: str = "",
    end_state: str = "",
    constraints: list[str] | None = None,
    team_size: int = 1,
) -> str:
    """Build full agent prompt for ClawTeam workers.
    
    Sections in order:
    - Identity (agent info, always)
    - User Context (if user provided)
    - Workspace (if workspace_dir provided)
    - Mission (if intent provided)            → ## Mission / **Intent:**
    - Coordination Rules (if team_size > 1)  → ## Coordination Rules (+ Boundary)
    - Task                                  → ## Task
    - Coordination Protocol (always)         → ## Coordination Protocol (+ task list)
    - Self-Evaluation (always)               → ## Self-Evaluation (+ confidence scoring)
    """
    if constraints is None:
        constraints = []

    lines = [
        "You are a ClawTeam worker agent.",
        f"Team: {team_name}. Your name: {agent_name}.",
        f"Environment: CLAWTEAM_AGENT_NAME={agent_name}, CLAWTEAM_TEAM_NAME={team_name}",
        f"Clawteam binary: $CLAWTEAM_BIN",
        "Note: For exec commands, add clawteam to the OpenClaw exec allowlist:",
        f"  openclaw approvals allowlist add --agent \"*\" \"$CLAWTEAM_BIN\"",
        "",
    ]

    # Include agent_id and agent_type for identity
    lines.append(f"Your ID: {agent_id}")
    lines.append(f"Role: {agent_type}")
    lines.append("")

    # User context section
    if user:
        lines.extend([
            "## User Context",
            f"User: {user}",
            "",
        ])

    # Workspace context section
    if workspace_dir:
        lines.extend([
            "## Workspace",
            f"Working directory: {workspace_dir}",
            f"Branch: {workspace_branch}",
            "This is an isolated git worktree for your exclusive use.",
            "",
        ])

    # Mission / Intent section (Auftragstaktik)
    if intent:
        lines.extend([
            "## Mission",
            f"**Intent:** {intent}",
            "",
        ])

    # End state and constraints (come after mission)
    if end_state:
        lines.append(f"**End State:**\n{end_state}\n")
    if constraints:
        lines.append("**Constraints:**")
        for c in constraints:
            lines.append(f"- {c}")
        lines.append("")

    # Coordination Rules — boids rules for multi-agent teams ONLY
    if team_size > 1:
        lines.extend([
            "## Coordination Rules",
            "You are part of a multi-agent team. Follow these boids rules:",
            "1. **Separation**: Be aware of teammates' tasks to avoid duplication.",
            "2. **Alignment**: Sync with leader via `clawteam inbox send` for major decisions.",
            "3. **Cohesion**: After completing your task, check if teammates need help.",
            "4. **Boundary**: Stay within your assigned scope; escalate overflow to leader.",
            "",
        ])

    # Task section
    lines.extend([
        "## Task",
        task,
        "",
    ])

    # Auto-Confirm Timeout Section (always present)
    lines.extend([
        "## Auto-Confirm Timeout",
        "When a prompt requires user confirmation with timeout behavior:",
        "",
        "**Multiple choice format:**",
        "  `A)xxx B)yyy 默认B 30s超时自动选`",
        "  → After 30 seconds of no response, automatically select option B (the default).",
        "",
        "**Yes/No format:**",
        "  `确认？[Y/n] 默认Y 30s超时自动继续`",
        "  → After 30 seconds of no response, automatically proceed with Y (the default).",
        "",
        "**Implementation notes:**",
        "- Default option is indicated by uppercase letter or capitalized [Y/n] pattern.",
        "- Timeout countdown starts when the prompt is displayed.",
        "- On timeout, the default option is selected automatically.",
        "",
    ])

    # Coordination Protocol (always present)
    lines.extend([
        "## Coordination Protocol",
        "After completing your work:",
        f"1. Run: clawteam task list {team_name} --owner {agent_name}",
        f"2. Mark completed: clawteam task update <id> --status completed --owner {agent_name}",
        f"3. Notify leader: clawteam inbox send {team_name} {leader_name} 'Task done.'",
        f"4. On exit: clawteam lifecycle on-exit --team {team_name} --agent {agent_name} --exit-code 0",
        "",
        "## Exit Protocol",
        "When all steps above are complete, you MUST:",
        "Write the following line as your FINAL response line (nothing after it):",
        "exit 0",  # VERY IMPORTANT: This must be your LAST output to close the tmux pane!
        # Do NOT output anything after this. Your session will auto-close after this line.",
        "",
    ])

    # Self-Evaluation + Exit Protocol - streamlined, no pauses
    lines.extend([
        "## Self-Evaluation + Exit",
        "Quick reflection (internal, no pause), then output ONLY:",
        "exit 0",
        "",
        "This closes the pane automatically.",
    ])

    # Workflow reminder
    lines.extend([
        f"Be concise. Write results to /tmp/{team_name}/{agent_name}-output.md",
    ])

    return "\n".join(lines)
