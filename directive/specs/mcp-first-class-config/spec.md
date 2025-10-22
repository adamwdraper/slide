# Spec (per PR)

**Feature name**: MCP first-class configuration in Tyler (Agent and Chat CLI)
**One-line summary**: Declare and auto-connect MCP servers via config or Agent constructor; no shim files required.

---

## Problem
Users must write Python shims to connect Model Context Protocol (MCP) servers and export `TOOLS` to Tyler. This adds friction, scatters logic, and deviates from MCP client norms where servers are configured declaratively and tools are auto-exposed.

## Goal
Enable first-class, declarative MCP configuration in Tyler:
- In chat config (`tyler-chat-config.yaml`): an `mcp:` section listing servers to auto-connect on startup.
- In Python: an `Agent(mcp=...)` constructor argument that connects servers and registers tools automatically.

## Success Criteria
- [ ] Users can specify at least one MCP server in YAML, and Tyler auto-connects and exposes tools without custom shims.
- [ ] Users can instantiate `Agent(mcp=...)` with one line and get tools from the declared servers.
- [ ] Namespacing and include/exclude filters work to prevent tool overload.
- [ ] Backward compatibility: existing `tools:` and Python `MCPAdapter` flows continue to work.

## User Story
As a developer, I want to declare my MCP servers once (in config or Agent), so that I can immediately use their tools in Tyler without writing glue code.

## Flow / States
- Happy path: User declares `mcp.servers` with `name`, `transport`, `url`. On startup, Tyler connects, discovers tools, namespaces them, and exposes them to the agent.
- Edge case: Server unreachable or lists zero tools → startup continues with a warning; agent still runs with remaining tools.

## UX Links
- Docs reference for MCP server usage: https://www.mintlify.com/docs/ai/model-context-protocol#using-your-mcp-server

## Requirements
- Must support multiple servers with transports: `sse` and `websocket`; keep `stdio` for parity.
- Must support `namespace`, `include_tools`, `exclude_tools` per server.
- Must provide `connect_on_start`/`connect_on_init` behavior toggles.
- Must surface clear warnings (not fatal) when a server cannot be connected or exposes zero tools.
- Must preserve existing `tools:` semantics and `MCPAdapter` Python API.
- Must not require users to write shim files to load MCP tools.

## Acceptance Criteria
- Given a YAML config with `mcp.servers: [{ name: "wandb_docs", transport: "sse", url: "https://docs.wandb.ai/mcp" }]`, when `tyler-chat` starts, then the agent has tools named `wandb_docs__*` discovered from that server.
- Given an Agent constructed with `Agent(mcp={"connect_on_init": true, "servers": [...]})`, when created, then tools from those servers are registered and available in `go()` runs.
- Given `include_tools: ["search*"]` and `exclude_tools: ["*admin*"]`, when tools are registered, then only matching tools are exposed.
- Negative: Given an invalid URL, when starting, then a warning is logged and startup proceeds without crashing; other servers still connect.

## Non-Goals
- Full UI for managing MCP servers.
- Persistence of runtime-added servers beyond config (future enhancement).


