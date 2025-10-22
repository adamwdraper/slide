# Impact Analysis — MCP first-class configuration in Tyler

## Modules/packages likely touched
- packages/tyler/tyler/cli/chat.py — load_config: parse new `mcp:` section; auto-connect/register tools on startup
- packages/tyler/tyler/models/agent.py — accept `mcp` kwarg; connect/register during init
- packages/tyler/tyler/mcp/adapter.py — add namespacing and include/exclude filtering (if not already sufficient)
- packages/tyler/tyler/mcp/client.py — ensure SSE/WebSocket support and connection ergonomics; non-fatal errors
- packages/tyler/examples — add example for YAML `mcp:` and Agent `mcp` usage
- docs — quickstart for MCP config (chat + Agent)

## Contracts to update (APIs, events, schemas, migrations)
- Agent constructor adds optional `mcp: Dict[str, Any]` param (runtime config only; no persistence schema changes)
- Chat YAML schema extended with:
  - `mcp.connect_on_start: bool`
  - `mcp.servers[]: { name, transport, url, namespace?, include_tools?, exclude_tools? }`
- No database schemas or migrations impacted

## Risks
- Security:
  - Connecting to arbitrary public MCP servers can expose tools invoking external APIs. Mitigation: clear warnings and docs; optional allowlist in future.
  - Auth flows surfaced by MCP endpoints (per Mintlify’s OpenAPI securitySchemes) prompt users; ensure we do not log secrets.
- Performance/Availability:
  - Startup delay while connecting to multiple servers or listing tools. Mitigation: connect concurrently with timeouts; continue on partial failure.
  - Large tool surfaces increase prompt size. Mitigation: include/exclude filters; namespacing; cap or summarize tool descriptions if needed.
- Data integrity:
  - N/A — no persistent data changed. Ensure tool execution results are sanitized for display.

## Observability needs
- Logs:
  - Info: server connect attempts, success/failure, tool counts per server
  - Warn: zero tools discovered, non-fatal connect/list errors, filtered tools summary
  - Debug: include/exclude filtering details
- Metrics:
  - mcp.connect.success_count, mcp.connect.failure_count
  - mcp.tools.discovered_total, mcp.tools.exposed_total
  - mcp.connect.latency_ms (per server), mcp.list.latency_ms
- Alerts:
  - Optional: high failure rate connecting to MCP servers on startup
