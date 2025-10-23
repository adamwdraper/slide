# Spec: First-Class MCP Configuration Support

**Feature name**: MCP Config  
**One-line summary**: Add declarative MCP server configuration to Tyler Agent and tyler-chat CLI, eliminating custom glue code.

---

## Problem

Currently, using MCP (Model Context Protocol) servers with Tyler requires:
1. **Manual adapter setup**: Developers write boilerplate to instantiate `MCPAdapter`, connect servers, get tools, pass to Agent
2. **No CLI support**: tyler-chat users cannot connect to MCP servers without writing custom tool files
3. **Poor discoverability**: MCP is documented but not a first-class config option, making it feel like an advanced/experimental feature

This creates friction for users who want to connect Tyler to documentation sources (e.g., Mintlify MCP servers like `https://docs.wandb.ai/mcp`), databases, filesystems, or other MCP-enabled services.

## Goal

Make MCP servers a first-class, declarative configuration option in both:
- **tyler-chat CLI**: YAML config with `mcp.servers` section
- **Tyler Agent Python API**: `mcp` parameter accepting server definitions

When configured, Tyler automatically connects, discovers tools, namespaces them safely, and merges into the agent's tool set—no custom code required.

## Success Criteria

- [ ] Users can add MCP servers to `tyler-chat-config.yaml` and immediately use discovered tools in chat sessions
- [ ] Python Agent users can pass `mcp={...}` config and get a ready-to-use agent with MCP tools
- [ ] Zero custom "glue" Python files needed for common MCP use cases (docs, APIs)
- [ ] Tool naming is predictable and collision-safe via namespacing

## User Story

**As a** Tyler user wanting to connect to W&B documentation via Mintlify MCP,  
**I want** to add a simple YAML config block or Python dict,  
**So that** my agent can search docs and call W&B APIs without writing adapter/connection code.

## Flow / States

### Happy Path (CLI)
1. User adds minimal `mcp.servers` block to `tyler-chat-config.yaml`:
   ```yaml
   mcp:
     servers:
       - name: mintlify
         transport: sse
         url: https://docs.wandb.ai/mcp
   ```
2. User runs `tyler chat`
3. Tyler connects to MCP server on startup, discovers tools (e.g., `search`)
4. ALL discovered tools are registered automatically (no filters needed)
5. Tools appear namespaced (`mintlify_search`) in agent's tool set
6. User asks "search docs for W&B Weave integration"
7. Agent calls `mintlify_search` tool successfully

### Edge Case (Connection Failure)
1. User configures MCP server with wrong URL or offline server
2. Tyler logs warning: "Failed to connect to MCP server 'mintlify': Connection refused"
3. If `fail_silent: true` (default), Tyler continues with other tools
4. If `fail_silent: false`, Tyler exits with error

## UX Links

- Reference: [Mintlify MCP Documentation](https://www.mintlify.com/docs/ai/model-context-protocol#using-your-mcp-server)
- Example MCP servers: https://github.com/modelcontextprotocol/servers
- Tyler MCP examples: `packages/tyler/examples/300_mcp_basic.py`, `301_mcp_connect_existing.py`

## Requirements

### Must
- Support all three transports: `stdio`, `sse`, `websocket`
- Support environment variable substitution in URLs, headers, auth (already in CLI config loader)
- Namespace tools by server name to avoid collisions (e.g., `servername_toolname`)
- Register ALL discovered tools by default (no filtering unless explicitly configured)
- Allow optional tool filtering (`include_tools`, `exclude_tools`)
- Allow custom namespace prefix override
- Work in both `tyler chat` CLI and Python `Agent` API
- Fail gracefully if MCP server is unavailable (configurable via `fail_silent`)
- Log clear messages when connecting, discovering tools, or failing
- Position config approach as the primary/recommended API in docs and examples

### Must Not
- Require users to write custom Python files for common MCP use cases
- Break existing `MCPAdapter` API (this is additive, but low-level escape hatch only)
- Feature `MCPAdapter` in examples or primary documentation (config approach only)
- Auto-connect without explicit config (opt-in only)
- Expose raw MCP credentials in logs

## Acceptance Criteria

### CLI (tyler-chat)

**Given** a `tyler-chat-config.yaml` with this block:
```yaml
mcp:
  servers:
    - name: mintlify
      transport: sse
      url: https://docs.wandb.ai/mcp
```

**When** user runs `tyler chat` and asks "search docs for weave"

**Then**:
- Tyler connects to the MCP server on startup
- Logs show "Connected to MCP server 'mintlify'"
- Discovered tools are namespaced as `mintlify_search`, etc.
- Agent successfully calls the tool and returns results
- No custom Python files are required

---

**Given** a minimal MCP server config with no tool filters:
```yaml
mcp:
  servers:
    - name: mintlify
      transport: sse
      url: https://docs.wandb.ai/mcp
```

**When** Tyler connects and discovers 3 tools from the server

**Then**:
- ALL 3 discovered tools are registered automatically
- No explicit `include_tools` or `exclude_tools` needed
- Tools are namespaced as `mintlify_tool1`, `mintlify_tool2`, `mintlify_tool3`

---

**Given** an MCP server with multiple tools and this config:
```yaml
mcp:
  servers:
    - name: filesystem
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      include_tools: ["read_file", "list_directory"]
      exclude_tools: ["write_file"]
```

**When** agent's available tools are listed

**Then**:
- Only `filesystem_read_file` and `filesystem_list_directory` appear
- `filesystem_write_file` is NOT registered

---

**Given** an MCP server that requires auth via headers:
```yaml
mcp:
  servers:
    - name: api
      transport: websocket
      url: wss://api.example.com/mcp
      headers:
        Authorization: "Bearer ${MCP_TOKEN}"
```

**When** `MCP_TOKEN` env var is set and agent connects

**Then**:
- Tyler substitutes `${MCP_TOKEN}` with actual value
- Connection succeeds with proper auth headers
- Token is NOT logged in plaintext

---

**Given** an unreachable MCP server with `fail_silent: true`:
```yaml
mcp:
  servers:
    - name: offline
      transport: sse
      url: https://nonexistent.example.com/mcp
      fail_silent: true
```

**When** `tyler chat` starts

**Then**:
- Tyler logs warning: "Failed to connect to MCP server 'offline'"
- CLI continues and agent is usable with other tools
- No crash or stack trace

---

**Given** an unreachable MCP server with `fail_silent: false`

**When** `tyler chat` starts

**Then**:
- Tyler exits with error code 1
- Error message clearly states which server failed

### Python API

**Given** this Python code:
```python
from tyler import Agent

agent = Agent(
    name="Tyler",
    model_name="gpt-4.1",
    tools=["web"],
    mcp={
        "servers": [{
            "name": "mintlify",
            "transport": "sse",
            "url": "https://docs.wandb.ai/mcp"
        }]
    }
)

# First use connects to MCP lazily
result = await agent.go(thread)
```

**When** agent is used

**Then**:
- Agent is created normally (sync, no async needed)
- On first `agent.go()` call, MCP servers connect lazily
- All discovered tools are registered and available
- Subsequent calls reuse existing connections

---

**Given** namespace prefix override:
```python
agent = Agent(
    model_name="gpt-4.1",
    mcp={
        "servers": [{
            "name": "mintlify",
            "transport": "sse",
            "url": "https://docs.wandb.ai/mcp",
            "prefix": "docs"
        }]
    }
)
```

**When** agent is used and tools are registered

**Then**:
- Tool names use `docs_` prefix instead of `mintlify_`
- Example: `docs_search` instead of `mintlify_search`

---

**Given** cleanup is needed:
```python
agent = Agent(mcp={...})
# ... use agent ...
await agent.cleanup()
```

**When** cleanup is called

**Then**:
- All MCP connections are closed cleanly
- Resources are freed

### Negative Cases

**Given** invalid transport type:
```yaml
mcp:
  servers:
    - name: bad
      transport: http  # invalid, should be 'sse'
      url: https://example.com
```

**When** config is loaded

**Then**:
- Tyler raises `ValueError: Invalid transport 'http'. Must be one of: stdio, sse, websocket`

---

**Given** missing required field:
```yaml
mcp:
  servers:
    - name: incomplete
      transport: sse
      # missing 'url'
```

**When** config is loaded

**Then**:
- Tyler raises `ValueError: MCP server 'incomplete' with transport 'sse' requires 'url' field`

## Non-Goals

- Building a generic MCP server (Tyler is an MCP client only)
- Auto-discovery of MCP servers (users must explicitly configure)
- Migration tool for existing `MCPAdapter` usage (existing code continues to work)
- Server lifecycle management beyond connect/disconnect (e.g., monitoring, restarts)
- Support for MCP protocol versions other than what the underlying `mcp` package supports
- Custom tool name transformations beyond prefix override (users can fork if needed)

