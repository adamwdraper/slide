#!/usr/bin/env python3
"""
Example demonstrating tool imports - comparing approaches.

Shows both the direct function import and namespace approaches.
Namespace approach is recommended to avoid naming collisions.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import weave
from tyler import Agent, Thread, Message
from tyler.utils.logging import get_logger

# Approach 1: Direct function imports (simple but risks name collisions)
# from lye import fetch_page, download_file, run_command, read_file, write_file

# Approach 2: Namespace imports (RECOMMENDED - avoids collisions)
from lye import web, files, command_line

logger = get_logger(__name__)

# Initialize weave
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-tool-imports")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    print("=== Tool Import Approaches ===\n")
    
    # Using namespace approach (RECOMMENDED)
    print("Using namespace imports (recommended):")
    agent = Agent(
        name="research_assistant",
        model_name="gpt-4.1",
        purpose="To help users research information and manage files",
        tools=[
            # Clear which module each tool comes from
            web.fetch_page,
            web.download_file,
            command_line.run_command,
            files.read_file,
            files.write_file
        ],
        temperature=0.7
    )
    print(f"Loaded {len(agent._processed_tools)} tools with clear namespacing\n")
    
    # Create a thread
    thread = Thread()
    
    # Example conversations showing the tools in action
    conversations = [
        "Can you fetch the content from https://example.com?",
        "Run the command 'ls -la' to see what files we have",
        "Write a summary of what you found to a file called research_summary.txt"
    ]
    
    for user_input in conversations:
        logger.info(f"User: {user_input}")
        
        # Add user message
        message = Message(role="user", content=user_input)
        thread.add_message(message)
        
        # Process with agent
        processed_thread, new_messages = await agent.go(thread)
        
        # Log responses
        for msg in new_messages:
            if msg.role == "assistant":
                logger.info(f"Assistant: {msg.content}")
            elif msg.role == "tool":
                logger.info(f"Tool ({msg.name}): {msg.content[:100]}...")
        
        logger.info("-" * 50)


# Why namespace imports are better:
# 1. No ambiguity - web.fetch_page vs hypothetical files.fetch_page
# 2. Self-documenting - you always know the source module
# 3. Easier refactoring - changing implementations doesn't break imports
# 4. Better IDE support - autocomplete shows module contents
# 5. Follows Python conventions - like numpy.array, pandas.DataFrame

if __name__ == "__main__":
    asyncio.run(main()) 