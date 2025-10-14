"""
Simple test for thinking tokens using DeepSeek (easiest to set up).

Usage:
  export DEEPSEEK_API_KEY=sk-your-key
  uv run python test_thinking_simple.py
"""
import asyncio
import os
from tyler import Agent, Thread, Message, EventType

async def test():
    # Check for API key
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not set")
        print("\nGet a free key from: https://platform.deepseek.com/")
        print("Then run: export DEEPSEEK_API_KEY=sk-your-key")
        return
    
    print(f"✅ DeepSeek API Key: {api_key[:10]}...\n")
    
    # Create agent with DeepSeek
    agent = Agent(
        name="thinking-test",
        model_name="deepseek/deepseek-chat",
        temperature=0.7,
        reasoning_effort="low"  # Enable thinking!
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What is 17 * 23? Show your thinking process step by step."
    ))
    
    print("🚀 Streaming response with thinking tokens...\n")
    print("="*70)
    
    thinking_count = 0
    content_count = 0
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            thinking_count += 1
            thinking = event.data['thinking_chunk']
            thinking_type = event.data['thinking_type']
            print(f"\n💭 [{thinking_type.upper()}] {thinking}")
        
        elif event.type == EventType.LLM_STREAM_CHUNK:
            content_count += 1
            print(event.data['content_chunk'], end="", flush=True)
        
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(f"\n\n{'='*70}")
            print(f"\n📊 Results:")
            print(f"   Thinking chunks: {thinking_count}")
            print(f"   Content chunks: {content_count}")
            
            if thinking_count > 0:
                print(f"\n🎉 SUCCESS! Thinking tokens are working!")
                print(f"   You should see the same in tyler chat CLI")
            else:
                print(f"\n⚠️  No thinking tokens detected")

if __name__ == "__main__":
    print("\n" + "="*70)
    print(" THINKING TOKENS TEST - DeepSeek")
    print("="*70 + "\n")
    
    asyncio.run(test())

