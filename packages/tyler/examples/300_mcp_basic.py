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
    # Create an agent that connects to the Brave Search MCP server on init
    # The server should already be running with:
    # BRAVE_API_KEY=xxx npx -y @modelcontextprotocol/server-brave-search
    agent = Agent(
        name="Tyler",
        model_name="gpt-4o-mini",
        mcp={
            "connect_on_init": True,
            "servers": [
                {
                    "name": "brave",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
                    "env": {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "")}
                }
            ]
        }
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
    async for event in agent.go(thread, stream=True):
        if event.type.name == "LLM_STREAM_CHUNK":
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type.name == "MESSAGE_CREATED":
            message = event.data.get("message")
            if message and message.role == "tool":
                print(f"\n[Tool execution: {message.name}]\n")
        elif event.type.name == "EXECUTION_COMPLETE":
            print("\n\nProcessing complete!")


if __name__ == "__main__":
    # Check for Brave API key
    if not os.environ.get("BRAVE_API_KEY"):
        print("Error: BRAVE_API_KEY environment variable not set.")
        print("Please set it to use the Brave Search API.")
        print("Example: export BRAVE_API_KEY=your_api_key_here")
        sys.exit(1)
        
    asyncio.run(main()) 