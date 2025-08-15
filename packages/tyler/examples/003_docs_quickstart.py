"""
Example from the quickstart page of the documentation.
This demonstrates building a research assistant agent with multiple tool types.
Now with execution observability!
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
from tyler import Agent, Thread, Message, EventType
from lye import WEB_TOOLS, IMAGE_TOOLS, FILES_TOOLS


async def main():
    # Create your agent
    agent = Agent(
        name="research-assistant",
        model_name="gpt-4o",
        purpose="To help with research and analysis tasks",
        tools=[
            *WEB_TOOLS,      # Can search and fetch web content
            *IMAGE_TOOLS,    # Can analyze and describe images
            *FILES_TOOLS     # Can read and write files
        ]
    )

    # Create a conversation thread
    thread = Thread()
    
    # Add your request
    message = Message(
        role="user",
        content="Search for information about the Mars Perseverance rover and create a summary"
    )
    thread.add_message(message)
    
    # Let the agent work with streaming for real-time feedback
    print("🤖 Agent is working...\n")
    
    # Use streaming mode to show progress
    tool_count = 0
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.TOOL_SELECTED:
            tool_count += 1
            print(f"🔧 Using tool: {event.data.get('tool_name')}")
        elif event.type == EventType.LLM_STREAM_CHUNK:
            # Print content as it arrives
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(f"\n\n✅ Complete! Used {tool_count} tools in {event.data.get('duration_ms', 0):.2f}ms")


if __name__ == "__main__":
    asyncio.run(main()) 