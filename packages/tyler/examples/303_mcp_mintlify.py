"""Example of using Tyler with a Mintlify MCP server (W&B docs).

This is a real-world example showing how to connect Tyler to W&B documentation
via the Mintlify MCP server. Perfect copy-paste starter for your own use!

No API key needed - Mintlify MCP servers are public for documentation search.

Run:
    python 303_mcp_mintlify.py
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import weave
import os
from tyler import Agent, Thread, Message

# Initialize weave tracing if available
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-mcp-example")
except Exception:
    pass


async def main():
    """Search W&B documentation using Mintlify MCP server."""
    
    print("=" * 70)
    print("Tyler + Mintlify MCP Example: Search W&B Documentation")
    print("=" * 70)
    
    # Create agent with W&B docs MCP server
    try:
        agent = Agent(
            name="DocsBot",
            model_name="gpt-4o-mini",
            purpose="To help users find information in W&B documentation",
            tools=["web"],  # Can combine MCP tools with built-in tools!
            mcp={
                "servers": [{
                    "name": "wandb_docs",
                    "transport": "sse",
                    "url": "https://docs.wandb.ai/mcp",
                    "fail_silent": False  # Fail fast if docs server is down
                }]
            }
        )
        print("✓ Agent created (config schema validated)")
    except ValueError as e:
        print(f"✗ Config validation failed: {e}")
        return
    
    # Connect to MCP servers (fail fast!)
    print("\n🔗 Connecting to W&B documentation server...")
    print("   URL: https://docs.wandb.ai/mcp")
    
    try:
        await agent.connect_mcp()
        print("✓ Connected successfully!")
        
        # Show what tools are available
        mcp_tools = [
            t["function"]["name"]
            for t in agent._processed_tools
            if "wandb_docs_" in t["function"]["name"]
        ]
        print(f"  MCP tools available: {mcp_tools}")
        
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print("\nNote: fail_silent=False means connection errors are raised.")
        print("The server may be temporarily unavailable or the URL changed.")
        return
    
    # Create a thread with a documentation question
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="How do I use Weave for tracing my LLM applications? Give me a quick example."
    ))
    
    # Process with streaming
    print("\n💬 User: How do I use Weave for tracing my LLM applications? Give me a quick example.")
    print("\n🤖 Tyler: ", end="", flush=True)
    
    async for event in agent.go(thread, stream=True):
        if event.type.name == "LLM_STREAM_CHUNK":
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type.name == "TOOL_SELECTED":
            tool_name = event.data.get("tool_name")
            print(f"\n\n  [Using tool: {tool_name}]", flush=True)
            print("\n🤖 Tyler: ", end="", flush=True)
        elif event.type.name == "EXECUTION_COMPLETE":
            print("\n\n✓ Complete!")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    await agent.cleanup()
    print("✓ Done!\n")


if __name__ == "__main__":
    asyncio.run(main())

