"""
Example from the quickstart page of the documentation.
This demonstrates building a research assistant agent with multiple tool types.
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
        model_name="gpt-4o",  # Use the model for your API key provider
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
    
    # Let the agent work with streaming feedback
    print("🤖 Agent is working...\n")
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type == EventType.TOOL_SELECTED:
            print(f"\n🔧 Using tool: {event.data.get('tool_name')}")
        elif event.type == EventType.TOOL_RESULT:
            print(f"✅ Tool result from {event.data.get('tool_name')}")
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(f"\n\nDone in {event.data.get('duration_ms', 0):.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
