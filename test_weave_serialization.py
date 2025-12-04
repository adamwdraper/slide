#!/usr/bin/env python3
"""
Test script to verify Weave serialization/deserialization of Tyler Agent.
This reproduces the real-world scenario where Weave saves and loads an Agent.
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

import weave
from tyler import Agent, Thread, Message

async def main():
    print("=" * 60)
    print("Testing Weave Agent Serialization")
    print("=" * 60)
    
    # Initialize Weave
    print("\n1. Initializing Weave...")
    weave.init("tyler-serialization-test")
    print("   ✓ Weave initialized")
    
    # Create an Agent
    print("\n2. Creating Agent...")
    agent = Agent(
        name="Tester",
        model_name="gpt-4o",
        purpose="To test Weave serialization",
        temperature=0.7
    )
    print(f"   ✓ Agent created: {agent.name}")
    print(f"   - message_factory type: {type(agent.message_factory)}")
    print(f"   - completion_handler type: {type(agent.completion_handler)}")
    
    # Publish the Agent to Weave
    print("\n3. Publishing Agent to Weave...")
    weave.publish(agent, name="Tester")
    print("   ✓ Agent published to Weave")
    
    # Get the ref
    ref_str = f"weave:///{os.getenv('WANDB_ENTITY', 'wandb-designers')}/tyler-serialization-test/object/Tester:latest"
    print(f"\n4. Retrieving Agent from Weave ref: {ref_str}")
    
    try:
        # Retrieve the Agent from Weave
        retrieved_obj = weave.ref(ref_str).get()
        print("   ✓ Object retrieved from Weave")
        print(f"   - Retrieved object type: {type(retrieved_obj)}")
        print(f"   - Retrieved object: {retrieved_obj}")
        
        # Check if it's wrapped
        if hasattr(retrieved_obj, '_val'):
            print(f"   - Wrapped object type: {type(retrieved_obj._val)}")
            retrieved_agent = retrieved_obj._val
        elif hasattr(retrieved_obj, 'val'):
            print(f"   - Val object type: {type(retrieved_obj.val)}")
            retrieved_agent = retrieved_obj.val
        else:
            retrieved_agent = retrieved_obj
            
        print(f"   - Actual agent type: {type(retrieved_agent)}")
        print(f"   - Agent name: {retrieved_agent.name if hasattr(retrieved_agent, 'name') else 'N/A'}")
        
        if hasattr(retrieved_agent, 'message_factory'):
            print(f"   - message_factory type: {type(retrieved_agent.message_factory)}")
        else:
            print("   - message_factory: NOT FOUND (excluded from serialization)")
            
        if hasattr(retrieved_agent, 'completion_handler'):
            print(f"   - completion_handler type: {type(retrieved_agent.completion_handler)}")
        else:
            print("   - completion_handler: NOT FOUND (excluded from serialization)")
        
        # Try to use the retrieved agent
        print("\n5. Testing retrieved Agent with a simple task...")
        thread = Thread()
        thread.add_message(Message(
            role="user",
            content="Say hello in exactly 5 words."
        ))
        
        try:
            # When using Weave publish/ref, need to call the OpRef
            if hasattr(retrieved_agent.run, '__call__'):
                # It's the WeaveObject wrapper, call the OpRef
                result = await retrieved_obj.run(thread)
            else:
                # It's a direct Agent instance
                result = await retrieved_agent.run(thread)
                
            print("   ✓ Agent executed successfully!")
            print(f"   - Response: {result.content}")
            print(f"   - New messages: {len(result.new_messages)}")
            
        except AttributeError as e:
            if "'str' object has no attribute 'debug'" in str(e):
                print("   ✗ LOGGER BUG DETECTED!")
                print(f"   - Error: {e}")
                print("   - The module-level logger is being serialized as a string")
                return False
            else:
                raise
        except TypeError as e:
            if "'OpRef' object is not callable" in str(e):
                print("   ⚠ OpRef issue - trying alternative approach...")
                # Try calling through the WeaveObject wrapper
                try:
                    result = await retrieved_obj.run(thread)
                    print("   ✓ Agent executed successfully via WeaveObject!")
                    print(f"   - Response: {result.content if hasattr(result, 'content') else result}")
                except Exception as e2:
                    print(f"   ✗ Still failing: {e2}")
                    import traceback
                    traceback.print_exc()
                    return False
            else:
                raise
                
    except Exception as e:
        print(f"   ✗ Error during retrieval/execution: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Weave serialization working correctly!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)

