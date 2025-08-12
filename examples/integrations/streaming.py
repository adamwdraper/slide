#!/usr/bin/env python3
"""
Example demonstrating streaming updates from the agent.
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
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent
agent = Agent(
    model_name="gpt-4.1",
    purpose="To demonstrate streaming updates.",
    temperature=0.7
)

async def main():
    # Create a thread
    thread = Thread()

    # Add a user message
    message = Message(
        role="user",
        content="Write a poem about a brave adventurer."
    )
    thread.add_message(message)

    logger.info("User: %s", message.content)

    # Process the thread with streaming
    content_buffer = []
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_STREAM_CHUNK:
            chunk = event.data.get("content_chunk", "")
            content_buffer.append(chunk)
            logger.info("Content chunk: %s", chunk)
        elif event.type == EventType.MESSAGE_CREATED:
            msg = event.data.get("message")
            if msg and msg.role == "assistant":
                logger.info("Complete assistant message: %s", msg.content)
            elif msg and msg.role == "tool":
                logger.info("Tool message: %s", msg.content)
        elif event.type == EventType.EXECUTION_ERROR:
            logger.error("Error: %s", event.data.get("message"))
        elif event.type == EventType.EXECUTION_COMPLETE:
            logger.info("Processing complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 