# Spec — MCP Best-Practices Refresh

**Feature name**: MCP Best-Practices Refresh
**One-line summary**: Refresh Tyler's MCP client integration, examples, and docs for the MCP 2025-11-25 stable spec while preserving the existing `Agent(mcp={...})` API.

---

## Problem
Tyler's MCP docs and adapter behavior lag current MCP guidance. Remote MCP usage should present Streamable HTTP as the primary transport, `stdio` as the local process transport, and SSE only as legacy compatibility. The adapter should also preserve richer MCP tool metadata, validate configuration more defensively, serialize tool results safely, and clean up dynamically registered MCP tools so reconnects do not duplicate exposed tools.

## Goal
Tyler users can configure MCP servers through the current `Agent(mcp={...})` and `await agent.connect_mcp()` flow with updated transport framing, stricter validation, safer result handling, metadata preservation, and reliable cleanup/reconnect behavior.

## Success Criteria
- [ ] MCP config accepts only `stdio`, `streamablehttp`, and legacy `sse`, with no docs or examples claiming `websocket` support.
- [ ] Tyler validates URL schemes, list/dict option types, positive retry/timeout values, and required transport fields before connection.
- [ ] MCP tools exposed to providers use OpenAI-compatible function names while preserving original MCP names and metadata in attributes.
- [ ] MCP tool results prefer structured content, serialize non-text content into JSON-compatible values, and raise on MCP `isError` results.
- [ ] `cleanup()` removes MCP tools from exposed tools and allows reconnect without duplicate definitions.
- [ ] Docs and examples recommend `try/finally await agent.cleanup()` and describe MCP tools as privileged/untrusted unless explicitly trusted.

## User Story
As a Tyler developer, I want MCP integration that follows current MCP guidance without changing Tyler's public API, so that I can connect reviewed local and remote MCP servers safely and predictably.

## Flow / States
Happy path: a user creates `Agent(mcp={...})`, Tyler validates the config, `await agent.connect_mcp()` connects servers, registers sanitized tool names with metadata, the model calls MCP tools, and `await agent.cleanup()` disconnects and removes dynamic MCP tools.

Edge case: a user configures an invalid transport, URL, timeout, or option type. Tyler raises a clear `ValueError` at initialization rather than failing later during connection.

## UX Links
- Designs: N/A
- Prototype: N/A
- Copy/Content: MCP spec 2025-11-25, MCP transports, MCP security best practices, MCP Python SDK PyPI page

## Requirements
- Must keep `Agent(mcp={...})` and `await agent.connect_mcp()` as the public API.
- Must not add provider-native OpenAI MCP support in this pass.
- Must support only `stdio`, `streamablehttp`, and legacy `sse`.
- Must add optional config fields for connection, read, process, encoding, and tool execution timeout behavior.
- Must sanitize the full exposed Tyler MCP tool name to OpenAI-compatible function name constraints.
- Must preserve MCP server/tool metadata in tool attributes.
- Must remove dynamically registered MCP tools during cleanup.
- Must update docs, examples, and CLI config comments to current MCP transport and security positioning.

## Acceptance Criteria
- Given MCP config with HTTP transport URL using a non-HTTP scheme, when creating an `Agent`, then Tyler raises `ValueError`.
- Given MCP config with `websocket`, invalid option types, or non-positive retries/timeouts, when creating an `Agent`, then Tyler raises `ValueError`.
- Given an MCP tool with special characters or an overlong server/tool name, when it is registered, then the exposed Tyler name is OpenAI-compatible and original names are preserved in attributes.
- Given an MCP tool result with `structuredContent`, when called through Tyler, then Tyler returns that structured content.
- Given an MCP tool result with non-text content, when called through Tyler, then Tyler returns JSON-serializable dictionaries instead of object repr strings.
- Given an MCP tool result with `isError=True`, when called through Tyler, then Tyler raises a `ValueError`.
- Given an agent with MCP tools, when `cleanup()` is called and then `connect_mcp()` is called again, then the tool list and system prompt do not contain duplicate MCP tool definitions and non-MCP prompt content is preserved.

## Non-Goals
- Provider-native OpenAI MCP integration.
- MCP roots, elicitation UI, OAuth browser flows, progressive discovery runtime, or new trust/permission UI.
- Breaking secure-default changes beyond compatible validation and hardening guidance.
- Changes to A2A APIs.
