---
name: clawteam
description: "Multi-agent swarm coordination for OpenClaw agents and Claude Code. Use when: the user wants to create agent teams, spawn multiple agents to work in parallel, coordinate tasks with dependencies, broadcast messages between agents, monitor progress via kanban board, or launch pre-built team templates (hedge-fund, code-review, research-paper). Also use when the user asks to: split this task across agents, run multiple agents at once, have agents work together, coordinate a team of agents. ClawTeam uses git worktree isolation + tmux/subprocess + filesystem-based messaging. Trigger phrases: clawteam, multi-agent, agent team, spawn agents, parallel agents, swarm, use clawteam, create a team, let agents work together, coordinate agents, split work across agents, multiple agents at once, hedge fund analysis, code review team, research team, research paper team."
---

# ClawTeam — Multi-Agent Swarm Coordination

## Overview

ClawTeam is a CLI tool (`clawteam`) for orchestrating multiple AI agents as self-organizing swarms. It uses git worktree isolation, tmux windows, and filesystem-based messaging. OpenClaw is the default agent backend.

**CLI binary**: `clawteam` (installed via pip, available in PATH)


## 🛠️ Install (for AI Agents)

If `clawteam` is not installed, install it first:

```bash
# Clone the Zirflow-maintained fork (includes OpenClaw fixes)
git clone https://github.com/zirflow/ClawTeam-OpenClaw.git /tmp/ClawTeam-OpenClaw

# Install CLI (full OpenClaw integration)
pip install -e /tmp/ClawTeam-OpenClaw --break-system-packages

# Create symlink so clawteam is always on PATH
mkdir -p ~/bin
ln -sf "$(which clawteam)" ~/bin/clawteam

# Verify
clawteam --version
```

For humans: `pip install -e "git+https://github.com/zirflow/ClawTeam-OpenClaw.git#egg=clawteam" --break-system-packages`


## Quick Start

### One-Command Template Launch (Recommended)

```bash
# Launch a pre-built team from a template
clawteam launch hedge-fund --team fund1
clawteam launch code-review --team review1
clawteam launch research-paper --team paper1
```

### Manual Team Setup

```bash
# 1. Create team with leader
clawteam team spawn-team my-team -d "Build a web app" -n leader

# 2. Create tasks with dependencies
clawteam task create my-team "Design API schema" -o architect
# Returns task ID, e.g., abc123

clawteam task create my-team "Implement auth" -o backend --blocked-by abc123
clawteam task create my-team "Build frontend" -o frontend --blocked-by abc123
clawteam task create my-team "Write tests" -o tester

# 3. Spawn agents (each gets its own tmux window + git worktree)
clawteam spawn -t my-team -n architect --task "Design the API schema for a web app"
clawteam spawn -t my-team -n backend --task "Implement OAuth2 authentication"
clawteam spawn -t my-team -n frontend --task "Build React dashboard"

# 4. Monitor
clawteam board show my-team        # Kanban view
clawteam board attach my-team      # Tmux tiled view (all agents side-by-side)
clawteam board serve --port 8080   # Web dashboard
```

## Command Reference

### Team Management

| Command | Description |
|---------|-------------|
| `clawteam team spawn-team <name> -d "<desc>" -n <leader>` | Create team |
| `clawteam team discover` | List all teams |
| `clawteam team status <team>` | Show team members and info |
| `clawteam team cleanup <team> --force` | Delete team and all data |

### Task Management

| Command | Description |
|---------|-------------|
| `clawteam task create <team> "<subject>" -o <owner> [-d "<desc>"] [--blocked-by <id>]` | Create task |
| `clawteam task list <team> [--owner <name>]` | List tasks (filterable) |
| `clawteam task update <team> <id> --status <status> --owner <name>` | Update status (set owner so EXIT hook can find task) |
| `clawteam task get <team> <id>` | Get single task |
| `clawteam task stats <team>` | Timing statistics |
| `clawteam task wait <team>` | Block until all tasks complete |

**Task statuses**: `pending`, `in_progress`, `completed`, `blocked`

**Dependency auto-resolution**: When a blocking task completes, dependent tasks automatically change from `blocked` to `pending`.

**Task locking**: When a task moves to `in_progress`, it is locked by the calling agent. Other agents cannot claim it unless they use `--force`. Stale locks from dead agents are automatically released.

### Agent Spawning

**IMPORTANT**: Always use the default command (`openclaw`) — do NOT override to `claude` or other agents. The default handles permissions, prompt injection, and nesting detection correctly. If you specify `claude` as the command, agents will get stuck on interactive permission prompts.

```bash
# Default (tmux backend): openclaw tui in tmux — routes to main agent, may queue if busy
clawteam spawn -t <team> -n <name> --task "<task description>"

# Subprocess backend (RECOMMENDED for bash commands):
# - Does NOT route to main agent — independent subprocess, <2s completion
# - Exit Protocol via Python monitor thread (subprocess_wrapper.py)
clawteam spawn subprocess -t <team> -n <name> -- bash -c 'echo DONE'

# tmux backend (for interactive AI agent tasks):
clawteam spawn tmux -t <team> -n <name> --task "<task>"

# With git worktree isolation
clawteam spawn -t <team> -n <name> --task "<task>" --workspace --repo /path/to/repo
```

Each spawned agent gets:
- Its own tmux window (visible via `board attach`)
- Its own git worktree branch (`clawteam/{team}/{agent}`)
- An auto-injected coordination prompt (how to use clawteam CLI)
- Environment variables: `CLAWTEAM_AGENT_NAME`, `CLAWTEAM_TEAM_NAME`, etc.

**Spawn safety features:**
- Commands are pre-validated before launch — you get a clear error if the agent CLI is not installed
- If a spawn fails, the registered team member and worktree are automatically rolled back
- Claude Code and Codex workspace trust prompts are auto-confirmed in fresh worktrees

### Messaging

| Command | Description |
|---------|-------------|
| `clawteam inbox send <team> <to> "<msg>" --from <sender>` | Point-to-point message |
| `clawteam inbox broadcast <team> "<msg>" --from <sender>` | Broadcast to all |
| `clawteam inbox peek <team> -a <agent>` | Peek without consuming |
| `clawteam inbox receive <team>` | Consume messages |
| `clawteam inbox log <team>` | View message history |

### Monitoring

| Command | Description |
|---------|-------------|
| `clawteam board show <team>` | Kanban board (rich terminal) |
| `clawteam board overview` | All teams overview |
| `clawteam board live <team>` | Live-refreshing board |
| `clawteam board attach <team>` | Tmux tiled view |
| `clawteam board serve --port 8080` | Web dashboard |

### Cost Tracking

| Command | Description |
|---------|-------------|
| `clawteam cost report <team> --input-tokens <N> --output-tokens <N> --cost-cents <N>` | Report usage |
| `clawteam cost show <team>` | Show summary |
| `clawteam cost budget <team> <dollars>` | Set budget |

### Templates

| Command | Description |
|---------|-------------|
| `clawteam template list` | List available templates |
| `clawteam template show <name>` | Show template details |
| `clawteam launch <template> [--team-name <name>] [--goal "<goal>"]` | Launch from template |

**Built-in templates**: `hedge-fund`, `code-review`, `research-paper`

### Configuration

```bash
clawteam config show                           # Show all settings
clawteam config set transport file             # Set transport backend
clawteam config set skip_permissions true      # Auto-skip permission prompts
clawteam config health                         # System health check
```

### Other Commands

| Command | Description |
|---------|-------------|
| `clawteam lifecycle idle <team> --agent <name>` | Report agent idle |
| `clawteam session save <team> --session-id <id>` | Save session for resume |
| `clawteam plan submit <team> "<plan>" --from <agent>` | Submit plan for approval (team-scoped storage) |
| `clawteam workspace list <team>` | List git worktrees |
| `clawteam workspace merge <team> --agent <name>` | Merge agent branch |

## JSON Output

Add `--json` before any subcommand for machine-readable output:

```bash
clawteam --json task list my-team
clawteam --json team status my-team
```

## Typical Workflow

1. **User says**: "Create a team to build a web app"
2. **You do**: `clawteam team spawn-team webapp -d "Build web app" -n leader`
3. **Create tasks**: Use `clawteam task create` with `--blocked-by` for dependencies
4. **Spawn agents**: Use `clawteam spawn` for each worker
5. **Monitor**: Start a background polling loop immediately — do NOT wait for user to ask
6. **Communicate**: Use `clawteam inbox broadcast` for team-wide updates
7. **Deliver**: Proactively send final results to the user as soon as all tasks complete
8. **Cleanup**: `clawteam cost show`, `clawteam task stats`, merge worktrees, then `clawteam team cleanup webapp --force`

## Leader Orchestration Pattern

When YOU are the leader agent, follow this pattern to autonomously manage a swarm:

### Phase 1: Analyze & Plan
```
1. Understand the user's goal
2. Break it into independent subtasks
3. Identify dependencies between tasks (what must finish before what)
4. Decide how many worker agents are needed
```

### Phase 2: Setup
```bash
# Create team
clawteam team spawn-team <team> -d "<goal description>" -n leader

# Create tasks with dependency chains
clawteam task create <team> "Design API" -o architect
# Save the returned task ID (e.g., abc123)
clawteam task create <team> "Build backend" -o backend --blocked-by abc123
clawteam task create <team> "Build frontend" -o frontend --blocked-by abc123
clawteam task create <team> "Integration tests" -o tester --blocked-by <backend-id>,<frontend-id>
```

### Phase 3: Spawn Workers
```bash
# Each spawn launches an openclaw tui in its own tmux window
clawteam spawn -t <team> -n architect --task "Design REST API schema for <goal>"
clawteam spawn -t <team> -n backend --task "Implement backend based on API schema"
clawteam spawn -t <team> -n frontend --task "Build React frontend"
clawteam spawn -t <team> -n tester --task "Write and run integration tests"
```

### Phase 4: Monitor Loop

**IMPORTANT**: Start monitoring immediately after spawning — do NOT wait for the user to ask for status updates. Run the monitor loop in the background right away so you can:
1. **Push mid-progress updates proactively** — when ~50% of tasks complete, send the user a brief status update (e.g. "4/7 agents done, 3 still working"). Do NOT wait for them to ask.
2. **Deliver final results immediately** when all tasks complete.
3. **Keep workers fed** — detect idle workers with pending tasks and send continuation instructions.

```bash
# Poll task status every 30-60 seconds
while true; do
  # Get task status
  TASK_STATUS=$(clawteam task list <team> --json 2>/dev/null | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
done = sum(1 for t in tasks if t['status'] == 'completed')
pending = sum(1 for t in tasks if t['status'] == 'pending')
in_progress = sum(1 for t in tasks if t['status'] == 'in_progress')
total = len(tasks)
print(f'DONE={done} PENDING={pending} IN_PROGRESS={in_progress} TOTAL={total}')
")
  echo "$TASK_STATUS"
  
  # Check for messages from workers
  clawteam inbox receive <team>
  
  # Send mid-progress update when roughly half the tasks are done
  DONE=$(echo "$TASK_STATUS" | grep -oP 'DONE=\K\d+')
  TOTAL=$(echo "$TASK_STATUS" | grep -oP 'TOTAL=\K\d+')
  if [ "$DONE" -ge $((TOTAL / 2)) ] && [ "$DONE" -lt "$TOTAL" ]; then
    echo "[Monitor] Mid-progress: $DONE/$TOTAL complete — pushing update"
    # Send update to user via feishu message tool
    # (handled by the agent — not a CLI command)
  fi
  
  # CRITICAL: If workers are idle (inbox empty) but pending tasks exist,
  # send continuation instructions. Workers go idle when their inbox is empty
  # after completing a task — they need explicit instruction to continue.
  PENDING=$(echo "$TASK_STATUS" | grep -oP 'PENDING=\K\d+')
  IN_PROGRESS=$(echo "$TASK_STATUS" | grep -oP 'IN_PROGRESS=\K\d+')
  if [ "$PENDING" -gt 0 ] && [ "$IN_PROGRESS" -eq 0 ]; then
    echo "[Monitor] Workers idle but $PENDING tasks pending — sending continuation"
    # Get list of pending tasks
    PENDING_TASKS=$(clawteam task list <team> --json 2>/dev/null | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
for t in tasks:
  if t['status'] == 'pending':
    print(f\"ID={t['id']} SUBJECT={t['subject'][:40]}\")
")
    echo "Pending tasks:"
    echo "$PENDING_TASKS"
    # Send message to leader's inbox instructing workers to self-assign
    clawteam inbox send <team> leader "[AUTO] $PENDING tasks still pending. " \
      "Send continuation instructions to workers to pick up: $PENDING_TASKS"
    # Send continuation to each idle worker (they check inbox on idle)
    for worker in <agent1> <agent2> ...; do
      NEXT_TASK=$(clawteam task list <team> --json 2>/dev/null | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
for t in tasks:
  if t['status'] == 'pending' and not t.get('owner'):
    print(t['id'])
    break
" 2>/dev/null)
      if [ -n "$NEXT_TASK" ]; then
        clawteam inbox send <team> leader $worker \
          "CONTINUE: Assign task $NEXT_TASK to yourself and start working."
      fi
    done
  fi
  
  if [ "$DONE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "[Monitor] All $TOTAL tasks complete — converging"
    break
  fi
  sleep 30
done
```

**Key coordination fix**: Workers go idle after completing a task (inbox empty → they call `lifecycle idle`). The leader MUST send continuation instructions via inbox when pending tasks exist. Without this, workers sit idle forever.

### Phase 5: Converge & Report

**IMPORTANT**: Proactively deliver results to the user as soon as all tasks complete. Do NOT wait for the user to ask. Include the final output, a summary, and cost/timing stats. ALWAYS merge worktrees and clean up.

```bash
# After all tasks complete — do ALL of these steps:
clawteam board show <team>           # Final status
clawteam cost show <team>            # Total cost — include in report to user
clawteam task stats <team>           # Timing stats — include in report to user
# Merge each worker's branch back to main
for agent in <agent1> <agent2> ...; do
  clawteam workspace merge <team> --agent $agent
done
clawteam team cleanup <team> --force  # Clean up — ALWAYS do this last
# Then: send the final deliverables to the user immediately
```

### Decision Rules for the Leader
- **Independent tasks** → spawn workers in parallel
- **Sequential tasks** → use `--blocked-by` to chain them; ClawTeam auto-unblocks
- **Worker asks for help** → check inbox, provide guidance via `inbox send`
- **Worker stuck** → check task status; if `in_progress` too long, send a nudge via `inbox send`
- **Worker done** → verify result via inbox message, then move to next phase
- **All done** → merge worktrees, deliver results to user proactively, then cleanup
- **Always** → start background monitoring immediately after spawn; never wait for user to ask for status

## Data Location

All state stored in `~/.clawteam/`:
- Teams: `~/.clawteam/teams/<team>/config.json`
- Tasks: `~/.clawteam/tasks/<team>/task-<id>.json` (with `fcntl` file locking for concurrent safety)
- Plans: `~/.clawteam/plans/<team>/<agent>-<plan_id>.md` (team-scoped, isolated per team)
- Messages: `~/.clawteam/teams/<team>/inboxes/<agent>/msg-*.json`
- Costs: `~/.clawteam/costs/<team>/`
