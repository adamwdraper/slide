# Technical Design Review (TDR) — MCP first-class configuration in Tyler

**Author**: Tyler agent (assistant)  
**Date**: 2025-10-22  
**Links**: Spec (`/directive/specs/mcp-first-class-config/spec.md`), Impact (`/directive/specs/mcp-first-class-config/impact.md`)

---

## 1. Summary
Add first-class MCP configuration so users can declare servers in chat YAML (`mcp:`) or pass an `mcp` argument to `Agent(...)`. Tyler auto-connects to servers on startup/initialization, discovers tools, namespaces them, and exposes them without custom shim code.

## 2. Decision Drivers & Non‑Goals
- Drivers: reduce setup friction; align with MCP client norms; improve multi-server ergonomics; keep startup resilient.
- Non‑Goals: UI for MCP management; persistence of runtime-added servers; advanced auth brokers.

## 3. Current State — Codebase Map (concise)
- `tyler/cli/chat.py`: loads YAML config, builds agent from config, processes tools list.
- `tyler/models/agent.py`: Agent constructor registers tools and drives execution.
- `tyler/mcp/client.py`: connects to servers via stdio/SSE/WebSocket and lists tools.
- `tyler/mcp/adapter.py`: converts MCP tools to Tyler function tools and registers with `tool_runner`.

## 4. Proposed Design (high level, implementation‑agnostic)
- YAML: Add `mcp.connect_on_start` and `mcp.servers[]` with fields {name, transport, url, namespace?, include_tools?, exclude_tools?}.
- Chat CLI: On load_config, if `mcp.connect_on_start`, connect to all servers concurrently using `MCPAdapter`; apply namespace + filters; append to tools list before Agent init.
- Python: `Agent(mcp=...)` accepts same structure; during `__init__`, connect concurrently, discover, filter, and include tools in `_processed_tools`.
- Error handling: timeouts per server, non-fatal on failure; warn and continue. Tool discovery empty → warn only.
- Performance: parallel connects; simple glob/pattern filtering; namespacing avoids collisions.

## 5. Alternatives Considered
- Keep shim files only: simplest to implement, but poor UX and discoverability.
- Environment variable–only wiring: brittle, lacks multi-server structure and filtering.
- Post-init API to add servers: useful but still requires code, not config-first.

## 6. Data Model & Contract Changes
- No storage changes. Runtime-only config:
  - YAML: `mcp.connect_on_start: bool`, `mcp.servers[]` as above.
  - Agent: `mcp: Dict[str, Any]` optional.

## 7. Security, Privacy, Compliance
- Do not log secrets or full request bodies. Redact auth headers.
- Document that public MCP servers may expose actions; recommend trusted sources.
- Honor Mintlify/OpenAPI securitySchemes: tool prompts for creds; ensure we don’t persist credentials.

## 8. Observability & Operations
- Logs: connect attempts, successes/failures, tool counts, filtered totals.
- Metrics: connect success/failure counts, latencies, tools discovered/exposed.
- Optional alert on sustained high failure rate.

## 9. Rollout & Migration
- No migration. Feature flag not required; behavior only triggers if `mcp` provided.
- Revert plan: remove `mcp` parsing and Agent arg; users can fall back to shim or no MCP.

## 10. Test Strategy & Spec Coverage (TDD)
- Unit: YAML parser merges tools with MCP-discovered; Agent `mcp` init connects and registers tools (mock MCP client).
- Contract: ensure tool definitions match expected shapes; namespacing and include/exclude patterns respected.
- Integration: simulated SSE server fixture returning a small toolset; verify tools callable end-to-end.
- Negative: invalid URL, timeout, zero tools, overlapping namespaces.
- CI: all new tests in `packages/tyler/tests/` run in CI.

## 11. Risks & Open Questions
- Risk: long startup for many servers → mitigate with timeouts and concurrency.
- Open: default transport precedence for Mintlify endpoints (prefer `/mcp/sse` first?). Proposal: try exact URL, else append `/sse` if not present.

## 12. Milestones / Plan (post‑approval)
- Implement YAML loader support and concurrent connects.
- Add Agent `mcp` constructor logic.
- Add include/exclude filtering and namespacing.
- Write tests; add examples and docs.
- Land in small PRs; keep CI green.

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved in the PR.
