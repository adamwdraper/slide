#!/usr/bin/env python3
"""
Test the new execution observability API.
"""
import asyncio
from tyler import Agent, Thread, Message
from tyler.models.agent import EventType

async def test_non_streaming():
    """Test non-streaming mode with execution details."""
    print("\n=== Testing Non-Streaming Mode ===")
    
    # Create agent
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="To demonstrate execution observability",
        temperature=0.7
    )
    
    # Create thread
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello! What's 2+2?"))
    
    # Run agent and get detailed result
    result = await agent.run(thread)
    
    print(f"\nFinal output: {result.content}")
    print(f"Success: {result.success}")
    print(f"Total tokens: {result.execution.total_tokens}")
    print(f"Duration: {result.execution.duration_ms:.2f}ms")
    print(f"Total events: {len(result.execution.events)}")
    
    # Show event timeline
    print("\nEvent Timeline:")
    for event in result.execution.events:
        print(f"  {event.timestamp.strftime('%H:%M:%S.%f')[:-3]} - {event.type.value}")
        if event.type == EventType.LLM_RESPONSE:
            print(f"    Content: {event.data['content'][:50]}...")
            print(f"    Tokens: {event.data.get('tokens', {})}")

async def test_streaming():
    """Test streaming mode with real-time events."""
    print("\n\n=== Testing Streaming Mode ===")
    
    # Create agent with a tool
    def calculate(x: int, y: int, operation: str = "add") -> str:
        """Perform a calculation."""
        if operation == "add":
            return f"{x} + {y} = {x + y}"
        elif operation == "multiply":
            return f"{x} * {y} = {x * y}"
        return "Unknown operation"
    
    # Create custom tool
    calculator_tool = {
        "definition": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Perform mathematical calculations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "First number"},
                        "y": {"type": "integer", "description": "Second number"},
                        "operation": {
                            "type": "string",
                            "enum": ["add", "multiply"],
                            "description": "Operation to perform"
                        }
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "implementation": calculate
    }
    
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="To demonstrate streaming with tools",
        tools=[calculator_tool]
    )
    
    # Create thread
    thread = Thread()
    thread.add_message(Message(role="user", content="Calculate 15 times 7 for me"))
    
    # Stream events
    print("\nStreaming events:")
    content_buffer = []
    
    async for event in agent.stream(thread):
        # Show different event types
        if event.type == EventType.LLM_REQUEST:
            print(f"\n🤖 Starting LLM request (model: {event.data['model']})")
            
        elif event.type == EventType.LLM_STREAM_CHUNK:
            chunk = event.data["content_chunk"]
            content_buffer.append(chunk)
            print(chunk, end="", flush=True)
            
        elif event.type == EventType.LLM_RESPONSE:
            if content_buffer:
                print()  # New line after streaming
            print(f"✓ LLM response complete (tokens: {event.data.get('tokens', {})})")
            
        elif event.type == EventType.TOOL_SELECTED:
            print(f"\n🔧 Tool selected: {event.data['tool_name']}")
            print(f"   Arguments: {event.data['arguments']}")
            
        elif event.type == EventType.TOOL_RESULT:
            print(f"✓ Tool result: {event.data['result']}")
            
        elif event.type == EventType.MESSAGE_CREATED:
            msg = event.data["message"]
            if msg.role == "tool":
                print(f"\n📋 Tool message: {msg.content}")
                
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(f"\n✅ Execution complete!")
            print(f"   Duration: {event.data['duration_ms']:.2f}ms")
            print(f"   Total tokens: {event.data['total_tokens']}")

async def main():
    """Run all tests."""
    try:
        await test_non_streaming()
        await test_streaming()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
