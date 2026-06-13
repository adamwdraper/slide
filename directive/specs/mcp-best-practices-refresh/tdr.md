# Technical Design Review (TDR) — MCP Best-Practices Refresh

**Author**: Codex
**Date**: 2026-06-04
**Links**: Spec (`/directive/specs/mcp-best-practices-refresh/spec.md`), Impact (`/directive/specs/mcp-best-practices-refresh/impact.md`)

---

## 1. Summary
Refresh Tyler's MCP integration around the MCP 2025-11-25 stable framing while keeping the existing cross-provider MCP SDK adapter as the integration path. The public API remains `Agent(mcp={...})`, `await agent.connect_mcp()`, and `await agent.cleanup()`.

The implementation will tighten config validation, map current Python SDK transport options, preserve richer MCP tool metadata, safely serialize tool results, and make cleanup remove dynamically registered MCP tools so reconnects do not duplicate exposed definitions. Docs and examples will position Streamable HTTP as the default remote transport, `stdio` as the local transport, and SSE as legacy compatibility.

## 2. Decision Drivers & Non-Goals
- Drivers: current MCP spec alignment, cross-provider compatibility, predictable cleanup, safer defaults, and docs that reduce unsafe MCP server usage.
- Non-Goals: provider-native OpenAI MCP, roots, elicitation UI, OAuth browser flow, progressive runtime discovery, and A2A API changes.

## 3. Current State — Codebase Map
- `packages/tyler/tyler/mcp/config_loader.py` validates Tyler MCP config, builds SDK `StdioServerParameters`, `SseServerParameters`, and `StreamableHttpParameters`, connects via `ClientSessionGroup`, converts SDK tools to Tyler dict tools, and creates closures that call `group.call_tool()`.
- `packages/tyler/tyler/models/agent.py` validates MCP config in `__init__`, exposes `connect_mcp()`, appends MCP tool dicts to `self.tools`, rebuilds the tool manager, and stores an MCP disconnect callback. `cleanup()` currently disconnects but does not remove MCP tools from exposed tools.
- `ToolRunner` registers tool implementations, definitions, attributes, and optional per-tool execution timeouts.
- Existing tests cover basic validation, env substitution, parameter mapping, progress callbacks, collision avoidance, `connect_mcp()`, and cleanup basics.
- Docs currently include MCP guides, concepts, API docs, CLI config docs, and Tyler examples. Some comments mention `websocket` and cleanup guidance is inconsistent.

## 4. Proposed Design
- Keep Tyler's SDK-backed adapter and public API unchanged.
- Expand validation in `_validate_server_config()`:
  - Require server dicts with string `name` and transport in `stdio`, `streamablehttp`, or `sse`.
  - Require `command` for `stdio` and `url` for HTTP transports.
  - Require `http` or `https` URL schemes for `streamablehttp` and legacy `sse`.
  - Validate list fields (`args`, `include_tools`, `exclude_tools`), dict fields (`env`, `headers`), boolean fields (`fail_silent`, `terminate_on_close`), and positive numeric fields (`max_retries`, `timeout_seconds`, `sse_read_timeout_seconds`, `tool_timeout_seconds`).
- Map optional SDK parameter fields in `_build_server_params()` only when supported by the installed SDK.
- Sanitize the complete exposed name `<prefix>_<original_tool_name>` into OpenAI-compatible function names (`[A-Za-z0-9_-]`, max 64 chars), with deterministic hashing when truncation is needed.
- Preserve MCP metadata in attributes, including server name, original name, SDK name, exposed name, schema/annotation/icon fields, execution metadata, and `_meta`.
- Serialize tool call results with a helper:
  - Raise when `isError` is true.
  - Prefer `structuredContent`.
  - Return a single text content item as a string.
  - Return multiple text items as a list.
  - Convert non-text content to JSON-compatible dictionaries using model dump APIs when available.
- Track dynamic MCP tool names on the agent. On cleanup, disconnect and remove those tools from `self.tools`, `_processed_tools`, runner registries, attributes cache, and prompt text.

## 5. Alternatives Considered
- Add provider-native OpenAI MCP support now: rejected because it would fragment cross-provider behavior and is explicitly out of scope.
- Keep permissive config validation: rejected because invalid transports, schemes, and timeout values fail late and obscure MCP trust boundaries.
- Leave cleanup as disconnect-only: rejected because reconnect currently risks duplicate tool definitions and stale prompts.

## 6. Data Model & Contract Changes
- No persistent data model changes.
- MCP config adds optional fields while preserving existing required fields.
- Tool attribute metadata is additive and backward compatible.
- A2A APIs remain unchanged; docs will clarify A2A is for agent-to-agent delegation, not general external tool integration.

## 7. Security, Privacy, Compliance
- MCP tools are privileged integrations and should be treated as untrusted unless the server is reviewed and trusted.
- Secrets remain environment-variable based; examples avoid hardcoded secrets.
- Tool annotations and descriptions are advisory and not a trust boundary.
- Include/exclude filters are recommended to minimize exposed tools and avoid always-on large catalogs.

## 8. Observability & Operations
- Continue using existing logging for connection attempts, retry failures, disconnect errors, and name collisions.
- No dashboards, alerts, or SLO changes in this pass.

## 9. Rollout & Migration
- Backward compatible for existing `stdio`, `streamablehttp`, and `sse` users with valid URLs/options.
- Invalid config now fails fast at agent construction.
- SSE remains supported as legacy compatibility.
- Revert plan: revert MCP adapter/docs/test changes; no data migrations involved.

## 10. Test Strategy & Spec Coverage (TDD)
- TDD commitment: add failing tests first, confirm failures where practical, then implement.
- Config validation tests: invalid transport, URL schemes, option types, positive values, and required transport fields.
- Parameter mapping tests: optional timeout/read/process/encoding/cwd fields propagate into SDK parameter objects where supported.
- Tool conversion tests: metadata preservation, full exposed name sanitization/truncation, include/exclude behavior, and collision warning compatibility.
- Tool result tests: structured content preference, simple text returns, multiple/non-text content serialization, `isError` raises, progress callback, and read/progress timeout propagation.
- Agent lifecycle tests: cleanup removes MCP tools, reconnect does not duplicate tools, system prompt regenerates after cleanup, and skills/AGENTS.md prompt content is preserved.
- CLI/docs tests: YAML examples and docs do not claim `websocket`; examples recommend `try/finally await agent.cleanup()`.

## 11. Risks & Open Questions
- SDK parameter names may differ across compatible versions. Mitigation: inspect constructor signatures and set only supported fields.
- Sanitized names may collide after truncation. Mitigation: deterministic suffixes and existing collision logging.
- Some MCP content objects may have SDK-specific serialization shapes. Mitigation: prefer `model_dump()`/`dict()` and fall back to public non-callable attributes.

## 12. Milestones / Plan
- Add spec, impact, and TDR docs.
- Add focused failing tests for MCP validation, mapping, metadata, result serialization, and lifecycle cleanup.
- Implement adapter and lifecycle changes.
- Update docs, examples, and YAML comments.
- Refresh `uv.lock` for `mcp 1.27.2`.
- Run the requested targeted test command.

---

**Approval Gate**: User supplied an implementation plan and asked to implement it in this workspace on 2026-06-04.
