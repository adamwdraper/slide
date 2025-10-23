"""Example of using Tyler with MCP (Model Context Protocol) servers.

This example demonstrates the recommended way to use MCP with Tyler using
the declarative config approach. No manual adapter code needed!

For this example, we'll use the Brave Search MCP server.

Setup:
    export BRAVE_API_KEY=your_api_key_here
    python 300_mcp_basic.py
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
from tyler import Agent, Thread, Message

# Initialize weave tracing if WANDB_API_KEY is set
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    """Run the example using declarative MCP config."""
    
    # Create agent with MCP config (no manual adapter code!)
    agent = Agent(
        name="Tyler",
        model_name="gpt-4o-mini",
        mcp={
            "servers": [{
                "name": "brave",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-brave-search"],
                "env": {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "")}
            }]
        }
    )
    
    # Connect to MCP servers (fail fast if server unavailable)
    logger.info("Connecting to MCP servers...")
    try:
        await agent.connect_mcp()
        logger.info(f"Connected! Tools discovered: {len(agent._processed_tools)}")
    except Exception as e:
        logger.error(f"Failed to connect to MCP servers: {e}")
        logger.info("Make sure you have BRAVE_API_KEY set and npx is available.")
        return
    
    # Create a thread
    thread = Thread()
    
    # Add a user message
    thread.add_message(Message(
        role="user",
        content="What's the latest news about quantum computing breakthroughs?"
    ))
    
    # Process the thread with streaming
    logger.info("Processing thread with streaming...")
    async for event in agent.go(thread, stream=True):
        if event.type.name == "LLM_STREAM_CHUNK":
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type.name == "MESSAGE_CREATED":
            message = event.data.get("message")
            if message and message.role == "tool":
                print(f"\n\n[Tool: {message.name}]")
        elif event.type.name == "EXECUTION_COMPLETE":
            print("\n\n✓ Complete!")
    
    logger.info("Done!")
    
    # Note: No cleanup needed - script ends and connections close automatically


if __name__ == "__main__":
    # Check for Brave API key
    if not os.environ.get("BRAVE_API_KEY"):
        print("Error: BRAVE_API_KEY environment variable not set.")
        print("Please set it to use the Brave Search API.")
        print("Example: export BRAVE_API_KEY=your_api_key_here")
        sys.exit(1)
        
    asyncio.run(main())
