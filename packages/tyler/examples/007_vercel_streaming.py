#!/usr/bin/env python
"""
Example: Vercel AI SDK Streaming
================================

This example demonstrates using Tyler's 'vercel' streaming mode to produce
output compatible with the Vercel AI SDK's useChat hook.

The Vercel AI SDK Data Stream Protocol uses Server-Sent Events (SSE) format
and is designed for building chat interfaces with React/Next.js frontends.

See: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol

Usage:
    python examples/007_vercel_streaming.py
    
To integrate with FastAPI:
    See the `create_fastapi_endpoint()` function below.
"""
# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio

from tyler import Agent, Thread, Message, VERCEL_STREAM_HEADERS


# Create agent
agent = Agent(
    name="vercel-streaming-assistant",
    model_name="gpt-4.1",
    purpose="To demonstrate Vercel AI SDK streaming.",
    temperature=0.7
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
    logger.info("Demo 1: Raw Vercel AI SDK Streaming")
    logger.info("=" * 60)
    await demo_vercel_streaming()
    
    logger.info("\n")
    logger.info("=" * 60)
    logger.info("Demo 2: Parsing Vercel Stream for Text")
    logger.info("=" * 60)
    await demo_with_parsing()
    
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
