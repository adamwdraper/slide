#!/usr/bin/env python
"""
Example: Vercel AI SDK Streaming
================================

This example demonstrates Tyler's Vercel streaming modes:

- **vercel**: Yields SSE-formatted strings for HTTP streaming (React/Next.js)
- **vercel_objects**: Yields chunk dictionaries for frameworks like marimo

The Vercel AI SDK Data Stream Protocol uses Server-Sent Events (SSE) format
and is designed for building chat interfaces with React/Next.js frontends.

See: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol

Requirements:
    - WANDB_API_KEY: Required for W&B Inference (get from https://wandb.ai/authorize)
    - WANDB_PROJECT: Optional, for Weave tracing

Usage:
    export WANDB_API_KEY=your_api_key
    export WANDB_PROJECT=your_project  # optional
    python examples/007_vercel_streaming.py
    
To integrate with FastAPI:
    See the `create_fastapi_endpoint()` function below.
    
To integrate with marimo:
    See the `demo_vercel_objects()` function below.
"""
# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import os
import sys
import asyncio
import weave

from tyler import Agent, Thread, Message, VERCEL_STREAM_HEADERS

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


# Create agent using DeepSeek-R1 via W&B Inference
# This model actually streams back thinking/reasoning tokens
# See available models: https://docs.wandb.ai/inference/models
agent = Agent(
    name="vercel-streaming-assistant",
    model_name="openai/deepseek-ai/DeepSeek-R1-0528",
    base_url="https://api.inference.wandb.ai/v1",
    api_key=get_wandb_api_key(),
    purpose="To demonstrate Vercel AI SDK streaming with thinking tokens.",
    reasoning="low",
    temperature=0.7,
    drop_params=True
)


async def demo_vercel_streaming():
    """Demonstrate raw Vercel streaming output."""
    thread = Thread()
    message = Message(
        role="user",
        content="Write a haiku about programming."
    )
    thread.add_message(message)
    
    logger.info("User: %s", message.content)
    logger.info("Streaming in Vercel AI SDK format...")
    logger.info("-" * 50)
    
    # Stream in Vercel format
    async for sse_chunk in agent.stream(thread, mode="vercel"):
        # In production, you would yield this to an HTTP response
        # Here we just print it to show the raw SSE format
        print(sse_chunk, end="", flush=True)
    
    logger.info("-" * 50)
    logger.info("Streaming complete!")


async def demo_with_parsing():
    """Demonstrate parsing the Vercel stream to extract text."""
    import json
    
    thread = Thread()
    message = Message(
        role="user",
        content="What is 2 + 2? Answer briefly."
    )
    thread.add_message(message)
    
    logger.info("User: %s", message.content)
    logger.info("Extracting text from Vercel stream...")
    logger.info("-" * 50)
    
    content_parts = []
    
    async for sse_chunk in agent.stream(thread, mode="vercel"):
        # Parse the SSE format
        if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
            try:
                data = json.loads(sse_chunk[6:])
                
                if data.get("type") == "text-delta":
                    content_parts.append(data.get("delta", ""))
                    print(data.get("delta", ""), end="", flush=True)
                    
            except json.JSONDecodeError:
                # Skip malformed JSON chunks (e.g., partial SSE data)
                pass
    
    print()  # Newline
    logger.info("-" * 50)
    logger.info("Full response: %s", "".join(content_parts))


async def demo_vercel_objects():
    """Demonstrate vercel_objects mode for marimo integration.
    
    This mode yields chunk dictionaries directly (no SSE wrapping),
    which is what marimo's mo.ui.chat(vercel_messages=True) expects.
    """
    thread = Thread()
    message = Message(
        role="user",
        content="Say hello in exactly 3 words."
    )
    thread.add_message(message)
    
    logger.info("User: %s", message.content)
    logger.info("Streaming with vercel_objects mode (raw chunk dicts)...")
    logger.info("-" * 50)
    
    content_parts = []
    
    async for chunk in agent.stream(thread, mode="vercel_objects"):
        # chunk is a dict, not an SSE string
        chunk_type = chunk.get("type", "")
        
        if chunk_type == "text-delta":
            delta = chunk.get("delta", "")
            content_parts.append(delta)
            print(delta, end="", flush=True)
        elif chunk_type == "reasoning-delta":
            # Thinking/reasoning tokens
            delta = chunk.get("delta", "")
            print(f"[thinking: {delta}]", end="", flush=True)
        elif chunk_type in ("start", "finish", "start-step", "finish-step"):
            # Log protocol events for debugging
            logger.debug("Protocol event: %s", chunk)
    
    print()  # Newline
    logger.info("-" * 50)
    logger.info("Full response: %s", "".join(content_parts))
    
    # Show example marimo integration
    logger.info("\n")
    logger.info("Example marimo integration:")
    logger.info("""
    import marimo as mo
    from tyler import Agent, Thread, Message
    
    agent = Agent(name="assistant", model_name="gpt-4.1")
    
    async def model(messages, config):
        thread = Thread()
        for msg in messages:
            thread.add_message(Message(role=msg.role, content=msg.content))
        
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            yield chunk
    
    mo.ui.chat(model, vercel_messages=True)
    """)


def create_fastapi_endpoint():
    """
    Example of integrating with FastAPI.
    
    This creates an endpoint compatible with the Vercel AI SDK's useChat hook.
    
    Frontend usage with @ai-sdk/react:
    
        import { useChat } from '@ai-sdk/react';
        
        export default function Chat() {
            const { messages, sendMessage, input, setInput } = useChat({
                api: '/api/chat',  // Points to your Tyler backend
            });
            
            return (
                <div>
                    {messages.map(message => (
                        <div key={message.id}>
                            {message.role}: {message.parts.map((part, i) => 
                                part.type === 'text' ? <span key={i}>{part.text}</span> : null
                            )}
                        </div>
                    ))}
                    <form onSubmit={e => {
                        e.preventDefault();
                        sendMessage({ text: input });
                        setInput('');
                    }}>
                        <input 
                            value={input} 
                            onChange={e => setInput(e.target.value)} 
                        />
                    </form>
                </div>
            );
        }
    """
    # Import inside function since these are optional dependencies
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import StreamingResponse
    except ImportError:
        logger.warning("FastAPI not installed. Skipping FastAPI example.")
        return None
    
    app = FastAPI()
    
    @app.post("/api/chat")
    async def chat(request: Request):
        """Vercel AI SDK compatible chat endpoint."""
        body = await request.json()
        messages = body.get("messages", [])
        
        # Create thread from messages
        thread = Thread()
        for msg in messages:
            thread.add_message(Message(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))
        
        # Stream response
        async def generate():
            async for sse_chunk in agent.stream(thread, mode="vercel"):
                yield sse_chunk
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers=VERCEL_STREAM_HEADERS
        )
    
    return app


async def main():
    logger.info("=" * 60)
    logger.info("Demo 1: Raw Vercel AI SDK Streaming (SSE strings)")
    logger.info("=" * 60)
    await demo_vercel_streaming()
    
    logger.info("\n")
    logger.info("=" * 60)
    logger.info("Demo 2: Parsing Vercel Stream for Text")
    logger.info("=" * 60)
    await demo_with_parsing()
    
    logger.info("\n")
    logger.info("=" * 60)
    logger.info("Demo 3: Vercel Objects Mode (for marimo, etc.)")
    logger.info("=" * 60)
    await demo_vercel_objects()
    
    logger.info("\n")
    logger.info("=" * 60)
    logger.info("FastAPI Integration Example")
    logger.info("=" * 60)
    app = create_fastapi_endpoint()
    if app:
        logger.info("FastAPI app created successfully!")
        logger.info("Run with: uvicorn examples.007_vercel_streaming:app --reload")
        logger.info("Then connect your React frontend using @ai-sdk/react")
    else:
        logger.info("Install FastAPI to use the API endpoint example:")
        logger.info("  pip install fastapi uvicorn")


if __name__ == "__main__":
    asyncio.run(main())


# Export the FastAPI app for uvicorn
app = create_fastapi_endpoint()
