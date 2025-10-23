#!/usr/bin/env python3
"""Manual test for MCP integration with real Mintlify server.

This script connects to the W&B documentation Mintlify MCP server
and runs a real query. Use this to verify the feature works end-to-end.

Run:
    python test_mcp_manual.py
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from tyler import Agent, Thread, Message


async def main():
    """Test MCP with real Mintlify server."""
    
    print("=" * 70)
    print("Manual MCP Test: Connecting to W&B Docs (Mintlify MCP)")
    print("=" * 70)
    
    # Create agent with real Mintlify MCP server
    print("\n1️⃣  Creating agent with MCP config...")
    agent = Agent(
        name="DocsBot",
        model_name="gpt-4o-mini",
        purpose="To help search W&B documentation",
        mcp={
            "servers": [{
                "name": "wandb_docs",
                "transport": "sse",
                "url": "https://docs.wandb.ai/mcp",
                "fail_silent": False  # Fail if server is down
            }]
        }
    )
    print("   ✓ Agent created (config schema validated)")
    
    # Connect to MCP servers
    print("\n2️⃣  Connecting to Mintlify MCP server...")
    print("   URL: https://docs.wandb.ai/mcp")
    
    try:
        await agent.connect_mcp()
        print("   ✓ Connected successfully!")
        
        # Show discovered tools
        mcp_tools = [
            t["function"]["name"]
            for t in agent._processed_tools
            if "wandb_docs_" in t["function"]["name"]
        ]
        print(f"\n   Tools discovered: {len(mcp_tools)}")
        for tool_name in mcp_tools:
            print(f"     - {tool_name}")
        
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        print("\n   This could mean:")
        print("     - The Mintlify server is temporarily unavailable")
        print("     - Network connectivity issues")
        print("     - The URL has changed")
        return
    
    # Create a thread and ask a question
    print("\n3️⃣  Testing tool execution...")
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What is Weave and how do I use it for tracing?"
    ))
    
    print("   Question: What is Weave and how do I use it for tracing?")
    print("\n   Agent response:")
    print("   " + "-" * 66)
    
    # Stream the response
    async for event in agent.go(thread, stream=True):
        if event.type.name == "LLM_STREAM_CHUNK":
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type.name == "TOOL_SELECTED":
            tool_name = event.data.get("tool_name")
            print(f"\n   [Using tool: {tool_name}]", flush=True)
            print("   ", end="", flush=True)
        elif event.type.name == "EXECUTION_COMPLETE":
            print("\n   " + "-" * 66)
    
    # Cleanup
    print("\n4️⃣  Cleaning up...")
    await agent.cleanup()
    print("   ✓ MCP connections closed")
    
    print("\n" + "=" * 70)
    print("✅ Manual test complete - MCP integration working!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

