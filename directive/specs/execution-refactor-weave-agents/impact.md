# Impact Analysis - Tyler execution refactor with Weave Agents tracing

## Modules/packages likely touched
- `packages/tyler/tyler/models/agent.py`
- `packages/tyler/tyler/models/execution.py`
- `packages/tyler/tyler/models/tool_manager.py`
- `packages/tyler/tyler/models/skill.py`
- `packages/tyler/tyler/streaming/core.py`
- `packages/tyler/tyler/utils/tool_runner.py`
- `packages/tyler/pyproject.toml`
- `uv.lock`
- Tyler unit tests under `packages/tyler/tests/`

## Contracts to update (APIs, events, schemas, migrations)
- `AgentResult` gains an `execution` field.
- New execution summary/tool call summary dataclasses.
- Agent-owned `ToolRunner` becomes the execution source for regular, skill, delegation, and MCP tools.
- New optional Weave Agents adapter contract around `start_session`, `start_turn`, `start_llm`, and `start_tool`.

## Risks
- Security: tool context still contains user-provided dependencies; tracing adapter must avoid requiring Weave and should keep payloads to existing request/tool data.
- Performance/Availability: per-agent runners increase registration work per agent but prevent global mutation; tracing adapter must be no-op safe.
- Data integrity: thread/message creation and persistence order must remain unchanged across tool iterations.

## Observability needs
- Logs: keep existing error logs for LLM and tool failures.
- Metrics: expose duration, token totals, and tool call summaries on `AgentResult.execution`.
- Alerts: none added in this pass.
