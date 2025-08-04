"""
Example from the quickstart page of the documentation.
This demonstrates building a research assistant agent with multiple tool types.
"""

import asyncio
from tyler import Agent, Thread, Message
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
    
    # Let the agent work
    print("🤖 Agent is working...")
    processed_thread, new_messages = await agent.go(thread)
    
    # Print the results
    for msg in new_messages:
        if msg.role == "assistant":
            print(f"\n💬 Assistant: {msg.content}")
        elif msg.role == "tool":
            print(f"\n🔧 Used tool '{msg.name}'")


if __name__ == "__main__":
    asyncio.run(main()) 