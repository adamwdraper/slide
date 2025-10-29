#!/usr/bin/env python3
"""
Example showing different ways to import tool groups.

You have flexibility in how you import and use tools with Tyler.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import weave
from tyler import Agent, Thread, Message
from tyler.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize weave
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-tool-groups")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    print("=== Different Ways to Import Tools ===\n")
    
    # Method 1: Import entire tool groups
    from lye import WEB_TOOLS, AUDIO_TOOLS, FILES_TOOLS
    
    # Create agent with all tools from multiple groups
    agent1 = Agent(
        name="multi_tool_agent",
        model_name="gpt-4.1",
        purpose="To help with web, audio, and file tasks",
        tools=[
            *WEB_TOOLS,      # Unpacks all web tools
            *AUDIO_TOOLS,    # Unpacks all audio tools
            *FILES_TOOLS     # Unpacks all file tools
        ]
    )
    print(f"Agent 1 has {len(agent1._processed_tools)} tools from multiple groups")
    
    # Method 2: Import specific tools from their modules
    from lye.web import fetch_page
    from lye.files import write_file
    from lye.image import analyze_image
    
    agent2 = Agent(
        name="specific_tools_agent", 
        model_name="gpt-4.1",
        purpose="To help with specific tasks",
        tools=[
            fetch_page,       # Just web fetch
            analyze_image,    # Just image analysis
            write_file        # Just file writing
        ]
    )
    print(f"Agent 2 has {len(agent2._processed_tools)} specific tools")
    
    # Method 3: Mix and match - some groups, some specific
    from lye import WEB_TOOLS
    from lye.command_line import run_command
    
    agent3 = Agent(
        name="mixed_agent",
        model_name="gpt-4.1", 
        purpose="To help with web tasks and command execution",
        tools=[
            *WEB_TOOLS,      # All web tools
            run_command      # Plus this specific tool
        ]
    )
    print(f"Agent 3 has {len(agent3._processed_tools)} tools (mix of group and specific)")
    
    # Method 4: Legacy string-based (still works!)
    agent4 = Agent(
        name="legacy_agent",
        model_name="gpt-4.1",
        purpose="To help with web and file tasks",
        tools=["web", "files"]  # Old way still supported
    )
    print(f"Agent 4 has {len(agent4._processed_tools)} tools (using legacy strings)")
    
    # Method 5: Get actual function implementations from tool groups
    # This is useful if you want to see what's available
    print("\n=== Available Tools in Groups ===")
    print(f"Web tools: {[tool['definition']['function']['name'] for tool in WEB_TOOLS]}")
    print(f"Audio tools: {[tool['definition']['function']['name'] for tool in AUDIO_TOOLS]}")
    
    # Method 6: Filter tools from a group
    # Only get tools that match certain criteria
    web_download_tools = [
        tool for tool in WEB_TOOLS 
        if 'download' in tool['definition']['function']['name']
    ]
    
    agent5 = Agent(
        name="download_agent",
        model_name="gpt-4.1",
        purpose="To help download files",
        tools=web_download_tools  # Filtered subset
    )
    print(f"\nAgent 5 has {len(agent5._processed_tools)} download-related tools")
    
    # Demo conversation
    print("\n=== Demo Conversation ===")
    thread = Thread()
    message = Message(role="user", content="What tools do you have available?")
    thread.add_message(message)
    
    processed_thread, new_messages = await agent1.run(thread)
    
    for msg in new_messages:
        if msg.role == "assistant":
            print(f"Multi-tool agent: {msg.content}")


if __name__ == "__main__":
    asyncio.run(main()) 