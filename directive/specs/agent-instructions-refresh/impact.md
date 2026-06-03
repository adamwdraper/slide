# Impact Analysis — Agent Instructions Refresh

## Modules/packages likely touched
- `packages/tyler/tyler/models/agent.py`
- `packages/tyler/tyler/models/agents_md.py`
- `packages/tyler/tyler/models/completion_handler.py`
- `packages/tyler/tyler/models/skill.py`
- `packages/tyler/tyler/cli/chat.py`
- Tyler tests, docs, and config examples

## Contracts to update (APIs, events, schemas, migrations)
- `Agent.agents_md` default behavior changes from disabled to auto-discovery.
- New `Agent.agents_md_base_dir` config field for deterministic discovery.
- New `Agent.instruction_role` / `CompletionHandler.instruction_role` field with values `system` or `developer`.
- No database migrations, event schema changes, or external API changes.

## Risks
- Security: AGENTS.md auto-discovery can load local project instructions unexpectedly unless disabled.
- Performance/Availability: prompt size can increase, but existing AGENTS.md size guards remain.
- Data integrity: no persisted data model changes.

## Observability needs
- Logs: keep existing warnings for missing, unreadable, or oversized AGENTS.md files.
- Metrics: no new metrics required.
- Alerts: no new alerts required.
