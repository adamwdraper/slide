#!/usr/bin/env python3
"""
Example demonstrating the new agent execution observability features.
Shows both streaming and non-streaming modes with detailed metrics.
"""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import os
import asyncio
import weave
import sys
from tyler import Agent, Thread, Message, EventType, ExecutionEvent, AgentResult

# Define a simple tool to demonstrate tool usage tracking
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        # Safely evaluate mathematical expressions
        result = eval(expression, {"__builtins__": {}}, {})
        return f"The result is: {result}"
    except Exception as e:
        return f"Error: {str(e)}"

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent with a tool
agent = Agent(
    model_name="gpt-4o-mini",
    purpose="To demonstrate execution observability with tool usage.",
    temperature=0.7,
    tools=[{
        "definition": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate a mathematical expression",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "The mathematical expression to evaluate"
                        }
                    },
                    "required": ["expression"]
                }
            }
        },
        "implementation": calculate
    }]
)

async def demo_non_streaming():
    """Demonstrate non-streaming mode with full execution details."""
    logger.info("\n" + "="*60)
    logger.info("NON-STREAMING MODE - Complete Execution Details")
    logger.info("="*60)
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Calculate the area of a circle with radius 5, then multiply by 2"
    ))
    
    # Execute in non-streaming mode
    result = await agent.go(thread)
    
    # Display the response
    logger.info("\n📝 Response: %s", result.content)
    
    # Display execution metrics
    logger.info("\n📊 Execution Metrics:")
    logger.info("   Duration: %.2fms", result.execution.duration_ms)
    logger.info("   Total tokens: %d", result.execution.total_tokens)
    logger.info("   Total events: %d", len(result.execution.events))
    logger.info("   Success: %s", result.success)
    
    # Display tool usage
    if result.execution.tool_calls:
        logger.info("\n🔧 Tool Usage:")
        for tool_call in result.execution.tool_calls:
            logger.info("   Tool: %s", tool_call.tool_name)
            logger.info("   Arguments: %s", tool_call.arguments)
            logger.info("   Result: %s", tool_call.result)
            logger.info("   Duration: %.2fms", tool_call.duration_ms)
            logger.info("   Success: %s", tool_call.success)
    
    # Display event breakdown
    event_counts = {}
    for event in result.execution.events:
        event_counts[event.type.value] = event_counts.get(event.type.value, 0) + 1
    
    logger.info("\n📈 Event Breakdown:")
    for event_type, count in sorted(event_counts.items()):
        logger.info("   %s: %d", event_type, count)

async def demo_streaming():
    """Demonstrate streaming mode with real-time events."""
    logger.info("\n" + "="*60)
    logger.info("STREAMING MODE - Real-time Event Stream")
    logger.info("="*60)
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What's 15% of 240? Show your calculation."
    ))
    
    # Track metrics as we stream
    event_count = 0
    chunk_count = 0
    tool_count = 0
    
    logger.info("\n🎯 Streaming events as they happen:\n")
    
    async for event in agent.go(thread, stream=True):
        event_count += 1
        
        if event.type == EventType.LLM_STREAM_CHUNK:
            chunk_count += 1
            # Print chunks inline for streaming effect
            print(event.data.get("content_chunk", ""), end="", flush=True)
            
        elif event.type == EventType.LLM_REQUEST:
            logger.info("→ Sending request to LLM...")
            
        elif event.type == EventType.TOOL_SELECTED:
            tool_count += 1
            print()  # New line before tool info
            logger.info("→ Tool selected: %s", event.data.get("tool_name"))
            logger.info("  Arguments: %s", event.data.get("arguments"))
            
        elif event.type == EventType.TOOL_RESULT:
            logger.info("← Tool result: %s", event.data.get("result"))
            print()  # Resume streaming on new line
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            print()  # Final newline
            logger.info("\n✅ Streaming complete!")
            logger.info("   Total events: %d", event_count)
            logger.info("   Content chunks: %d", chunk_count)
            logger.info("   Tool calls: %d", tool_count)
            logger.info("   Duration: %.2fms", event.data.get("duration_ms", 0))

async def main():
    """Run both demos."""
    # First show non-streaming mode
    await demo_non_streaming()
    
    # Then show streaming mode
    await demo_streaming()
    
    logger.info("\n" + "="*60)
    logger.info("✨ Execution observability demo complete!")
    logger.info("="*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)
