#!/usr/bin/env python3
"""
Basic example demonstrating a simple conversation with the agent.
Now with execution observability!
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
from tyler import Agent, Thread, Message, AgentResult

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent
agent = Agent(
    model_name="gpt-4o",
    purpose="To be a helpful assistant.",
    temperature=0.7
)

async def main():
    # Create a thread
    thread = Thread()

    # Example conversation
    conversations = [
        "Hello! Can you help me with some tasks?",
        "What's your purpose?",
        "Thank you, that's all for now."
    ]

    for user_input in conversations:
        logger.info("User: %s", user_input)
        
        # Add user message
        message = Message(
            role="user",
            content=user_input
        )
        thread.add_message(message)

        # Process the thread with the new API
        result = await agent.go(thread)
        
        # The thread is updated in-place, but we also get rich execution details
        logger.info("Assistant: %s", result.output)
        
        # Show execution metrics
        logger.debug("Execution metrics:")
        logger.debug("  - Duration: %.2fms", result.execution.duration_ms)
        logger.debug("  - Total tokens: %d", result.execution.total_tokens)
        logger.debug("  - Success: %s", result.success)
        
        # Show any tool usage
        if result.execution.tool_calls:
            logger.debug("  - Tools used:")
            for tool_call in result.execution.tool_calls:
                logger.debug("    * %s (%.2fms)", tool_call.tool_name, tool_call.duration_ms)
        
        logger.info("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 