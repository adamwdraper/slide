"""Example of using Tyler with the Brave Search MCP server.

This example demonstrates how to use Tyler with an MCP server.
The server should be started separately before running this example.

To start the Brave Search server:
    BRAVE_API_KEY=your_key npx -y @modelcontextprotocol/server-brave-search

Then run this example.
"""
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

# Add the parent directory to the path so we can import the example utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize weave tracing if WANDB_API_KEY is set
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

async def main():
    """Run the example."""
    # Create MCP adapter
    mcp = MCPAdapter()
    
    logger.info("Connecting to Brave Search MCP server...")
    
    # Connect to the Brave Search server running on stdio
    # The server should already be running with:
    # BRAVE_API_KEY=xxx npx -y @modelcontextprotocol/server-brave-search
    connected = await mcp.connect(
        name="brave",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "")}
    )
    
    if not connected:
        logger.error("Failed to connect to Brave Search MCP server.")
        logger.info("Make sure you have BRAVE_API_KEY set and the server is accessible.")
        return
    
    try:
        # Get the MCP tools for the agent
        mcp_tools = mcp.get_tools_for_agent(["brave"])
        
        if not mcp_tools:
            logger.error("No tools discovered from the Brave Search MCP server.")
            return
            
        logger.info(f"Discovered {len(mcp_tools)} tools from the Brave Search MCP server.")
        
        # Create an agent with the MCP tools
        agent = Agent(
            name="Tyler",
            model_name="gpt-4o-mini",
            tools=mcp_tools
        )
        
        # Create a thread
        thread = Thread()
        
        # Add a user message
        thread.add_message(Message(
            role="user",
            content="What's the latest news about quantum computing breakthroughs?"
        ))
        
        # Process the thread with streaming
        logger.info("Processing thread with streaming...")
        async for update in agent.go_stream(thread):
            if update.type.name == "CONTENT_CHUNK":
                print(update.data, end="", flush=True)
            elif update.type.name == "TOOL_MESSAGE":
                print(f"\n[Tool execution: {update.data.name}]\n")
            elif update.type.name == "COMPLETE":
                print("\n\nProcessing complete!")
                
    finally:
        # Clean up
        logger.info("Disconnecting from MCP server...")
        await mcp.disconnect_all()


if __name__ == "__main__":
    # Check for Brave API key
    if not os.environ.get("BRAVE_API_KEY"):
        print("Error: BRAVE_API_KEY environment variable not set.")
        print("Please set it to use the Brave Search API.")
        print("Example: export BRAVE_API_KEY=your_api_key_here")
        sys.exit(1)
        
    asyncio.run(main()) 