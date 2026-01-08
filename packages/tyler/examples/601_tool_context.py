"""Example: Tool Context Injection (Dependency Injection)

This example demonstrates how to use the tool_context parameter
to inject dependencies (like databases, API clients, user info)
into your tools at runtime.

Features shown:
- Creating tools that accept context
- Injecting different contexts per request
- Multi-tenant patterns with user-specific data
- Accessing typed metadata fields (tool_name, tool_call_id)

Prerequisites:
    pip install slide-tyler

Usage:
    export OPENAI_API_KEY=your-key
    python 601_tool_context.py
"""
import asyncio
from typing import Dict, Any
from dataclasses import dataclass

import weave

from tyler import Agent, Thread, Message, ToolContext


# Simulated database
class MockDatabase:
    """Simulated database for the example."""
    def __init__(self):
        self.orders = {
            "user_123": [
                {"id": "ORD-001", "item": "Widget Pro", "total": 99.99},
                {"id": "ORD-002", "item": "Gadget X", "total": 149.99},
            ],
            "user_456": [
                {"id": "ORD-003", "item": "Thing", "total": 29.99},
            ]
        }
        self.preferences = {
            "user_123": {"theme": "dark", "notifications": True},
            "user_456": {"theme": "light", "notifications": False},
        }
    
    async def get_orders(self, user_id: str, limit: int = 10):
        return self.orders.get(user_id, [])[:limit]
    
    async def get_preferences(self, user_id: str):
        return self.preferences.get(user_id, {})


# Tools that use context injection
# Note: The first parameter must be named 'ctx' or 'context'

@weave.op()
async def get_my_orders(ctx: ToolContext, limit: int = 5) -> str:
    """Get the current user's orders.
    
    Args:
        ctx: Injected context containing 'db' and 'user_id'
        limit: Maximum number of orders to return
    
    Returns:
        JSON string of user's orders
    """
    import json
    
    db = ctx["db"]
    user_id = ctx["user_id"]
    
    orders = await db.get_orders(user_id, limit)
    
    return json.dumps({
        "user_id": user_id,
        "orders": orders,
        "count": len(orders)
    })


@weave.op()
async def get_my_preferences(ctx: ToolContext) -> str:
    """Get the current user's preferences.
    
    Args:
        ctx: Injected context containing 'db' and 'user_id'
    
    Returns:
        JSON string of user's preferences
    """
    import json
    
    db = ctx["db"]
    user_id = ctx["user_id"]
    
    prefs = await db.get_preferences(user_id)
    
    return json.dumps({
        "user_id": user_id,
        "preferences": prefs
    })


@weave.op()
def get_current_user_info(ctx: ToolContext) -> str:
    """Get information about the current user.
    
    This is a sync tool example - context injection works for both
    sync and async tools.
    
    Args:
        ctx: Injected context containing user info
    
    Returns:
        String describing the current user
    """
    user_id = ctx["user_id"]
    user_name = ctx.get("user_name", "Unknown")
    user_tier = ctx.get("user_tier", "standard")
    
    return f"Current user: {user_name} (ID: {user_id}, Tier: {user_tier})"


@weave.op()
async def get_debug_info(ctx: ToolContext) -> str:
    """Get debug information about the current tool execution.
    
    This tool demonstrates accessing the typed metadata fields
    of ToolContext that are automatically populated by the agent.
    
    Args:
        ctx: Injected context with both metadata and user deps
    
    Returns:
        Debug information string
    """
    # Access typed metadata fields (automatically populated)
    tool_name = ctx.tool_name        # "get_debug_info"
    tool_call_id = ctx.tool_call_id  # e.g., "call_abc123"
    
    # Access user-provided dependencies (dict-style)
    user_id = ctx.get("user_id", "unknown")
    
    return f"Debug: tool={tool_name}, call_id={tool_call_id}, user={user_id}"


# Create tool definitions
orders_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_my_orders",
            "description": "Get the current user's order history",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of orders to return",
                        "default": 5
                    }
                },
                "required": []
            }
        }
    },
    "implementation": get_my_orders
}

preferences_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_my_preferences",
            "description": "Get the current user's preferences and settings",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    "implementation": get_my_preferences
}

user_info_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_current_user_info",
            "description": "Get information about the current logged-in user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    "implementation": get_current_user_info
}

debug_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "get_debug_info",
            "description": "Get debug info about the current tool execution",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    "implementation": get_debug_info
}


async def basic_context_injection():
    """Basic example: Inject database and user info into tools."""
    print("=" * 60)
    print("Basic Tool Context Injection Example")
    print("=" * 60)
    
    # Create agent with context-aware tools
    agent = Agent(
        name="account-assistant",
        model_name="gpt-4.1",
        purpose="To help users with their account and orders",
        tools=[orders_tool, preferences_tool, user_info_tool, debug_tool]
    )
    
    # Create shared database
    db = MockDatabase()
    
    # Request for User A
    print("\n--- Request from User 123 (Alice) ---")
    
    thread_a = Thread()
    thread_a.add_message(Message(
        role="user",
        content="What are my recent orders?"
    ))
    
    # Inject context for User A
    result_a = await agent.run(
        thread_a,
        tool_context={
            "db": db,
            "user_id": "user_123",
            "user_name": "Alice",
            "user_tier": "premium"
        }
    )
    
    print(f"Response for Alice: {result_a.content[:200]}...")
    
    # Same agent, different user context
    print("\n--- Request from User 456 (Bob) ---")
    
    thread_b = Thread()
    thread_b.add_message(Message(
        role="user",
        content="What are my orders and preferences?"
    ))
    
    # Inject context for User B
    result_b = await agent.run(
        thread_b,
        tool_context={
            "db": db,
            "user_id": "user_456",
            "user_name": "Bob",
            "user_tier": "standard"
        }
    )
    
    print(f"Response for Bob: {result_b.content[:200]}...")


async def streaming_with_context():
    """Example: Use tool context with streaming."""
    print("\n" + "=" * 60)
    print("Streaming with Tool Context Example")
    print("=" * 60)
    
    from tyler import EventType
    
    agent = Agent(
        name="streaming-assistant",
        model_name="gpt-4.1",
        purpose="To help users with their account",
        tools=[orders_tool]
    )
    
    db = MockDatabase()
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Show me my orders"
    ))
    
    print("\nStreaming response:")
    
    # Stream with tool context
    async for event in agent.stream(
        thread,
        tool_context={
            "db": db,
            "user_id": "user_123",
            "user_name": "Alice"
        }
    ):
        if event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type == EventType.TOOL_SELECTED:
            print(f"\n🔧 Using tool: {event.data['tool_name']}")
        elif event.type == EventType.TOOL_RESULT:
            print(f"   Tool returned: {event.data['result'][:100]}...")
    
    print()  # Final newline


async def main():
    """Run all examples."""
    # Basic context injection
    await basic_context_injection()
    
    # Streaming with context
    await streaming_with_context()
    
    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

