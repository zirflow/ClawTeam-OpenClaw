# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | ✅ Current         |
| < 0.3   | ❌ Unsupported     |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via:

1. **GitHub Security Advisories** — preferred for non-critical issues
   - Navigate to the repository → Security → Advisories → "Report a vulnerability"
2. **Email** — for critical vulnerabilities requiring private disclosure
   - Contact: security@zirflow.com

For non-critical bugs, regular GitHub Issues are appropriate.

## Security Best Practices for Production Use

When running ClawTeam in production:

- **Network isolation**: ClawTeam workers communicate over local filesystem and ZeroMQ.
  Ensure proper firewall rules if enabling ZeroMQ P2P transport.
- **Secret management**: Never commit credentials to workspaces. Use environment
  variables and OpenClaw's secrets management.
- **Worker process isolation**: Each worker runs as a subprocess. Ensure the spawning
  user has minimal required permissions.
- **Cron job delivery**: If configuring Feishu/Slack delivery for cron jobs,
  verify webhook URLs are kept confidential.

## Scope

This security policy covers the ClawTeam-OpenClaw orchestration framework.
Dependencies (OpenClaw, Claude Code, Codex, etc.) have their own security policies.
