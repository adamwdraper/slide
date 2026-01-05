"""MCP Progress Callbacks: Real-time progress updates from long-running tools.

This example demonstrates how to receive progress notifications from MCP tools
that report progress during execution. This is useful for:
- Long-running search operations
- File processing tasks
- Data analysis operations
- Any MCP tool that emits progress updates

The TOOL_PROGRESS event contains:
- tool_name: Name of the tool reporting progress
- progress: Current progress value (e.g., bytes processed, items completed)
- total: Total expected value (optional, may be None)
- message: Human-readable progress message (optional)
- tool_call_id: ID of the tool call

Note: Progress events are only emitted if the MCP server implements progress
notifications. Not all MCP servers support this feature.

Run:
    python 303_mcp_progress_callback.py
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import os
import weave
from tyler import Agent, Thread, Message
from tyler.models.execution import EventType

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
    except Exception:
        pass


async def example_streaming_with_progress():
    """Example 1: Handle progress events during streaming."""
    
    print("\n" + "=" * 70)
    print("Example 1: Progress Events in Streaming")
    print("=" * 70)
    print("\nThis example shows how to handle TOOL_PROGRESS events during streaming.")
    print("Progress events are yielded when MCP tools report progress updates.\n")
    
    agent = Agent(
        name="ProgressDemo",
        model_name="gpt-4o-mini",
        purpose="Demonstrate progress callback handling",
        mcp={
            "servers": [{
                "name": "docs",
                "transport": "streamablehttp",
                "url": "https://slide.mintlify.app/mcp",
                "prefix": "slide",
                "fail_silent": False
            }]
        }
    )
    
    print("Connecting to MCP server...")
    await agent.connect_mcp()
    print(f"✓ Connected! Tools: {[t['function']['name'] for t in agent._processed_tools]}\n")
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Use the slide_SearchSlideFramework tool to search for 'agent streaming'. Return the results."
    ))
    
    print("💬 User: Use the slide_SearchSlideFramework tool to search for 'agent streaming'")
    print("\n🤖 Agent: ", end="", flush=True)
    
    progress_count = 0
    
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data.get("content_chunk", ""), end="", flush=True)
            
        elif event.type == EventType.TOOL_SELECTED:
            tool_name = event.data.get("tool_name")
            print(f"\n\n  📍 Starting tool: {tool_name}", flush=True)
            
        elif event.type == EventType.TOOL_PROGRESS:
            # Handle progress updates from MCP tools
            progress_count += 1
            progress = event.data.get("progress", 0)
            total = event.data.get("total")
            message = event.data.get("message", "")
            tool_name = event.data.get("tool_name")
            
            if total:
                pct = (progress / total) * 100
                print(f"  ⏳ [{tool_name}] Progress: {progress}/{total} ({pct:.1f}%) - {message}", flush=True)
            else:
                print(f"  ⏳ [{tool_name}] Progress: {progress} - {message}", flush=True)
                
        elif event.type == EventType.TOOL_RESULT:
            tool_name = event.data.get("tool_name")
            duration_ms = event.data.get("duration_ms", 0)
            print(f"  ✓ Tool complete: {tool_name} ({duration_ms:.0f}ms)", flush=True)
            print("\n🤖 Agent: ", end="", flush=True)
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(f"\n\n✓ Complete! (Progress events received: {progress_count})")
    
    await agent.cleanup()


async def example_custom_progress_callback():
    """Example 2: Provide a custom progress callback via tool_context."""
    
    print("\n" + "=" * 70)
    print("Example 2: Custom Progress Callback")
    print("=" * 70)
    print("\nYou can also provide a custom progress callback via tool_context.")
    print("This is useful when you need custom handling beyond streaming events.\n")
    
    # Track progress in a custom data structure
    progress_log = []
    
    async def my_progress_callback(progress: float, total: float = None, message: str = None):
        """Custom progress handler that logs to our data structure."""
        entry = {
            "progress": progress,
            "total": total,
            "message": message,
            "timestamp": asyncio.get_event_loop().time()
        }
        progress_log.append(entry)
        
        # Custom formatting
        if total:
            bar_width = 30
            filled = int((progress / total) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"    [{bar}] {progress}/{total}", flush=True)
        else:
            print(f"    Progress update: {progress} - {message}", flush=True)
    
    agent = Agent(
        name="CustomProgressDemo",
        model_name="gpt-4o-mini",
        purpose="Demonstrate custom progress callback",
        mcp={
            "servers": [{
                "name": "docs",
                "transport": "streamablehttp",
                "url": "https://slide.mintlify.app/mcp",
                "prefix": "docs",
                "fail_silent": False
            }]
        }
    )
    
    print("Connecting to MCP server...")
    await agent.connect_mcp()
    print("✓ Connected!\n")
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Use the docs_SearchSlideFramework tool to search for 'MCP integration'. Show me what you find."
    ))
    
    print("💬 User: Use the docs_SearchSlideFramework tool to search for 'MCP integration'")
    print("\n🤖 Agent: ", end="", flush=True)
    
    # Use agent.run() with custom tool_context including progress_callback
    # Note: For run(), progress events go to the callback, not as yielded events
    result = await agent.run(
        thread,
        tool_context={
            "progress_callback": my_progress_callback,
            # You can include other context values too
            "custom_data": "example"
        }
    )
    
    print(result.content[:500] + "..." if len(result.content) > 500 else result.content)
    print(f"\n\n✓ Complete! Progress log entries: {len(progress_log)}")
    
    if progress_log:
        print("\nProgress log:")
        for entry in progress_log:
            print(f"  - {entry}")
    else:
        print("\n(Note: This MCP server didn't emit progress notifications)")
    
    await agent.cleanup()


async def main():
    """Run all progress callback examples."""
    
    print("=" * 70)
    print("Tyler MCP Progress Callback Examples")
    print("=" * 70)
    print("\nProgress callbacks allow you to receive real-time updates from")
    print("MCP tools that support progress notifications.")
    print("\nNote: Not all MCP servers emit progress events. The Slide docs")
    print("server used in these examples may not emit progress, but the")
    print("infrastructure is in place for servers that do.")
    
    # Example 1: Streaming with progress events
    await example_streaming_with_progress()
    
    # Example 2: Custom progress callback
    await example_custom_progress_callback()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("\nKey takeaways:")
    print("  ✓ TOOL_PROGRESS events are yielded during agent.stream()")
    print("  ✓ Custom callbacks can be passed via tool_context")
    print("  ✓ Progress includes: progress, total, message, tool_name")
    print("  ✓ Not all MCP servers emit progress - depends on implementation")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

