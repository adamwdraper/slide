#!/usr/bin/env python3
"""
Example demonstrating streaming updates from the agent.
Now with the new event-based streaming API!
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
from tyler import Agent, Thread, Message, EventType, ExecutionEvent

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("slide")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent
agent = Agent(
    model_name="gpt-4o",
    purpose="To demonstrate streaming updates.",
    temperature=0.7
)

async def main():
    # Create a thread
    thread = Thread()

    # Add a user message
    message = Message(
        role="user",
        content="Write a short poem about a brave adventurer."
    )
    thread.add_message(message)

    logger.info("User: %s", message.content)
    logger.info("Processing with streaming...")
    logger.info("-" * 50)

    # Process the thread with the new streaming API
    content_buffer = []
    total_tokens = 0
    
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_STREAM_CHUNK:
            # Real-time content streaming
            chunk = event.data.get("content_chunk", "")
            content_buffer.append(chunk)
            # Print chunk without newline for real-time effect
            print(chunk, end="", flush=True)
            
        elif event.type == EventType.LLM_REQUEST:
            logger.debug("🤖 Sending request to %s...", event.data.get("model"))
            
        elif event.type == EventType.LLM_RESPONSE:
            # Complete response received
            print()  # New line after streaming
            logger.debug("💬 Complete response received")
            tokens = event.data.get("tokens", {})
            total_tokens = tokens.get("total_tokens", 0)
            
        elif event.type == EventType.TOOL_SELECTED:
            logger.info("🔧 Using tool: %s", event.data.get("tool_name"))
            logger.debug("   Arguments: %s", event.data.get("arguments"))
            
        elif event.type == EventType.TOOL_RESULT:
            logger.info("✅ Tool result: %s", event.data.get("result")[:100] + "...")
            
        elif event.type == EventType.MESSAGE_CREATED:
            msg = event.data.get("message")
            if msg and msg.role == "assistant":
                logger.debug("📝 Assistant message created")
            elif msg and msg.role == "tool":
                logger.debug("🔨 Tool message created")
                
        elif event.type == EventType.EXECUTION_ERROR:
            logger.error("❌ Error: %s", event.data.get("message"))
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            logger.info("-" * 50)
            logger.info("🏁 Processing complete!")
            logger.info("   Total time: %.2fms", event.data.get("duration_ms", 0))
            logger.info("   Total tokens: %d", total_tokens)
            logger.info("   Content length: %d chars", len(''.join(content_buffer)))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 