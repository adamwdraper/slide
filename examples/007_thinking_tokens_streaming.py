"""
Example: Thinking Tokens in Streaming

Demonstrates how to access and display model reasoning/thinking tokens separately
from response content when using reasoning-capable models like OpenAI o1 or
Anthropic Claude.

Requires LiteLLM >= 1.63.0 and a reasoning-capable model.
"""

import asyncio
import logging
from tyler import Agent, Thread, Message, EventType

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def demo_thinking_with_anthropic():
    """
    Demo thinking tokens with Anthropic Claude (extended thinking).
    
    Requires: ANTHROPIC_API_KEY environment variable
    """
    logger.info("\n" + "="*70)
    logger.info("Demo: Thinking Tokens with Anthropic Claude")
    logger.info("="*70)
    
    # Create agent with reasoning-capable model
    agent = Agent(
        name="thinking-agent",
        model_name="anthropic/claude-3-7-sonnet-20250219",
        purpose="To demonstrate thinking tokens",
        temperature=0.7,
        reasoning="low"  # Enable thinking tokens
    )
    
    # Create a thread with a question that benefits from reasoning
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What's 137 * 284? Please show your thinking process."
    ))
    
    logger.info("\n💭 Thinking Process:")
    logger.info("-" * 70)
    
    thinking_buffer = []
    content_buffer = []
    
    # Stream with event mode to see thinking separately
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            # Thinking/reasoning tokens
            thinking = event.data['thinking_chunk']
            thinking_type = event.data['thinking_type']
            thinking_buffer.append(thinking)
            
            # Display thinking in a different style
            logger.info(f"[{thinking_type.upper()}] {thinking}")
        
        elif event.type == EventType.LLM_STREAM_CHUNK:
            # Regular response content
            content = event.data['content_chunk']
            content_buffer.append(content)
            print(content, end="", flush=True)
        
        elif event.type == EventType.MESSAGE_CREATED:
            msg = event.data['message']
            if msg.role == "assistant":
                # Check if reasoning was stored (top-level field)
                if msg.reasoning_content:
                    logger.info("\n\n✅ Reasoning stored in message")
                    logger.info(f"   Length: {len(msg.reasoning_content)} chars")
    
    logger.info("\n" + "="*70)
    logger.info(f"📊 Summary:")
    logger.info(f"   Thinking chunks: {len(thinking_buffer)}")
    logger.info(f"   Content chunks: {len(content_buffer)}")
    logger.info(f"   Total thinking: {sum(len(t) for t in thinking_buffer)} chars")
    logger.info(f"   Total content: {sum(len(c) for c in content_buffer)} chars")


async def demo_thinking_with_openai_o1():
    """
    Demo thinking tokens with OpenAI o1 (reasoning_content).
    
    Requires: OPENAI_API_KEY environment variable
    Note: o1 models automatically use reasoning, no special parameter needed
    """
    logger.info("\n" + "="*70)
    logger.info("Demo: Thinking Tokens with OpenAI o1")
    logger.info("="*70)
    
    agent = Agent(
        name="o1-agent",
        model_name="o1-preview",  # or "o1-mini"
        purpose="To demonstrate thinking with o1"
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Explain the solution to: If 5 machines take 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?"
    ))
    
    logger.info("\n🧠 o1 Reasoning:")
    logger.info("-" * 70)
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            reasoning = event.data['thinking_chunk']
            logger.info(f"[REASONING] {reasoning}")
        
        elif event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data['content_chunk'], end="", flush=True)
        
        elif event.type == EventType.EXECUTION_COMPLETE:
            logger.info("\n\n✅ Complete!")


async def demo_without_thinking_tokens():
    """
    Demo that non-reasoning models work unchanged (no thinking events).
    """
    logger.info("\n" + "="*70)
    logger.info("Demo: Regular Model (No Thinking Tokens)")
    logger.info("="*70)
    
    agent = Agent(
        name="regular-agent",
        model_name="gpt-4o",
        purpose="Regular chat without thinking tokens"
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Hello! How are you?"
    ))
    
    logger.info("\n💬 Response:")
    logger.info("-" * 70)
    
    thinking_count = 0
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            thinking_count += 1
        
        elif event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data['content_chunk'], end="", flush=True)
        
        elif event.type == EventType.EXECUTION_COMPLETE:
            logger.info(f"\n\n✅ Complete! Thinking events: {thinking_count} (expected: 0)")


async def demo_raw_streaming_with_thinking():
    """
    Demo raw streaming mode - thinking fields passed through unchanged.
    """
    logger.info("\n" + "="*70)
    logger.info("Demo: Raw Streaming (OpenAI Compatible)")
    logger.info("="*70)
    
    agent = Agent(
        name="raw-agent",
        model_name="anthropic/claude-3-7-sonnet-20250219"
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Count to 3."))
    
    logger.info("\nRaw chunks (showing structure):\n")
    
    chunk_count = 0
    async for chunk in agent.go(thread, stream="raw"):
        chunk_count += 1
        
        if hasattr(chunk, 'choices') and chunk.choices:
            delta = chunk.choices[0].delta
            
            # Raw mode preserves all fields
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                logger.info(f"Chunk {chunk_count}: reasoning_content = '{delta.reasoning_content}'")
            
            if hasattr(delta, 'thinking') and delta.thinking:
                logger.info(f"Chunk {chunk_count}: thinking = '{delta.thinking}'")
            
            if hasattr(delta, 'content') and delta.content:
                logger.info(f"Chunk {chunk_count}: content = '{delta.content}'")
    
    logger.info(f"\n✅ Total chunks: {chunk_count}")
    logger.info("   (Raw mode passes all fields through unchanged)")


async def demo_thinking_with_ui_separation():
    """
    Demo: Practical UI pattern - show thinking in collapsible section.
    """
    logger.info("\n" + "="*70)
    logger.info("Demo: UI Pattern - Separated Thinking Display")
    logger.info("="*70)
    
    agent = Agent(
        name="ui-agent",
        model_name="anthropic/claude-3-7-sonnet-20250219"
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Should I invest in stock A or stock B? A has P/E of 15, B has P/E of 25. B has 20% higher growth."
    ))
    
    # Simulate UI sections
    thinking_section = []
    response_section = []
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            thinking_section.append(event.data['thinking_chunk'])
        
        elif event.type == EventType.LLM_STREAM_CHUNK:
            response_section.append(event.data['content_chunk'])
    
    # Display as UI would
    if thinking_section:
        logger.info("\n📊 [Thinking Process] (collapsible section)")
        logger.info("─" * 70)
        logger.info(''.join(thinking_section))
        logger.info("─" * 70)
    
    logger.info("\n💬 [Response]")
    logger.info("─" * 70)
    logger.info(''.join(response_section))
    logger.info("─" * 70)
    
    logger.info("\n✅ Clean separation for UI display!")


async def main():
    """Run all demos"""
    # Uncomment the demo you want to run
    # Note: Some require API keys
    
    # await demo_thinking_with_anthropic()  # Requires ANTHROPIC_API_KEY
    # await demo_thinking_with_openai_o1()  # Requires OPENAI_API_KEY
    await demo_without_thinking_tokens()  # Works with any OpenAI-compatible model
    # await demo_raw_streaming_with_thinking()  # Raw mode demo
    # await demo_thinking_with_ui_separation()  # UI pattern demo
    
    logger.info("\n" + "="*70)
    logger.info("💡 Tip: Thinking tokens help build transparent AI applications!")
    logger.info("   Users can see how the model arrived at its answer.")
    logger.info("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

