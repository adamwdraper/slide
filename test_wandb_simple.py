"""
Simple test to verify W&B Inference works, then add thinking.
"""
import asyncio
import os
from dotenv import load_dotenv
from tyler import Agent, Thread, Message, EventType

load_dotenv('packages/tyler/.env')

async def test_basic():
    """Test basic W&B Inference without thinking first."""
    api_key = os.getenv('WANDB_API_KEY')
    print(f"✅ API Key: {api_key[:10]}...")
    
    # Test 1: Basic response (no thinking parameters)
    print("\n=== Test 1: Basic W&B Inference ===")
    agent = Agent(
        name="test",
        model_name="openai/deepseek-ai/DeepSeek-R1-0528",
        base_url="https://api.wandb.ai/api/v1/inference/wandb-designers/slide",
        extra_headers={"Authorization": f"Bearer {api_key}"},
        temperature=0.7,
        drop_params=True  # Drop unsupported params
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="What is 2+2?"))
    
    try:
        content = []
        async for event in agent.go(thread, stream=True):
            if event.type == EventType.LLM_STREAM_CHUNK:
                content.append(event.data['content_chunk'])
                print(event.data['content_chunk'], end="", flush=True)
        
        print(f"\n✅ Basic streaming works! Got {len(content)} chunks")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    # Test 2: With reasoning_effort
    print("\n\n=== Test 2: With reasoning_effort ===")
    agent2 = Agent(
        name="test2",
        model_name="openai/deepseek-ai/DeepSeek-R1-0528",
        base_url="https://api.wandb.ai/api/v1/inference/wandb-designers/slide",
        extra_headers={"Authorization": f"Bearer {api_key}"},
        temperature=0.7,
        reasoning_effort="low",  # Add this
        drop_params=True
    )
    
    thread2 = Thread()
    thread2.add_message(Message(role="user", content="What is 3+3? Show thinking."))
    
    try:
        thinking = []
        content = []
        async for event in agent2.go(thread2, stream=True):
            if event.type == EventType.LLM_THINKING_CHUNK:
                thinking.append(event.data['thinking_chunk'])
                print(f"💭 {event.data['thinking_chunk']}")
            elif event.type == EventType.LLM_STREAM_CHUNK:
                content.append(event.data['content_chunk'])
                print(event.data['content_chunk'], end="", flush=True)
        
        print(f"\n\n✅ Thinking chunks: {len(thinking)}")
        print(f"✅ Content chunks: {len(content)}")
        
        if thinking:
            print("\n🎉 THINKING TOKENS WORKING!")
        else:
            print("\n⚠️  No thinking tokens (might need different parameter)")
    
    except Exception as e:
        print(f"\n❌ Error with reasoning: {e}")

if __name__ == "__main__":
    asyncio.run(test_basic())

