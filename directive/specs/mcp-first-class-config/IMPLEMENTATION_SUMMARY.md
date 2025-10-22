# Implementation Summary — MCP first-class configuration in Tyler

## Overview
This change adds first-class support for configuring Model Context Protocol (MCP) servers via:
- Agent constructor: `Agent(mcp=...)` with `connect_on_init` and a list of `servers`.
- Chat config: `mcp:` section with `connect_on_start` and `servers`, passed through to the Agent.

Tools from connected MCP servers are discovered, optionally namespaced, filtered (include/exclude), and registered automatically.

## Key Changes
- packages/tyler/tyler/models/agent.py
  - New optional `mcp: Dict[str, Any]` field.
  - During initialization, when `connect_on_init` is true, connect to all declared servers concurrently via `MCPAdapter`, then append discovered tools to `tools` before registration.
- packages/tyler/tyler/cli/chat.py
  - `load_config` now passes through `mcp:` to Agent and maps `connect_on_start` -> `connect_on_init`.
- packages/tyler/tyler/mcp/adapter.py
  - Added per-server options: `namespace`, `include_tools`, `exclude_tools`.
  - Applied glob-style include/exclude filtering and namespacing on tool registration.

## Tests Added
- packages/tyler/tests/models/test_agent_mcp.py
  - Verifies Agent(mcp=...) connects (mocked) and registers discovered tools.
  - Ensures failed connections don’t crash and add no tools.
- packages/tyler/tests/cli/test_chat_mcp_config.py
  - Verifies `mcp:` in chat config is passed through and `connect_on_start` is mapped correctly.

## Usage Examples
- Python
```python
agent = Agent(
    model_name="gpt-4.1",
    mcp={
        "connect_on_init": True,
        "servers": [
            {
                "name": "wandb_docs",
                "transport": "sse",
                "url": "https://docs.wandb.ai/mcp",
                "namespace": "wandb",
                "include_tools": [],
                "exclude_tools": []
            }
        ]
    }
)
```

- Chat config
```yaml
mcp:
  connect_on_start: true
  servers:
    - name: wandb_docs
      transport: sse
      url: "https://docs.wandb.ai/mcp"
      namespace: "wandb"
      include_tools: []
      exclude_tools: []
```

## Notes
- Non-fatal behavior on connection/list failures; logs warnings and continues.
- SSE and WebSocket supported (stdio remains available).
- Aligns with MCP best practices; reduces need for shim files.
