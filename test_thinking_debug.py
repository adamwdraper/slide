"""
Quick test to see what fields are in the streaming delta for o3-mini
"""
import asyncio
import os
import logging
from tyler import Agent, Thread, Message, EventType

# Set up logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

async def test_o3_mini_thinking():
    agent = Agent(
        name="test",
        model_name="o3-mini",
        purpose="To test thinking tokens"
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="What is 2+2? Show your thinking."))
    
    print("\n=== Checking for thinking tokens ===\n")
    
    has_thinking = False
    has_content = False
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            has_thinking = True
            print(f"✅ THINKING: {event.data['thinking_chunk'][:100]}")
        elif event.type == EventType.LLM_STREAM_CHUNK:
            has_content = True
            print(f"   Content: {event.data['content_chunk'][:100]}")
    
    print(f"\n=== Results ===")
    print(f"Has thinking tokens: {has_thinking}")
    print(f"Has content: {has_content}")
    
    if not has_thinking:
        print("\n⚠️  No thinking tokens detected!")
        print("This could mean:")
        print("1. o3-mini doesn't emit thinking tokens in streaming mode")
        print("2. LiteLLM isn't passing them through")
        print("3. The field name is different than expected")
        print("\nCheck debug logs above for 'Delta attributes available' to see what fields exist")

if __name__ == "__main__":
    asyncio.run(test_o3_mini_thinking())

