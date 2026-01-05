"""Basic MCP (Model Context Protocol) example with Tyler.

This example shows the recommended way to connect Tyler to MCP servers
using declarative configuration - no manual adapter code needed!

We use the Mintlify documentation server as the primary example because
it works immediately without any API keys or setup.

Run:
    python 300_mcp_basic.py
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import os
import weave
from tyler import Agent, Thread, Message

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
    except Exception:
        pass


async def main():
    """Basic MCP example using Mintlify documentation server."""
    
    print("=" * 70)
    print("Tyler MCP Basic Example: Search Slide Documentation")
    print("=" * 70)
    print("\nThis example connects to the Slide documentation via MCP.")
    print("No API keys or setup required!\n")
    
    # Create agent with MCP config - declarative, no boilerplate!
    agent = Agent(
        name="DocsBot",
        model_name="gpt-4o-mini",
        purpose="To help users find information in Slide documentation",
        mcp={
            "servers": [{
                "name": "docs",
                "transport": "streamablehttp",  # Mintlify uses streamablehttp
                "url": "https://slide.mintlify.app/mcp",
                "fail_silent": False  # Fail fast if server is down
            }]
        }
    )
    
    # Connect to MCP servers
    print("Connecting to MCP server...")
    try:
        await agent.connect_mcp()
        print(f"✓ Connected! Tools available: {len(agent._processed_tools)}")
        
        # Show MCP tools
        mcp_tools = [t["function"]["name"] for t in agent._processed_tools if "docs_" in t["function"]["name"]]
        print(f"  MCP tools: {mcp_tools}\n")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return
    
    # Create a thread with a question
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="How do I create my first Tyler agent? Give me a quick example."
    ))
    
    # Process with streaming
    print("💬 User: How do I create my first Tyler agent? Give me a quick example.")
    print("\n🤖 DocsBot: ", end="", flush=True)
    
    async for event in agent.stream(thread):
        if event.type.name == "LLM_STREAM_CHUNK":
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type.name == "TOOL_SELECTED":
            tool_name = event.data.get("tool_name")
            print(f"\n\n  [Using tool: {tool_name}]", flush=True)
            print("\n🤖 DocsBot: ", end="", flush=True)
        elif event.type.name == "EXECUTION_COMPLETE":
            print("\n\n✓ Complete!")
    
    # Cleanup MCP connections
    await agent.cleanup()
    
    print("\n" + "=" * 70)
    print("Example complete!")
    print("\nTry other MCP servers:")
    print("  - Brave Search (requires API key)")
    print("  - GitHub (requires token)")
    print("  - File System")
    print("  - See 301_mcp_advanced.py for examples")
    print("=" * 70 + "\n")


# Alternative: Brave Search example (requires API key)
async def brave_search_example():
    """Alternative example using Brave Search MCP server.
    
    Requires: export BRAVE_API_KEY=your_api_key_here
    """
    if not os.environ.get("BRAVE_API_KEY"):
        print("Skipping Brave Search example - BRAVE_API_KEY not set")
        return
    
    agent = Agent(
        name="Tyler",
        model_name="gpt-4o-mini",
        mcp={
            "servers": [{
                "name": "brave",
                "transport": "stdio",  # Brave uses stdio
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-brave-search"],
                "env": {"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY")}
            }]
        }
    )
    
    await agent.connect_mcp()
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What's the latest news about AI?"
    ))
    
    result = await agent.run(thread)
    print(f"\nBrave Search Response:\n{result.content}")
    
    await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
    
    # Uncomment to try Brave Search (requires API key):
    # asyncio.run(brave_search_example())
