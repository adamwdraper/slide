# MCP Tools

Tyler provides support for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction), allowing seamless integration with MCP-compatible tools and services.

## Overview

[MCP](https://modelcontextprotocol.io/introduction) is an open standard for communication between AI agents and tools. Tyler's MCP integration allows you to:

- Connect to existing MCP servers via various transport protocols (STDIO, SSE, WebSocket)
- Automatically discover available tools from MCP servers
- Use MCP tools as native Tyler tools with automatic format conversion
- Connect to multiple MCP servers simultaneously

## Key Changes

:::note
Tyler no longer manages MCP server lifecycle. Servers should be started and managed externally (e.g., via Docker, systemd, or manually). This provides better security, flexibility, and follows industry best practices.
:::

## Quick Start

### 1. Start Your MCP Server

First, start your MCP server externally. For example, to use the Brave Search server:

```bash
# Start the server manually
BRAVE_API_KEY=your_key npx -y @modelcontextprotocol/server-brave-search
```

### 2. Connect from Tyler

```python
from tyler.mcp import MCPAdapter

# Create MCP adapter
mcp = MCPAdapter()

# Connect to the running server
await mcp.connect(
    name="brave",
    transport="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"],
    env={"BRAVE_API_KEY": "your_key"}
)

# Get tools for your agent
tools = mcp.get_tools_for_agent()
```

## Connection Methods

### STDIO Transport

For servers that communicate via standard input/output:

```python
await mcp.connect(
    name="filesystem",
    transport="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"]
)
```

### SSE Transport (HTTP)

For servers running on HTTP with Server-Sent Events:

```python
# Start server first: npx -y @modelcontextprotocol/server-filesystem --port 3000
await mcp.connect(
    name="filesystem",
    transport="sse",
    url="http://localhost:3000/sse"
)
```

### WebSocket Transport

For WebSocket-based servers:

```python
await mcp.connect(
    name="myserver",
    transport="websocket",
    url="ws://localhost:8080"
)
```

## Complete Example

Here's a full example using MCP tools with Tyler:

```python
"""Example of using Tyler with the Brave Search MCP server."""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import asyncio
import os
import sys
import weave
from typing import List, Dict, Any

from tyler import Agent, Thread, Message
from tyler.mcp import MCPAdapter

async def main():
    # Create MCP adapter
    mcp = MCPAdapter()
    
    # Connect to a Brave Search server (already running)
    connected = await mcp.connect(
        name="brave",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY")}
    )
    
    if not connected:
        print("Failed to connect to MCP server")
        return
    
    try:
        # Get MCP tools for the agent
        mcp_tools = mcp.get_tools_for_agent()
        
        # Create agent with MCP tools
        agent = Agent(
            name="SearchAssistant",
            model_name="gpt-4o-mini",
            tools=mcp_tools
        )
        
        # Use the agent
        thread = Thread()
        thread.add_message(Message(
            role="user",
            content="What's the latest news about AI?"
        ))
        
        # Process with streaming
        async for update in agent.go_stream(thread):
            if update.type.name == "CONTENT_CHUNK":
                print(update.data, end="", flush=True)
    
    finally:
        # Always disconnect when done
        await mcp.disconnect_all()

if __name__ == "__main__":
    asyncio.run(main())
```

## Multiple Servers

You can connect to multiple MCP servers simultaneously:

```python
from tyler.mcp import MCPAdapter

mcp = MCPAdapter()

# Connect to multiple servers
servers = [
    {"name": "filesystem", "transport": "sse", "url": "http://localhost:3000/sse"},
    {"name": "github", "transport": "stdio", "command": "mcp-server-github", "args": []},
    {"name": "postgres", "transport": "stdio", "command": "mcp-server-postgres", "args": ["postgresql://..."]}
]

for server in servers:
    name = server.pop("name")
    transport = server.pop("transport")
    await mcp.connect(name, transport, **server)

# Get tools from specific servers
fs_tools = mcp.get_tools_for_agent(["filesystem"])
all_tools = mcp.get_tools_for_agent()  # All tools from all servers
```

## Tool Naming

MCP tools are automatically namespaced to avoid conflicts:

- Original tool: `search` from server `brave`
- Tyler tool name: `brave__search`

This ensures tools from different servers don't conflict.

## API Reference

### MCPAdapter

The main interface for connecting to MCP servers.

#### Methods

- `connect(name: str, transport: str, **kwargs) -> bool`: Connect to an MCP server
- `get_tools_for_agent(server_names: Optional[List[str]] = None) -> List[Dict]`: Get Tyler-formatted tools
- `disconnect(name: str)`: Disconnect from a specific server
- `disconnect_all()`: Disconnect from all servers

### MCPClient

Lower-level client for direct MCP communication (advanced usage).

## Best Practices

1. **Server Management**: Start MCP servers externally for better control and security
2. **Error Handling**: Always check connection status and handle failures gracefully
3. **Cleanup**: Always disconnect from servers when done
4. **Tool Discovery**: Tools are discovered automatically upon connection

## Available MCP Servers

Popular MCP servers you can use with Tyler:

- `@modelcontextprotocol/server-brave-search`: Web search via Brave
- `@modelcontextprotocol/server-filesystem`: File system access
- `@modelcontextprotocol/server-github`: GitHub API access
- `@modelcontextprotocol/server-postgres`: PostgreSQL database access
- `@modelcontextprotocol/server-slack`: Slack integration

See the [MCP servers repository](https://github.com/modelcontextprotocol/servers) for more options. 