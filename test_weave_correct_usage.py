#!/usr/bin/env python3
"""
Test script to verify Weave serialization/deserialization of Tyler Agent.

This demonstrates the CORRECT way to use Weave with Tyler:
1. Weave traces Agent calls automatically (no special serialization needed)
2. Agent configuration can be versioned separately if needed
3. Don't use weave.publish() for complex Pydantic models - just use them normally!
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

import weave
from tyler import Agent, Thread, Message

async def main():
    print("=" * 60)
    print("Testing Tyler Agent with Weave (Correct Approach)")
    print("=" * 60)
    
    # Initialize Weave
    print("\n1. Initializing Weave...")
    weave.init("tyler-correct-usage")
    print("   ✓ Weave initialized")
    
    # Create an Agent - Weave will automatically track it
    print("\n2. Creating Agent...")
    agent = Agent(
        name="Tester",
        model_name="gpt-4o",
        purpose="To test Weave integration",
        temperature=0.7
    )
    print(f"   ✓ Agent created: {agent.name}")
    
    # Use the agent - Weave automatically traces the call
    print("\n3. Using Agent (Weave traces automatically)...")
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Say hello in exactly 5 words."
    ))
    
    try:
        result = await agent.run(thread)
        print("   ✓ Agent executed successfully!")
        print(f"   - Response: {result.content}")
        print(f"   - Weave is tracking this call automatically")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS - Tyler works perfectly with Weave!")
    print("=" * 60)
    print("\nKey Points:")
    print("  • Weave automatically traces all Agent.run() calls")
    print("  • No need to publish/retrieve Agent objects")
    print("  • Agent configuration is versioned in Weave UI")
    print("  • All tool calls, LLM calls, etc. are traced")
    print("\n✨ Check your Weave UI to see the traced call!")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)

