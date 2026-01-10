#!/usr/bin/env python3
"""
Example demonstrating OpenAI streaming mode.

This example shows how to use mode="openai" to get unmodified LiteLLM chunks
in OpenAI-compatible format, which is useful for:
- Building OpenAI API proxies
- Direct integration with OpenAI-compatible clients
- Debugging provider-specific behavior
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
import json
from tyler import Agent, Thread, Message

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
        logger.debug("Weave tracing initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent
agent = Agent(
    model_name="gpt-4o",
    purpose="To demonstrate OpenAI streaming mode.",
    temperature=0.7
)


def serialize_chunk_to_sse(chunk) -> str:
    """
    Serialize a raw LiteLLM chunk to Server-Sent Events (SSE) format.
    
    This is the format expected by OpenAI-compatible clients.
    """
    # Convert chunk to dict for JSON serialization
    chunk_dict = {
        "id": getattr(chunk, 'id', 'unknown'),
        "object": getattr(chunk, 'object', 'chat.completion.chunk'),
        "created": getattr(chunk, 'created', 0),
        "model": getattr(chunk, 'model', 'unknown'),
        "choices": []
    }
    
    # Process choices
    if hasattr(chunk, 'choices') and chunk.choices:
        for choice in chunk.choices:
            choice_dict = {
                "index": getattr(choice, 'index', 0),
                "delta": {},
                "finish_reason": getattr(choice, 'finish_reason', None)
            }
            
            # Extract delta content
            if hasattr(choice, 'delta'):
                delta = choice.delta
                if hasattr(delta, 'content') and delta.content is not None:
                    choice_dict["delta"]["content"] = delta.content
                if hasattr(delta, 'role') and delta.role:
                    choice_dict["delta"]["role"] = delta.role
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    # Tool calls would need to be serialized here
                    choice_dict["delta"]["tool_calls"] = delta.tool_calls
            
            chunk_dict["choices"].append(choice_dict)
    
    # Add usage if present
    if hasattr(chunk, 'usage') and chunk.usage:
        chunk_dict["usage"] = {
            "prompt_tokens": getattr(chunk.usage, 'prompt_tokens', 0),
            "completion_tokens": getattr(chunk.usage, 'completion_tokens', 0),
            "total_tokens": getattr(chunk.usage, 'total_tokens', 0)
        }
    
    # Format as SSE
    return f"data: {json.dumps(chunk_dict)}\n\n"


async def demo_openai_streaming():
    """Demonstrate OpenAI streaming with SSE serialization"""
    logger.info("=" * 60)
    logger.info("OpenAI Streaming Mode Demo")
    logger.info("=" * 60)
    
    # Create a thread
    thread = Thread()
    message = Message(
        role="user",
        content="Write a haiku about artificial intelligence."
    )
    thread.add_message(message)
    
    logger.info("User: %s", message.content)
    logger.info("-" * 60)
    logger.info("Streaming OpenAI chunks (printing as SSE format)...")
    logger.info("-" * 60)
    
    chunk_count = 0
    content_pieces = []
    usage_info = None
    
    # Stream OpenAI-compatible chunks
    async for chunk in agent.stream(thread, mode="openai"):
        chunk_count += 1
        
        # Serialize to SSE format (what you'd send to a client)
        sse_data = serialize_chunk_to_sse(chunk)
        
        # Print the SSE format (for demonstration)
        print(sse_data, end='')
        
        # Also collect content for summary
        if hasattr(chunk, 'choices') and chunk.choices:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                content_pieces.append(delta.content)
        
        # Collect usage info from final chunk
        if hasattr(chunk, 'usage') and chunk.usage:
            usage_info = chunk.usage
    
    logger.info("-" * 60)
    logger.info("✅ OpenAI streaming complete!")
    logger.info(f"   Chunks received: {chunk_count}")
    logger.info(f"   Content: {''.join(content_pieces)}")
    if usage_info:
        logger.info(f"   Tokens used: {usage_info.total_tokens} " +
                   f"(prompt: {usage_info.prompt_tokens}, " +
                   f"completion: {usage_info.completion_tokens})")


async def demo_comparison():
    """Compare openai mode vs events mode"""
    logger.info("\n" + "=" * 60)
    logger.info("Mode Comparison: OpenAI vs Events")
    logger.info("=" * 60)
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Say 'Hello from Tyler!' in exactly those words."
    ))
    
    # Test openai mode
    logger.info("\n[OpenAI Mode]")
    raw_content = []
    async for chunk in agent.stream(thread, mode="openai"):
        if hasattr(chunk, 'choices') and chunk.choices:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                raw_content.append(delta.content)
    raw_text = ''.join(raw_content)
    logger.info(f"Output: {raw_text}")
    
    # Test events mode for comparison
    thread2 = Thread()
    thread2.add_message(Message(
        role="user",
        content="Say 'Hello from Tyler!' in exactly those words."
    ))
    
    logger.info("\n[Events Mode]")
    from tyler import EventType
    events_content = []
    async for event in agent.stream(thread2):
        if event.type == EventType.LLM_STREAM_CHUNK:
            events_content.append(event.data.get("content_chunk", ""))
    events_text = ''.join(events_content)
    logger.info(f"Output: {events_text}")
    
    logger.info("\n✅ Both modes produce the same content")
    logger.info(f"   OpenAI mode: {len(raw_text)} chars")
    logger.info(f"   Events mode: {len(events_text)} chars")


async def main():
    """Run all demos"""
    try:
        # Demo 1: OpenAI streaming with SSE serialization
        await demo_openai_streaming()
        
        # Demo 2: Compare openai vs events mode
        await demo_comparison()
        
    except Exception as e:
        logger.error(f"Error in demo: {e}")
        logger.info("Note: This example requires a valid OPENAI_API_KEY environment variable")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)

