# MCP Reference

This page provides detailed reference information for Tyler's [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) integration components.

## MCPAdapter

The `MCPAdapter` class is the main interface for connecting Tyler agents to MCP servers. It handles server connections, tool discovery, and format conversion between MCP and Tyler tools.

### Constructor

```python
MCPAdapter(mcp_client: Optional[MCPClient] = None)
```

**Parameters:**
- `mcp_client`: Optional MCP client instance. If not provided, creates a new one.

### Methods

#### `async connect(name: str, transport: str, **kwargs) -> bool`

Connects to an MCP server and registers its tools with Tyler.

**Parameters:**
- `name`: Unique name for this connection
- `transport`: Transport type (`'stdio'`, `'sse'`, or `'websocket'`)
- `**kwargs`: Transport-specific arguments:
  - For `stdio`: `command` (str), `args` (List[str]), `env` (Dict[str, str])
  - For `sse`: `url` (str)
  - For `websocket`: `url` (str)

**Returns:**
- `bool`: True if connection successful and tools registered

**Example:**
```python
mcp = MCPAdapter()

# STDIO transport
connected = await mcp.connect(
    name="brave",
    transport="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"],
    env={"BRAVE_API_KEY": "your_key"}
)

# SSE transport
connected = await mcp.connect(
    name="filesystem",
    transport="sse",
    url="http://localhost:3000/sse"
)
```

#### `get_tools_for_agent(server_names: Optional[List[str]] = None) -> List[Dict[str, Any]]`

Gets Tyler-formatted tools for use with an Agent.

**Parameters:**
- `server_names`: Optional list of server names. If None, returns tools from all connected servers.

**Returns:**
- List of Tyler tool definitions ready for use with Agent

**Example:**
```python
# Get all tools
all_tools = mcp.get_tools_for_agent()

# Get tools from specific servers
brave_tools = mcp.get_tools_for_agent(["brave"])
```

#### `async disconnect(name: str) -> None`

Disconnects from a specific server and unregisters its tools.

**Parameters:**
- `name`: Name of the server to disconnect from

#### `async disconnect_all() -> None`

Disconnects from all servers and cleans up resources.

## MCPClient

The `MCPClient` class provides lower-level access to MCP protocol operations. It handles the actual communication with MCP servers.

### Constructor

```python
MCPClient()
```

### Methods

#### `async connect(name: str, transport: str, **kwargs) -> bool`

Connects to an MCP server.

**Parameters:**
- `name`: Unique name for this connection
- `transport`: Transport type (`'stdio'`, `'sse'`, or `'websocket'`)
- `**kwargs`: Transport-specific arguments

**Returns:**
- `bool`: True if connection successful

#### `get_tools(server_name: Optional[str] = None) -> List[Any]`

Gets discovered tools from one or all servers.

**Parameters:**
- `server_name`: Optional server name. If None, returns tools from all servers.

**Returns:**
- List of MCP tool objects

#### `async call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any`

Calls a tool on a specific server.

**Parameters:**
- `server_name`: Name of the server that has the tool
- `tool_name`: Name of the tool to call
- `arguments`: Tool arguments

**Returns:**
- Tool execution result

#### `async disconnect(name: str) -> None`

Disconnects from a specific server.

**Parameters:**
- `name`: Server name

#### `async disconnect_all() -> None`

Disconnects from all servers.

#### `is_connected(name: str) -> bool`

Checks if connected to a specific server.

**Parameters:**
- `name`: Server name

**Returns:**
- `bool`: True if connected

#### `list_connections() -> List[str]`

Lists all active connections.

**Returns:**
- List of server names

## Tool Naming Convention

MCP tools are automatically namespaced when converted to Tyler tools to avoid naming conflicts:

- **MCP Tool**: `search` from server `brave`
- **Tyler Tool Name**: `brave__search`

The naming pattern is: `{server_name}__{tool_name}`, with all non-alphanumeric characters replaced with underscores.

## Complete Example

```python
// ... existing code ...

from tyler import Agent, Thread, Message
from tyler.mcp import MCPAdapter

async def example_with_multiple_servers():
    # Create adapter
    mcp = MCPAdapter()
    
    # Connect to multiple servers
    servers = [
        {
            "name": "brave",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY")}
        },
        {
            "name": "filesystem",
            "transport": "sse",
            "url": "http://localhost:3000/sse"
        }
    ]
    
    connected_servers = []
    for server in servers:
        name = server.pop("name")
        transport = server.pop("transport")
        if await mcp.connect(name, transport, **server):
            connected_servers.append(name)
    
    if not connected_servers:
        print("No servers connected")
        return
    
    try:
        # Create agent with all MCP tools
        agent = Agent(
            name="MultiToolAssistant",
            model_name="gpt-4o-mini",
            tools=mcp.get_tools_for_agent()
        )
        
        # Use the agent
        thread = Thread()
        thread.add_message(Message(
            role="user",
            content="Search for recent AI news and save a summary to summary.txt"
        ))
        
        result_thread, messages = await agent.go(thread)
        
    finally:
        await mcp.disconnect_all()
``` 