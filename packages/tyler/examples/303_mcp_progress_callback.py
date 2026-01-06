"""MCP Progress Callbacks: Real-time progress updates from long-running tools.

This example demonstrates how to receive progress notifications from MCP tools
that report progress during execution. It includes:

1. A self-contained MCP server with a tool that emits progress updates
2. An agent that connects to this server and handles TOOL_PROGRESS events
3. Both streaming and custom callback approaches

Run:
    python 303_mcp_progress_callback.py
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import os
import sys
import tempfile
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


# Inline MCP server code that emits progress notifications
MCP_SERVER_CODE = '''
"""Minimal MCP server that emits progress notifications."""
import asyncio
from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP(name="ProgressDemo")

@mcp.tool()
async def long_task(task_name: str, ctx: Context, steps: int = 5) -> str:
    """Execute a simulated long-running task with progress updates.
    
    Args:
        task_name: Name of the task to execute
        steps: Number of steps to simulate (default 5)
    """
    await ctx.info(f"Starting task: {task_name}")
    
    for i in range(steps):
        # Simulate work
        await asyncio.sleep(0.3)
        
        # Report progress
        progress = i + 1
        await ctx.report_progress(
            progress=progress,
            total=steps,
            message=f"Completed step {progress}/{steps}"
        )
        await ctx.debug(f"Step {progress} done")
    
    return f"Task '{task_name}' completed successfully after {steps} steps!"

@mcp.tool()
async def quick_task(message: str) -> str:
    """A quick task that doesn't emit progress (for comparison)."""
    return f"Quick response: {message}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
'''


async def example_with_real_progress():
    """Example showing real progress events from a local MCP server."""
    
    print("\n" + "=" * 70)
    print("MCP Progress Callback Demo")
    print("=" * 70)
    print("\nThis example runs a local MCP server that emits progress updates")
    print("during tool execution. Watch for TOOL_PROGRESS events!\n")
    
    # Write the server code to a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(MCP_SERVER_CODE)
        server_script = f.name
    
    try:
        # Create agent connected to our progress-enabled server
        # Using gpt-4o for more reliable tool calling
        agent = Agent(
            name="ProgressAgent",
            model_name="gpt-4o",
            purpose="Execute tool calls immediately when requested. Do not describe actions - perform them.",
            mcp={
                "servers": [{
                    "name": "progress_demo",
                    "transport": "stdio",
                    "command": sys.executable,  # Use current Python
                    "args": [server_script],
                    "prefix": "demo",
                    "fail_silent": False
                }]
            }
        )
        
        print("Starting MCP server with progress support...")
        await agent.connect_mcp()
        
        tools = [t['function']['name'] for t in agent._processed_tools]
        print(f"✓ Connected! Tools available: {tools}\n")
        
        # Create thread with a request that triggers the long_task tool
        thread = Thread()
        thread.add_message(Message(
            role="user",
            content="Call demo_long_task with task_name='data_processing' and steps=5"
        ))
        
        print("💬 User: Call demo_long_task with 5 steps")
        print("\n🤖 Agent: ", end="", flush=True)
        
        progress_events = []
        
        # Force tool call on first iteration
        first_iteration = True
        async for event in agent.stream(thread):
            if event.type == EventType.LLM_STREAM_CHUNK:
                chunk = event.data.get("content_chunk", "")
                print(chunk, end="", flush=True)
                
            elif event.type == EventType.TOOL_SELECTED:
                tool_name = event.data.get("tool_name")
                print(f"\n\n  📍 Starting: {tool_name}", flush=True)
                
            elif event.type == EventType.TOOL_PROGRESS:
                # This is what we're demonstrating!
                progress = event.data.get("progress", 0)
                total = event.data.get("total")
                message = event.data.get("message", "")
                tool_name = event.data.get("tool_name")
                
                progress_events.append(event.data)
                
                # Show a nice progress bar
                if total:
                    pct = (progress / total) * 100
                    bar_width = 20
                    filled = int((progress / total) * bar_width)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    print(f"  ⏳ [{bar}] {pct:.0f}% - {message}", flush=True)
                else:
                    print(f"  ⏳ Progress: {progress} - {message}", flush=True)
                
            elif event.type == EventType.TOOL_RESULT:
                tool_name = event.data.get("tool_name")
                duration_ms = event.data.get("duration_ms", 0)
                print(f"  ✓ Complete: {tool_name} ({duration_ms:.0f}ms)", flush=True)
                print("\n🤖 Agent: ", end="", flush=True)
                
            elif event.type == EventType.EXECUTION_COMPLETE:
                print(f"\n\n{'=' * 50}")
                print(f"✓ Execution complete!")
                print(f"  Progress events received: {len(progress_events)}")
                if progress_events:
                    print(f"\n  Progress event details:")
                    for i, pe in enumerate(progress_events):
                        print(f"    {i+1}. {pe['progress']}/{pe['total']} - {pe['message']}")
        
        await agent.cleanup()
        
    finally:
        # Clean up temp file
        try:
            os.unlink(server_script)
        except OSError:
            pass


async def example_custom_callback():
    """Example showing custom progress callback via tool_context."""
    
    print("\n" + "=" * 70)
    print("Custom Progress Callback Example")
    print("=" * 70)
    print("\nYou can also provide a custom callback via tool_context.\n")
    
    # Write the server code to a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(MCP_SERVER_CODE)
        server_script = f.name
    
    try:
        # Custom progress tracking
        progress_log = []
        
        async def my_progress_callback(progress: float, total: float = None, message: str = None):
            """Custom callback that logs progress."""
            progress_log.append({"progress": progress, "total": total, "message": message})
            if total:
                pct = (progress / total) * 100
                print(f"    📊 Custom callback: {pct:.0f}% complete - {message}")
            else:
                print(f"    📊 Custom callback: {progress} - {message}")
        
        agent = Agent(
            name="CustomCallbackAgent",
            model_name="gpt-4o",
            purpose="Execute tool calls immediately when requested. Do not describe actions - perform them.",
            mcp={
                "servers": [{
                    "name": "progress_demo",
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [server_script],
                    "prefix": "demo",
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
            content="Run demo_long_task with task_name='custom_test' and steps=3"
        ))
        
        print("💬 User: Run demo_long_task with 3 steps")
        print("   (Using custom progress_callback)\n")
        
        # Use run() with custom tool_context
        result = await agent.run(
            thread,
            tool_context={
                "progress_callback": my_progress_callback
            }
        )
        
        print(f"\n✓ Result: {result.content[:200]}..." if len(result.content) > 200 else f"\n✓ Result: {result.content}")
        print(f"\n  Custom callback invocations: {len(progress_log)}")
        
        await agent.cleanup()
        
    finally:
        try:
            os.unlink(server_script)
        except:
            pass


async def main():
    """Run progress callback examples."""
    
    print("=" * 70)
    print("Tyler MCP Progress Callback Examples")
    print("=" * 70)
    print("\nThese examples demonstrate real progress callbacks from MCP tools.")
    print("A local MCP server is spawned that emits progress updates.")
    
    # Main example with streaming
    await example_with_real_progress()
    
    # Custom callback example
    await example_custom_callback()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("\nKey takeaways:")
    print("  ✓ TOOL_PROGRESS events are yielded during agent.stream()")
    print("  ✓ Progress includes: progress, total, message, tool_name")
    print("  ✓ Custom callbacks can be passed via tool_context")
    print("  ✓ MCP servers use ctx.report_progress() to emit updates")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
