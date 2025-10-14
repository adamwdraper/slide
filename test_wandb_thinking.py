"""
Test thinking tokens with W&B Inference DeepSeek model.

This script bypasses the CLI to test if thinking tokens work with
W&B Inference endpoint directly.
"""
import asyncio
import os
from dotenv import load_dotenv
from tyler import Agent, Thread, Message, EventType

# Load .env from packages/tyler/.env
load_dotenv('packages/tyler/.env')

async def test_wandb_inference_thinking():
    """Test thinking tokens with W&B Inference DeepSeek model."""
    
    # Get API key
    api_key = os.getenv('WANDB_API_KEY')
    if not api_key:
        print("❌ WANDB_API_KEY not found in environment")
        print("   Check packages/tyler/.env or set manually")
        return
    
    print(f"✅ WANDB_API_KEY loaded: {api_key[:10]}...")
    
    # Create agent with W&B Inference endpoint
    print("\n📦 Creating agent with W&B Inference...")
    # W&B Inference is OpenAI-compatible, so use openai/ prefix
    # The actual model is specified in the base_url endpoint
    agent = Agent(
        name="wandb-thinking-test",
        model_name="openai/deepseek-ai/DeepSeek-R1-0528",  # OpenAI-compatible format
        base_url="https://api.wandb.ai/api/v1/inference/wandb-designers/slide",
        extra_headers={
            "Authorization": f"Bearer {api_key}"
        },
        purpose="To test thinking tokens",
        temperature=0.7,
        reasoning_effort="low",  # Enable thinking tokens!
        drop_params=False  # Keep all params for W&B
    )
    
    # Create thread
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What is 15 * 23? Please show your thinking step by step."
    ))
    
    print("\n🚀 Streaming response...\n")
    print("="*70)
    
    thinking_chunks = []
    content_chunks = []
    all_events = []
    
    # Stream and collect events
    try:
        async for event in agent.go(thread, stream=True):
            all_events.append(event.type.value)
            
            if event.type == EventType.LLM_THINKING_CHUNK:
                thinking = event.data['thinking_chunk']
                thinking_type = event.data['thinking_type']
                thinking_chunks.append(thinking)
                print(f"💭 [{thinking_type.upper()}] {thinking}")
            
            elif event.type == EventType.LLM_STREAM_CHUNK:
                content = event.data['content_chunk']
                content_chunks.append(content)
                print(content, end="", flush=True)
            
            elif event.type == EventType.LLM_REQUEST:
                print(f"📤 LLM Request: model={event.data.get('model')}")
            
            elif event.type == EventType.LLM_RESPONSE:
                print("\n\n📥 LLM Response complete")
                tokens = event.data.get('tokens', {})
                print(f"   Tokens: {tokens.get('total_tokens', 'N/A')}")
            
            elif event.type == EventType.EXECUTION_COMPLETE:
                duration = event.data.get('duration_ms', 0)
                print(f"\n✅ Execution complete in {duration:.0f}ms")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Summary
    print("\n" + "="*70)
    print("\n📊 RESULTS:")
    print(f"   Thinking chunks: {len(thinking_chunks)}")
    print(f"   Content chunks: {len(content_chunks)}")
    print(f"   Event types: {set(all_events)}")
    
    if thinking_chunks:
        print("\n✅ SUCCESS! Thinking tokens detected:")
        print(f"   Total thinking: {sum(len(t) for t in thinking_chunks)} chars")
        print(f"   First thinking: {thinking_chunks[0][:100]}...")
    else:
        print("\n⚠️  No thinking tokens detected")
        print("   This could mean:")
        print("   1. Model doesn't support thinking in streaming")
        print("   2. reasoning_effort parameter not working")
        print("   3. W&B Inference endpoint issue")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(test_wandb_inference_thinking())

