"""Example of connecting to multiple MCP servers using declarative config.

This example shows how to:
1. Connect to multiple MCP servers simultaneously
2. Use custom namespace prefixes
3. Filter tools with include/exclude
4. Handle connection failures gracefully

No manual adapter code - just config!
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

# Initialize weave tracing if available
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}")


async def example_multiple_servers():
    """Example: Connect to multiple MCP servers with advanced config."""
    
    agent = Agent(
        name="Tyler",
        model_name="gpt-4o-mini",
        purpose="To help with filesystem operations and GitHub queries",
        mcp={
            "servers": [
                # Filesystem server with tool filtering
                {
                    "name": "filesystem",
                    "transport": "sse",
                    "url": "http://localhost:3000/sse",
                    "exclude_tools": ["write_file", "delete_file"],  # Read-only
                    "fail_silent": True  # Continue if unavailable
                },
                # GitHub server with custom prefix
                {
                    "name": "github",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
                    "prefix": "gh",  # Tools will be gh_search_repos, gh_create_issue, etc.
                    "fail_silent": True
                }
            ]
        }
    )
    
    # Connect to all servers
    logger.info("Connecting to MCP servers...")
    await agent.connect_mcp()
    
    # Show connected tools
    logger.info(f"Agent has {len(agent._processed_tools)} tools available")
    mcp_tools = [
        t["function"]["name"]
        for t in agent._processed_tools
        if any(prefix in t["function"]["name"] for prefix in ["filesystem_", "gh_"])
    ]
    logger.info(f"MCP tools: {mcp_tools}")
    
    # Use the agent
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="List files in the current directory"
    ))
    
    result = await agent.go(thread)
    print(f"\nResponse: {result.content}\n")
    
    # Cleanup (optional for scripts, but shown here for demonstration)
    # Useful in long-running apps or when creating/destroying many agents
    await agent.cleanup()


async def example_single_server_with_auth():
    """Example: Single server with authentication headers."""
    
    agent = Agent(
        name="Tyler",
        model_name="gpt-4o-mini",
        mcp={
            "servers": [{
                "name": "api",
                "transport": "sse",
                "url": "https://api.example.com/mcp",
                "headers": {
                    # Use environment variables for secrets!
                    "Authorization": f"Bearer {os.environ.get('API_TOKEN', '')}"
                },
                "include_tools": ["search", "query"],  # Whitelist specific tools
                "prefix": "api"
            }]
        }
    )
    
    # This example would fail without a real API server
    # Just showing the pattern
    print("\nExample config with auth (not connecting - no real server):")
    print(f"  Server: {agent.mcp['servers'][0]['name']}")
    print(f"  Transport: {agent.mcp['servers'][0]['transport']}")
    print(f"  Tools filter: {agent.mcp['servers'][0]['include_tools']}")


async def main():
    """Run the examples."""
    print("=" * 60)
    print("MCP Multi-Server Example")
    print("=" * 60)
    
    # Check prerequisites
    if not os.environ.get("GITHUB_TOKEN"):
        print("\nNote: GITHUB_TOKEN not set - GitHub server will be skipped")
    
    # Run examples
    try:
        await example_multiple_servers()
    except Exception as e:
        logger.error(f"Multi-server example failed: {e}")
        print(f"\n✗ Error: {e}")
        print("\nTo run this example:")
        print("  1. Start filesystem server: npx -y @modelcontextprotocol/server-filesystem --port 3000 /tmp")
        print("  2. (Optional) Set GITHUB_TOKEN for GitHub integration")
        print("  3. Run this script")
    
    print("\n" + "=" * 60)
    await example_single_server_with_auth()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
