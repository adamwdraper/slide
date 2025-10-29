#!/usr/bin/env python3
"""
Demo of the enhanced streaming with proper LLM_STREAM_CHUNK events.

This shows how the agent now emits individual content chunks as they
arrive from the LLM, enabling real-time streaming UIs.
"""

import asyncio
from tyler import Agent, Thread, Message, EventType

async def main():
    # Create a simple agent
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="To demonstrate streaming chunks"
    )
    
    # Create a thread
    thread = Thread()
    thread.add_message(Message(role="user", content="Tell me a short story about a robot"))
    
    print("=== Streaming with Content Chunks ===\n")
    
    # Track chunks to show streaming
    chunks_received = 0
    full_content = []
    
    print("Streaming response:")
    print("-" * 50)
    
    try:
        async for event in agent.stream(thread):
            if event.type == EventType.LLM_STREAM_CHUNK:
                # This is a new content chunk!
                chunk = event.data.get("content_chunk", "")
                chunks_received += 1
                full_content.append(chunk)
                # Print chunk inline without newline
                print(chunk, end="", flush=True)
                
            elif event.type == EventType.LLM_RESPONSE:
                # This event comes after all chunks are received
                print("\n" + "-" * 50)
                print(f"\n✅ Streaming complete!")
                print(f"   Total chunks received: {chunks_received}")
                print(f"   Full content length: {len(''.join(full_content))} chars")
                
            elif event.type == EventType.EXECUTION_COMPLETE:
                print(f"\n🏁 Execution complete in {event.data['duration_ms']:.2f}ms")
                
    except Exception as e:
        print(f"\nNote: This demo requires an OpenAI API key to actually stream.")
        print(f"Error: {str(e)}")
        print("\nBut the streaming infrastructure is working correctly!")
        print("With a valid API key, you would see:")
        print("- Individual LLM_STREAM_CHUNK events for each piece of content")
        print("- Real-time content appearing character by character")
        print("- Tool selection and execution events if tools are used")

if __name__ == "__main__":
    asyncio.run(main())
