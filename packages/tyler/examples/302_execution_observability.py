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
        weave.init("slide")
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
    """Demonstrate non-streaming mode."""
    logger.info("\n" + "="*60)
    logger.info("NON-STREAMING MODE")
    logger.info("="*60)
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Calculate the area of a circle with radius 5, then multiply by 2"
    ))
    
    # Execute in non-streaming mode
    result = await agent.run(thread)
    
    # Display the response
    logger.info("\n📝 Response: %s", result.content)
    
    # Display new messages
    logger.info("\n📊 Result Details:")
    logger.info("   New messages: %d", len(result.new_messages))
    logger.info("   Thread messages: %d", len(result.thread.messages))
    
    # Show tool usage from messages
    for msg in result.new_messages:
        if msg.tool_calls:
            logger.info("\n🔧 Tool Calls:")
            for tc in msg.tool_calls:
                logger.info("   Tool: %s", tc.get('function', {}).get('name'))
                logger.info("   Arguments: %s", tc.get('function', {}).get('arguments'))

async def demo_streaming():
    """Demonstrate streaming mode."""
    logger.info("\n" + "="*60)
    logger.info("STREAMING MODE - Real-time Events")
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
    
    # NOTE: The streaming API has changed - this is a simplified version
    # In the current implementation, streaming may return different types of events
    # or may not be fully supported as before
    try:
        async for event in agent.stream(thread):
            event_count += 1
            
            if isinstance(event, ExecutionEvent):
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
            else:
                # Handle other types of events that might be returned
                logger.info("Event: %s", type(event).__name__)
    except Exception as e:
        logger.error("Streaming error: %s", str(e))
        logger.info("Note: Streaming functionality may have changed in this version")

async def main():
    """Run both demos."""
    # First show non-streaming mode
    await demo_non_streaming()
    
    # Then show streaming mode
    await demo_streaming()
    
    logger.info("\n" + "="*60)
    logger.info("✨ Demo complete!")
    logger.info("="*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)
