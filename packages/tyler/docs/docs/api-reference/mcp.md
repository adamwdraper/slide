# MCP Reference

This page provides detailed reference information for Tyler's [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) integration components.

## MCPService

The `MCPService` class manages connections to MCP servers, discovers tools, and handles tool execution.

### Methods

#### `async initialize(server_configs: List[Dict[str, Any]]) -> None`

Initializes the MCP service with the provided server configurations.

**Parameters:**
- `server_configs`: List of server configuration dictionaries

**Example:**
```python
await mcp_service.initialize([
    {
        "name": "brave-search",
        "transport": "stdio",
        "command": ["python", "-m", "brave_search.server"],
        "auto_start": True
    }
])
```

#### `async _connect_to_server(name: str, config: Dict[str, Any]) -> Optional[ClientSession]`

Connects to an MCP server using the specified configuration.

**Parameters:**
- `name`: Server name
- `config`: Server configuration dictionary

**Returns:**
- `ClientSession` object if connection is successful, `None` otherwise

#### `async _discover_tools(name: str, session: ClientSession) -> None`

Discovers available tools from an MCP server.

**Parameters:**
- `name`: Server name
- `session`: MCP client session

#### `_convert_mcp_tool_to_tyler_tool(server_name: str, tool, session: ClientSession) -> Dict`

Converts an MCP tool definition to a Tyler-compatible tool definition.

**Parameters:**
- `server_name`: Server name
- `tool`: MCP tool definition
- `session`: MCP client session

**Returns:**
- Tyler-compatible tool definition dictionary

#### `_create_tool_implementation(server_name: str, tool_name: str)`

Creates a function that implements an MCP tool.

**Parameters:**
- `server_name`: Server name
- `tool_name`: Tool name

**Returns:**
- Function that executes the MCP tool

#### `get_tools_for_agent(server_names=None)`

Gets all available tools for use with a Tyler agent.

**Parameters:**
- `server_names`: Optional list of server names to filter tools by

**Returns:**
- List of Tyler-compatible tool definitions

#### `async cleanup()`

Cleans up all MCP server connections.

## MCPServerManager

The `MCPServerManager` class handles starting, stopping, and managing MCP server processes.

### Methods

#### `async start_server(name: str, config: Dict[str, Any]) -> bool`

Starts an MCP server with the specified configuration.

**Parameters:**
- `name`: Server name
- `config`: Server configuration dictionary

**Returns:**
- `True` if server started successfully, `False` otherwise

**Example:**
```python
success = await server_manager.start_server("brave-search", {
    "transport": "stdio",
    "command": ["python", "-m", "brave_search.server"],
    "auto_start": True
})
```

#### `async stop_server(name: str) -> bool`

Stops a running MCP server.

**Parameters:**
- `name`: Server name

**Returns:**
- `True` if server stopped successfully, `False` otherwise

**Example:**
```python
success = await server_manager.stop_server("brave-search")
```

#### `async stop_all_servers() -> None`

Stops all running MCP servers.

**Example:**
```python
await server_manager.stop_all_servers()
```

## Utility Functions

### `async initialize_mcp_service(server_configs: List[Dict[str, Any]]) -> MCPService`

Initializes and returns an MCPService instance.

**Parameters:**
- `server_configs`: List of server configuration dictionaries

**Returns:**
- Initialized `MCPService` instance

**Example:**
```python
mcp_service = await initialize_mcp_service([
    {
        "name": "brave-search",
        "transport": "stdio",
        "command": ["python", "-m", "brave_search.server"],
        "auto_start": True
    }
])
```

### `async cleanup_mcp_service(mcp_service: MCPService) -> None`

Cleans up an MCPService instance.

**Parameters:**
- `mcp_service`: MCPService instance to clean up

**Example:**
```python
await cleanup_mcp_service(mcp_service)
```

## Server Configuration

MCP servers can be configured with the following options:

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| `name` | Unique identifier for the server | Yes | - |
| `transport` | Transport protocol: `stdio`, `sse`, or `websocket` | Yes | - |
| `command` | Command to start the server (for `stdio` transport with `auto_start: true`) | For `stdio` with `auto_start: true` | - |
| `auto_start` | Whether Tyler should automatically start and manage the server | No | `False` |
| `url` | URL for connecting to the server (for `sse` and `websocket` transports) | For `sse` and `websocket` | - |
| `headers` | Optional HTTP headers for connection (for `sse` and `websocket` transports) | No | `{}` | 