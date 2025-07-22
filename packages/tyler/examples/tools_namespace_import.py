#!/usr/bin/env python3
"""
Example demonstrating namespace-based tool imports - avoiding name collisions.

This shows how to use module namespaces to organize tools and avoid
potential naming conflicts between different tool modules.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import weave
from tyler import Agent, Thread, Message
from tyler.utils.logging import get_logger

# Import tool modules as namespaces
from lye import web, files, command_line, audio, image

logger = get_logger(__name__)

# Initialize weave
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-namespace-tools")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    print("=== Namespace-based Tool Imports ===\n")
    
    # Method 1: Pass entire modules (all tools from each module)
    print("1. Using entire modules:")
    agent1 = Agent(
        name="full_module_agent",
        model_name="gpt-4.1",
        purpose="Agent with all tools from specific modules",
        tools=[
            web,            # All web tools
            files,          # All file tools
            command_line    # All command line tools
        ]
    )
    print(f"   Loaded {len(agent1._processed_tools)} tools from modules\n")
    
    # Method 2: Pass specific functions from modules (avoiding collisions)
    print("2. Using specific functions from namespaces:")
    agent2 = Agent(
        name="specific_function_agent", 
        model_name="gpt-4.1",
        purpose="Agent with specific tools selected from modules",
        tools=[
            web.fetch_page,      # Just the fetch_page function
            web.download_file,   # Just the download_file function
            files.read_file,     # Just read_file
            files.write_file,    # Just write_file
            command_line.run_command  # Just run_command
        ]
    )
    print(f"   Loaded {len(agent2._processed_tools)} specific tools\n")
    
    # Method 3: Mix modules and specific functions
    print("3. Mixing modules and specific functions:")
    agent3 = Agent(
        name="mixed_agent",
        model_name="gpt-4.1", 
        purpose="Agent mixing full modules and specific functions",
        tools=[
            web,                    # All web tools
            files.write_file,       # Just write_file from files
            audio.text_to_speech,   # Just text_to_speech from audio
            image                   # All image tools
        ]
    )
    print(f"   Loaded {len(agent3._processed_tools)} tools (mixed approach)\n")
    
    # Example usage showing namespace clarity
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Can you fetch the content from https://example.com and save a summary?"
    ))
    
    print("Processing request with namespace-based tools...")
    processed_thread, new_messages = await agent2.go(thread)
    
    for msg in new_messages:
        if msg.role == "assistant":
            print(f"Assistant: {msg.content}")
        elif msg.role == "tool":
            print(f"Tool ({msg.name}): Used successfully")


# Benefits of namespace approach:
# 1. No naming collisions - web.search vs files.search would be distinct
# 2. Clear organization - you know which module a tool comes from
# 3. Flexible granularity - use entire modules or specific functions
# 4. Better for large codebases - scales well as more tools are added
# 5. IDE support - autocomplete shows available functions per module

if __name__ == "__main__":
    asyncio.run(main()) 