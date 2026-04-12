"""Agent prompt builder — minimal coordination only.

The tmux_backend sets CLAWTEAM_AGENT_NAME, CLAWTEAM_TEAM_NAME env vars
and creates a minimal worker-workspace with AGENTS.md.
Keep this prompt lean — it is sent as a --task message to the TUI on every spawn.
"""


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
    """Build minimal agent prompt for ClawTeam workers."""
    lines = [
        "You are a ClawTeam worker agent.",
        f"Team: {team_name}. Your name: {agent_name}.",
        f"Environment: CLAWTEAM_AGENT_NAME={agent_name}, CLAWTEAM_TEAM_NAME={team_name}",
        "",
        "WORKFLOW:",
        "1. Check CLAWTEAM_AGENT_NAME env var to know your role",
        f"2. Read ~/.clawteam/teams/{team_name}/tasks/ for your tasks",
        f"3. Do your work, write output to /tmp/{team_name}/{agent_name}-output.md",
        f"4. Send result to leader: clawteam inbox send {team_name} {leader_name} <summary>",
        f"5. On exit: clawteam lifecycle on-exit --team {team_name} --agent {agent_name} --exit-code 0",
        "6. Type 'exit' to terminate",
        "",
        "TASK:",
        task,
        "",
        "Be concise. Write results to /tmp/{team_name}/{agent_name}-output.md",
    ]
    return "\n".join(lines)
