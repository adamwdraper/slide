#!/usr/bin/env python3
"""
Demo of the new Agent Execution Observability features in Tyler.

This example shows how to use the new API to get detailed insights
into what your agent is doing, including:
- LLM requests and responses
- Tool usage and results
- Token consumption
- Execution timing
"""

import asyncio
from tyler import Agent, Thread, Message, EventType

async def main():
    # Create an agent with a simple calculator tool
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression."""
        try:
            result = eval(expression, {"__builtins__": {}})
            return f"The result is: {result}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="To help users with calculations",
        tools=[{
            "definition": {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Evaluate a mathematical expression",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "The mathematical expression to evaluate"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            "implementation": calculate
        }]
    )
    
    # Create a thread with a user message
    thread = Thread()
    thread.add_message(Message(role="user", content="What's 25 * 4 + 10?"))
    
    print("=== Non-Streaming Mode ===\n")
    
    # Execute in non-streaming mode
    result = await agent.go(thread)
    
    print(f"Final response: {result.content}")
    print(f"\nExecution details:")
    print(f"- Duration: {result.execution.duration_ms:.2f}ms")
    print(f"- Total tokens: {result.execution.total_tokens}")
    print(f"- Tool calls: {len(result.execution.tool_calls)}")
    
    if result.execution.tool_calls:
        for tool_call in result.execution.tool_calls:
            print(f"\n  Tool: {tool_call.tool_name}")
            print(f"  Arguments: {tool_call.arguments}")
            print(f"  Result: {tool_call.result}")
            print(f"  Duration: {tool_call.duration_ms:.2f}ms")
    
    print("\n=== Streaming Mode ===\n")
    
    # Create a new thread for streaming demo
    thread2 = Thread()
    thread2.add_message(Message(role="user", content="Calculate 15 * 3"))
    
    # Execute in streaming mode
    print("Events as they happen:")
    async for event in agent.go(thread2, stream=True):
        if event.type == EventType.LLM_REQUEST:
            print(f"🤖 Sending request to {event.data['model']}...")
        elif event.type == EventType.LLM_RESPONSE:
            print(f"💬 Got response: {event.data['content'][:50]}...")
        elif event.type == EventType.TOOL_SELECTED:
            print(f"🔧 Using tool: {event.data['tool_name']} with {event.data['arguments']}")
        elif event.type == EventType.TOOL_RESULT:
            print(f"✅ Tool result: {event.data['result']}")
        elif event.type == EventType.MESSAGE_CREATED:
            msg = event.data['message']
            print(f"📝 New {msg.role} message created")
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(f"🏁 Done! Total time: {event.data['duration_ms']:.2f}ms")

if __name__ == "__main__":
    # Note: Set your OpenAI API key first:
    # export OPENAI_API_KEY="your-api-key"
    asyncio.run(main())
