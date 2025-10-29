#!/usr/bin/env python3
"""
Demonstrate the new execution observability API features.
This example shows how to use both streaming and non-streaming modes
to get detailed insights into agent execution.
"""
import asyncio
from tyler import Agent, Thread, Message
from tyler.models.agent import EventType

# Example 1: Basic non-streaming usage
async def basic_usage():
    """Shows the simplest way to use the new API."""
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="To be a helpful assistant"
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello!"))
    
    # Simple usage - just get the output
    result = await agent.go(thread)
    print(f"Response: {result.content}")
    
    # But you also have access to detailed execution info
    print(f"Took {result.execution.duration_ms:.2f}ms")
    print(f"Used {result.execution.total_tokens} tokens")

# Example 2: Detailed monitoring
async def monitoring_example():
    """Shows how to use execution details for monitoring."""
    agent = Agent(model_name="gpt-4o-mini")
    
    thread = Thread() 
    thread.add_message(Message(role="user", content="Explain quantum computing"))
    
    result = await agent.go(thread)
    
    # Access detailed metrics
    print("\n=== Execution Metrics ===")
    print(f"Duration: {result.execution.duration_ms:.2f}ms")
    print(f"Total tokens: {result.execution.total_tokens}")
    print(f"Success: {result.success}")
    
    # Analyze tool usage
    print(f"\nTool calls: {len(result.execution.tool_calls)}")
    for tool_call in result.execution.tool_calls:
        print(f"  - {tool_call.tool_name}: {tool_call.duration_ms:.2f}ms")
        if not tool_call.success:
            print(f"    Error: {tool_call.error}")
    
    # Event timeline
    print(f"\nTotal events: {len(result.execution.events)}")
    for event in result.execution.events:
        if event.type == EventType.LLM_RESPONSE:
            tokens = event.data.get("tokens", {})
            print(f"  LLM Response: {tokens.get('total_tokens', 0)} tokens")

# Example 3: Real-time streaming UI
async def streaming_ui_example():
    """Shows how to build a responsive UI with streaming."""
    agent = Agent(model_name="gpt-4o-mini")
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Write a haiku about coding"))
    
    print("\n=== Streaming Response ===")
    async for event in agent.stream(thread):
        if event.type == EventType.LLM_STREAM_CHUNK:
            # Show content as it arrives
            print(event.data["content_chunk"], end="", flush=True)
            
        elif event.type == EventType.TOOL_SELECTED:
            # Show tool usage in UI
            print(f"\n🔧 Using {event.data['tool_name']}...")
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            # Show final stats
            print(f"\n\n✓ Complete in {event.data['duration_ms']:.0f}ms")

# Example 4: Error handling and debugging
async def debugging_example():
    """Shows how to use execution details for debugging."""
    agent = Agent(model_name="gpt-4o-mini")
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Do something complex"))
    
    result = await agent.go(thread)
    
    if not result.success:
        print("\n=== Debugging Failed Execution ===")
        # Find what went wrong
        for event in result.execution.events:
            if event.type == EventType.EXECUTION_ERROR:
                print(f"Error: {event.data['message']}")
                print(f"Type: {event.data['error_type']}")
                print(f"Time: {event.timestamp}")
    
    # Analyze slow operations
    print("\n=== Performance Analysis ===")
    llm_events = [e for e in result.execution.events if e.type == EventType.LLM_RESPONSE]
    for event in llm_events:
        latency = event.data.get("latency_ms", 0)
        if latency > 1000:  # Flag slow responses
            print(f"⚠️  Slow LLM response: {latency:.0f}ms")

# Example 5: Custom event processing
async def custom_processing_example():
    """Shows how to process events for custom analytics."""
    agent = Agent(model_name="gpt-4o-mini")
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Help me plan a trip"))
    
    # Collect custom metrics during streaming
    metrics = {
        "chunks_received": 0,
        "tools_used": set(),
        "messages_created": 0
    }
    
    async for event in agent.stream(thread):
        # Update metrics based on event type
        if event.type == EventType.LLM_STREAM_CHUNK:
            metrics["chunks_received"] += 1
            
        elif event.type == EventType.TOOL_SELECTED:
            metrics["tools_used"].add(event.data["tool_name"])
            
        elif event.type == EventType.MESSAGE_CREATED:
            metrics["messages_created"] += 1
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            # Log final metrics
            print(f"\n=== Custom Metrics ===")
            print(f"Chunks streamed: {metrics['chunks_received']}")
            print(f"Unique tools used: {len(metrics['tools_used'])}")
            print(f"Messages created: {metrics['messages_created']}")

def main():
    """Run examples (would need proper API keys to actually execute)."""
    print("This demo shows the execution observability API patterns.")
    print("To run with actual LLM calls, set OPENAI_API_KEY environment variable.")
    print("\nKey features demonstrated:")
    print("- AgentResult object with execution details")
    print("- Streaming ExecutionEvent objects") 
    print("- Token tracking and performance metrics")
    print("- Tool call monitoring")
    print("- Error debugging capabilities")
    print("- Custom event processing")

if __name__ == "__main__":
    main()
