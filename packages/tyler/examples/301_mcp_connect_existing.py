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

# Initialize weave tracing if available
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}")


async def example_filesystem_agent():
    """Example: Create an Agent that connects to a filesystem MCP server via SSE."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping MCP server connection during tests")
        return None
    
    agent = Agent(
        name="FileAssistant",
        model_name="gpt-4o-mini",
        mcp={
            "connect_on_init": True,
            "servers": [
                {"name": "filesystem", "transport": "sse", "url": "http://localhost:3000/sse"}
            ]
        }
    )
    return agent


async def example_postgres_agent():
    """Example: Create an Agent that connects to a PostgreSQL MCP server via stdio."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping MCP server connection during tests")
        return None
    
    agent = Agent(
        name="PostgresAssistant",
        model_name="gpt-4o-mini",
        mcp={
            "connect_on_init": True,
            "servers": [
                {
                    "name": "postgres",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/dbname"]
                }
            ]
        }
    )
    return agent


async def example_multiple_agents():
    """Example: Create Agents that connect to multiple MCP servers."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("Skipping MCP server connection during tests")
        return None
    
    agents = []
    # Filesystem-backed agent
    agents.append(Agent(
        name="FSAssistant",
        model_name="gpt-4o-mini",
        mcp={
            "connect_on_init": True,
            "servers": [{"name": "filesystem", "transport": "sse", "url": "http://localhost:3000/sse"}]
        }
    ))
    # GitHub-backed agent (requires token)
    agents.append(Agent(
        name="GitHubAssistant",
        model_name="gpt-4o-mini",
        mcp={
            "connect_on_init": True,
            "servers": [
                {
                    "name": "github",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")}
                }
            ]
        }
    ))
    return agents


async def main():
    """Run examples of connecting to existing MCP servers."""
    
    # Example 1: Simple filesystem server
    logger.info("\n=== Example 1: Filesystem Server (via Agent.mcp) ===")
    agent_fs = await example_filesystem_agent()
    if agent_fs:
        thread = Thread()
        thread.add_message(Message(role="user", content="List the files in the current directory"))
        result = await agent_fs.go(thread)
        print("\nAgent response:")
        print(result.content)
    
    # Example 2: Multiple servers
    logger.info("\n=== Example 2: Multiple Servers (via Agent.mcp) ===")
    agents = await example_multiple_agents()
    if agents:
        logger.info(f"Created {len(agents)} agents with different MCP servers")


if __name__ == "__main__":
    asyncio.run(main()) 