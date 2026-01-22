#!/usr/bin/env python3
"""
Example demonstrating thinking tokens (reasoning) streaming.

This example shows how to:
1. Enable thinking tokens with the reasoning parameter
2. Stream both thinking and content separately
3. Use DeepSeek-R1 via W&B Inference (which actually returns thinking tokens)
4. Compare responses with and without thinking tokens

Thinking tokens allow you to see the model's internal reasoning process
before it generates its final answer.

Requirements:
    - WANDB_API_KEY: Required for W&B Inference (get from https://wandb.ai/authorize)
    - WANDB_PROJECT: Optional, for Weave tracing

Usage:
    export WANDB_API_KEY=your_api_key
    export WANDB_PROJECT=your_project  # optional
    python examples/006_thinking_tokens.py
"""
# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import os
import asyncio
import weave
import sys
from tyler import Agent, Thread, Message, EventType

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
        logger.debug("Weave tracing initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


def get_wandb_api_key() -> str:
    """Get W&B API key from environment, or exit with instructions."""
    api_key = os.getenv("WANDB_API_KEY")
    if not api_key:
        logger.error("WANDB_API_KEY not set!")
        logger.error("To use this example, you need a W&B API key:")
        logger.error("  1. Get your API key from: https://wandb.ai/authorize")
        logger.error("  2. Set it: export WANDB_API_KEY=your_api_key")
        sys.exit(1)
    return api_key


def create_deepseek_agent(purpose: str, reasoning: str = "low") -> Agent:
    """Create an agent using DeepSeek-R1 via W&B Inference.
    
    DeepSeek-R1 actually returns thinking tokens in the streaming response,
    unlike GPT models which do reasoning internally.
    
    See available models: https://docs.wandb.ai/inference/models
    """
    return Agent(
        model_name="openai/deepseek-ai/DeepSeek-R1-0528",
        base_url="https://api.inference.wandb.ai/v1",
        api_key=get_wandb_api_key(),
        purpose=purpose,
        reasoning=reasoning,
        temperature=0.7,
        drop_params=True
    )


async def demo_thinking_tokens_basic():
    """Basic example: Stream thinking tokens and content separately"""
    logger.info("=" * 70)
    logger.info("Demo 1: Basic Thinking Tokens Streaming")
    logger.info("=" * 70)
    
    # Create agent with thinking tokens enabled using DeepSeek-R1 via W&B Inference
    # DeepSeek-R1 actually streams back reasoning_content, unlike GPT models
    agent = create_deepseek_agent(
        purpose="To demonstrate thinking tokens streaming.",
        reasoning="low"  # Options: "low", "medium", "high"
    )
    
    # Create a thread with a problem that benefits from reasoning
    thread = Thread()
    message = Message(
        role="user",
        content="What is 47 * 89? Please show your reasoning step by step."
    )
    thread.add_message(message)
    
    logger.info("User: %s", message.content)
    logger.info("-" * 70)
    
    thinking_buffer = []
    content_buffer = []
    
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_THINKING_CHUNK:
            # Capture reasoning/thinking tokens
            chunk = event.data.get("thinking_chunk", "")
            thinking_buffer.append(chunk)
            print(f"\033[90m{chunk}\033[0m", end="", flush=True)  # Gray text for thinking
            
        elif event.type == EventType.LLM_STREAM_CHUNK:
            # Capture final content
            chunk = event.data.get("content_chunk", "")
            content_buffer.append(chunk)
            print(chunk, end="", flush=True)
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            print()  # New line
            logger.info("-" * 70)
            logger.info("✅ Complete!")
            logger.info(f"   Thinking tokens: {len(''.join(thinking_buffer))} chars")
            logger.info(f"   Content: {len(''.join(content_buffer))} chars")
            logger.info(f"   Total time: {event.data.get('duration_ms', 0):.2f}ms")


async def demo_reasoning_levels():
    """Compare different reasoning levels"""
    logger.info("\n" + "=" * 70)
    logger.info("Demo 2: Reasoning Levels")
    logger.info("=" * 70)
    
    problem = "A farmer has 17 sheep. All but 9 die. How many are left?"
    
    for level in ["low", "medium", "high"]:
        logger.info(f"\n--- Testing reasoning='{level}' ---")
        
        agent = create_deepseek_agent(
            purpose="To test reasoning levels",
            reasoning=level
        )
        
        thread = Thread()
        thread.add_message(Message(role="user", content=problem))
        
        thinking_tokens = 0
        content_tokens = 0
        
        async for event in agent.stream(thread):
            if event.type == EventType.LLM_THINKING_CHUNK:
                thinking_tokens += len(event.data.get("thinking_chunk", ""))
            elif event.type == EventType.LLM_STREAM_CHUNK:
                content_tokens += len(event.data.get("content_chunk", ""))
                print(event.data.get("content_chunk", ""), end="", flush=True)
            elif event.type == EventType.EXECUTION_COMPLETE:
                print()
                logger.info(f"   Thinking: {thinking_tokens} chars | Content: {content_tokens} chars")


async def demo_comparison():
    """Compare with and without thinking tokens"""
    logger.info("\n" + "=" * 70)
    logger.info("Demo 3: With vs Without Thinking Tokens")
    logger.info("=" * 70)
    
    problem = "If you have 8 coins and I have 5 coins, and you give me 3 coins, who has more?"
    
    # Without thinking tokens - use a non-reasoning model
    logger.info("\n[WITHOUT thinking tokens - using Llama 3.3]")
    agent_no_thinking = Agent(
        model_name="openai/meta-llama/Llama-3.3-70B-Instruct",
        base_url="https://api.inference.wandb.ai/v1",
        api_key=get_wandb_api_key(),
        purpose="Standard response",
        temperature=0.7,
        drop_params=True
    )
    
    thread1 = Thread()
    thread1.add_message(Message(role="user", content=problem))
    
    async for event in agent_no_thinking.stream(thread1):
        if event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type == EventType.EXECUTION_COMPLETE:
            print("\n")
    
    # With thinking tokens - use DeepSeek-R1
    logger.info("[WITH thinking tokens (DeepSeek-R1, reasoning='medium')]")
    agent_with_thinking = create_deepseek_agent(
        purpose="Response with reasoning",
        reasoning="medium"
    )
    
    thread2 = Thread()
    thread2.add_message(Message(role="user", content=problem))
    
    has_thinking = False
    async for event in agent_with_thinking.stream(thread2):
        if event.type == EventType.LLM_THINKING_CHUNK:
            if not has_thinking:
                logger.info("💭 Thinking process:")
                has_thinking = True
            print(f"   {event.data.get('thinking_chunk', '')}", end="", flush=True)
        elif event.type == EventType.LLM_STREAM_CHUNK:
            if has_thinking:
                print("\n\n📝 Final answer:")
                has_thinking = False
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type == EventType.EXECUTION_COMPLETE:
            print("\n")


async def demo_wandb_inference():
    """Example using W&B Inference with DeepSeek-R1 (thinking model)
    
    This demo shows a more complex math problem to really exercise the
    thinking capabilities of DeepSeek-R1.
    """
    logger.info("\n" + "=" * 70)
    logger.info("Demo 4: Complex Problem with DeepSeek-R1")
    logger.info("=" * 70)
    
    logger.info("Using W&B Inference with DeepSeek-R1-0528...")
    
    # Create agent configured for W&B Inference
    agent = create_deepseek_agent(
        purpose="To demonstrate W&B Inference with thinking tokens",
        reasoning="low"
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Calculate 123 × 456. Show your work."
    ))
    
    logger.info("Question: Calculate 123 × 456. Show your work.")
    logger.info("-" * 70)
    
    thinking_chars = 0
    content_chars = 0
    
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_THINKING_CHUNK:
            thinking_chars += len(event.data.get("thinking_chunk", ""))
            # Show abbreviated thinking (first 50 chars of each chunk)
            chunk = event.data.get("thinking_chunk", "")[:50]
            if chunk:
                print(f"\033[90m{chunk}...\033[0m", end="\r", flush=True)
            
        elif event.type == EventType.LLM_STREAM_CHUNK:
            # Clear the thinking line and show content
            if thinking_chars > 0 and content_chars == 0:
                print(" " * 70, end="\r")  # Clear line
                print()
            content_chars += len(event.data.get("content_chunk", ""))
            print(event.data.get("content_chunk", ""), end="", flush=True)
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            print()
            logger.info("-" * 70)
            logger.info(f"✅ W&B Inference complete!")
            logger.info(f"   Thinking: {thinking_chars} chars")
            logger.info(f"   Content: {content_chars} chars")


async def demo_all_events():
    """Show all thinking-related events in detail"""
    logger.info("\n" + "=" * 70)
    logger.info("Demo 5: All Thinking-Related Events")
    logger.info("=" * 70)
    
    agent = create_deepseek_agent(
        purpose="To show all event types",
        reasoning="low"
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What is 2+2?"
    ))
    
    logger.info("Streaming all events...")
    logger.info("-" * 70)
    
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_REQUEST:
            logger.info(f"🔵 LLM_REQUEST: model={event.data.get('model')}")
            
        elif event.type == EventType.LLM_THINKING_CHUNK:
            chunk = event.data.get("thinking_chunk", "")
            logger.info(f"💭 LLM_THINKING_CHUNK: {len(chunk)} chars")
            
        elif event.type == EventType.LLM_STREAM_CHUNK:
            chunk = event.data.get("content_chunk", "")
            logger.info(f"📝 LLM_STREAM_CHUNK: {len(chunk)} chars - '{chunk}'")
            
        elif event.type == EventType.LLM_RESPONSE:
            logger.info(f"✅ LLM_RESPONSE: tokens={event.data.get('tokens', {}).get('total_tokens', 0)}")
            
        elif event.type == EventType.MESSAGE_CREATED:
            msg = event.data.get("message")
            logger.info(f"📨 MESSAGE_CREATED: role={msg.role if msg else 'unknown'}")
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            logger.info(f"🏁 EXECUTION_COMPLETE: duration={event.data.get('duration_ms', 0):.2f}ms")
    
    logger.info("-" * 70)


async def main():
    """Run all demos"""
    try:
        # Demo 1: Basic thinking tokens streaming
        await demo_thinking_tokens_basic()
        
        # Demo 2: Different reasoning levels
        await demo_reasoning_levels()
        
        # Demo 3: Compare with and without thinking
        await demo_comparison()
        
        # Demo 4: W&B Inference with DeepSeek-R1
        await demo_wandb_inference()
        
        # Demo 5: All events in detail
        await demo_all_events()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ All demos complete!")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Error in demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)

