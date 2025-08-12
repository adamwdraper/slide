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
        logger.info("Assistant: %s", result.content)
        
        # Show execution metrics
        logger.debug("Execution metrics:")
        # Calculate duration from message timestamps
        if result.new_messages:
            start_time = min(msg.timestamp for msg in result.new_messages)
            end_time = max(msg.timestamp for msg in result.new_messages)
            duration_ms = (end_time - start_time).total_seconds() * 1000
            logger.debug("  - Duration: %.2fms", duration_ms)
        
        # Get token usage from thread
        token_stats = result.thread.get_total_tokens()
        logger.debug("  - Total tokens: %d", token_stats['overall']['total_tokens'])
        
        # Show any tool usage
        tool_usage = result.thread.get_tool_usage()
        if tool_usage['total_calls'] > 0:
            logger.debug("  - Tools used:")
            for tool_name, count in tool_usage['tools'].items():
                logger.debug("    * %s (%d calls)", tool_name, count)
        
        logger.info("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 