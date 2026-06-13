# Impact Analysis — MCP Best-Practices Refresh

## Modules/packages likely touched
- `packages/tyler/tyler/mcp/config_loader.py` for config validation, SDK parameter mapping, tool conversion, metadata preservation, and result serialization.
- `packages/tyler/tyler/models/agent.py` and `packages/tyler/tyler/utils/tool_runner.py` for MCP tool lifecycle cleanup and reconnect behavior.
- `packages/tyler/tests/mcp/`, `packages/tyler/tests/models/`, and `packages/tyler/tests/cli/` for TDD coverage.
- `packages/tyler/examples/`, `packages/tyler/README.md`, `docs/guides/`, `docs/concepts/`, `docs/apps/`, `docs/api-reference/`, `docs/docs.json`, and Tyler YAML examples for updated MCP guidance.
- Root `uv.lock` for the latest compatible `mcp` dependency resolution.

## Contracts to update (APIs, events, schemas, migrations)
- Public API remains `Agent(mcp={...})`, `await agent.connect_mcp()`, and `await agent.cleanup()`.
- MCP config schema gains optional fields: `timeout_seconds`, `sse_read_timeout_seconds`, `terminate_on_close`, `tool_timeout_seconds`, `cwd`, `encoding`, and `encoding_error_handler`.
- Tool attributes contract gains MCP metadata fields: server name, original name, SDK name, exposed name, `outputSchema`, annotations, icons, execution metadata, and `_meta`.
- No database migrations, event schema changes, or A2A contract changes.

## Risks
- Security: MCP servers can execute code or access sensitive data. Mitigation is compatible hardening: stricter config validation, docs that treat MCP tools and annotations as untrusted unless reviewed, env var guidance for secrets, and include/exclude filters.
- Performance/Availability: Remote MCP servers may hang or degrade agent runs. Mitigation is validated retry/timeout fields, SDK timeout propagation, and tool-level timeouts.
- Data integrity: Tool name sanitization/truncation can collide. Mitigation is deterministic suffixing for long names and warnings for collisions.

## Observability needs
- Logs: Retain connection attempt, retry, connection failure, cleanup, and tool collision logs.
- Metrics: No new metrics in this pass.
- Alerts: No new alerts in this pass.
