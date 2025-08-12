"""Example of connecting Tyler to an already-running MCP server.

This example shows how to connect to MCP servers that are already running,
such as servers started via Docker, systemd, or other process managers.
"""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import os
import weave
from tyler import Agent, Thread, Message
from tyler.mcp import MCPAdapter

# Initialize weave tracing if available
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}")


async def example_filesystem_server():
    """Example: Connect to a filesystem MCP server running on HTTP."""
    # Skip MCP server connections during tests
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping MCP server connection during tests")
        return None
        
    mcp = MCPAdapter()
    
    # Connect to a filesystem server running on HTTP
    # Start it first with: npx -y @modelcontextprotocol/server-filesystem --port 3000 /path/to/files
    connected = await mcp.connect(
        name="filesystem",
        transport="sse",  # Server-Sent Events over HTTP
        url="http://localhost:3000/sse"
    )
    
    if not connected:
        logger.error("Could not connect to filesystem server on http://localhost:3000")
        logger.info("Start it with: npx -y @modelcontextprotocol/server-filesystem --port 3000 /path/to/files")
        return None
        
    return mcp


async def example_postgres_server():
    """Example: Connect to a PostgreSQL MCP server."""
    # Skip MCP server connections during tests
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping MCP server connection during tests")
        return None
        
    mcp = MCPAdapter()
    
    # Connect to a PostgreSQL server
    # This assumes you have a PostgreSQL MCP server running
    connected = await mcp.connect(
        name="postgres",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/dbname"]
    )
    
    if not connected:
        logger.error("Could not connect to PostgreSQL MCP server")
        return None
        
    return mcp


async def example_multiple_servers():
    """Example: Connect to multiple MCP servers."""
    # Skip MCP server connections during tests
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping MCP server connection during tests")
        return None
        
    mcp = MCPAdapter()
    
    # Connect to multiple servers
    servers = [
        {
            "name": "filesystem",
            "transport": "sse",
            "url": "http://localhost:3000/sse"
        },
        {
            "name": "github",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")}
        }
    ]
    
    connected_servers = []
    for server in servers:
        name = server.pop("name")
        transport = server.pop("transport")
        if await mcp.connect(name, transport, **server):
            connected_servers.append(name)
            logger.info(f"Connected to {name}")
        else:
            logger.warning(f"Failed to connect to {name}")
    
    if not connected_servers:
        logger.error("No servers connected")
        return None
        
    return mcp, connected_servers


async def main():
    """Run examples of connecting to existing MCP servers."""
    
    # Example 1: Simple filesystem server
    logger.info("\n=== Example 1: Filesystem Server ===")
    mcp = await example_filesystem_server()
    
    if mcp:
        tools = mcp.get_tools_for_agent()
        logger.info(f"Available tools: {[t['definition']['function']['name'] for t in tools]}")
        
        # Create an agent with filesystem tools
        agent = Agent(
            name="FileAssistant",
            model_name="gpt-4o-mini",
            tools=tools
        )
        
        # Use the agent
        thread = Thread()
        thread.add_message(Message(
            role="user",
            content="List the files in the current directory"
        ))
        
        result = await agent.go(thread)
        print("\nAgent response:")
        print(result.content)
        
        # Show execution details
        print(f"\nExecution time: {result.execution.duration_ms:.2f}ms")
        if result.execution.tool_calls:
            print(f"Tools used: {len(result.execution.tool_calls)}")
        
        await mcp.disconnect_all()
    
    # Example 2: Multiple servers
    logger.info("\n=== Example 2: Multiple Servers ===")
    result = await example_multiple_servers()
    
    if result:
        mcp, connected = result
        
        # Get tools from specific servers
        fs_tools = mcp.get_tools_for_agent(["filesystem"])
        github_tools = mcp.get_tools_for_agent(["github"])
        
        logger.info(f"Filesystem tools: {len(fs_tools)}")
        logger.info(f"GitHub tools: {len(github_tools)}")
        
        # Create agent with all tools
        agent = Agent(
            name="MultiToolAssistant",
            model_name="gpt-4o-mini",
            tools=mcp.get_tools_for_agent()  # All tools from all servers
        )
        
        # Clean up
        await mcp.disconnect_all()


if __name__ == "__main__":
    asyncio.run(main()) 