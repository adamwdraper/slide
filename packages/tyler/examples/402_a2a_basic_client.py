"""Example of using Tyler as an A2A client to delegate tasks to other agents.

This example demonstrates how to use Tyler with the A2A protocol
to connect to and delegate tasks to remote A2A agents.

Requirements:
- pip install a2a-sdk
- A running A2A agent server (see 401_a2a_basic_server.py)

Run the server first, then run this client example.
"""

# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import asyncio
import os
import sys
import weave
from typing import List, Dict, Any

from tyler import Agent, Thread, Message, EventType
from tyler.a2a import A2AAdapter

# Add the parent directory to the path so we can import the example utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize weave tracing if WANDB_API_KEY is set
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-a2a")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    """Run the A2A client example."""
    
    # Create A2A adapter
    try:
        a2a = A2AAdapter()
    except ImportError as e:
        if "a2a-sdk" in str(e):
            print("Skipping A2A client example - a2a-sdk not installed")
            return
        raise
    
    logger.info("Connecting to A2A agent server...")
    
    # Connect to a remote A2A agent
    # This assumes you have a Tyler A2A server running on localhost:8000
    # (see 401_a2a_basic_server.py example)
    connected = await a2a.connect(
        name="remote_agent",
        base_url="http://localhost:8000"
    )
    
    if not connected:
        logger.error("Failed to connect to A2A agent server.")
        logger.info("Make sure you have an A2A agent running on http://localhost:8000")
        logger.info("You can start one with: python examples/401_a2a_basic_server.py")
        return
    
    try:
        # Get the A2A delegation tools for the agent
        a2a_tools = a2a.get_tools_for_agent(["remote_agent"])
        
        if not a2a_tools:
            logger.error("No delegation tools discovered from the A2A agent.")
            return
            
        logger.info(f"Discovered {len(a2a_tools)} delegation tools from the A2A agent.")
        
        # Create a Tyler agent with A2A delegation capabilities
        agent = Agent(
            name="A2A Client Agent",
            model_name="gpt-4o-mini",
            purpose="To coordinate tasks and delegate to remote A2A agents when needed",
            tools=a2a_tools
        )
        
        # Create a thread
        thread = Thread()
        
        # Add a user message that will require delegation
        thread.add_message(Message(
            role="user",
            content="""I need help with a complex research task about quantum computing applications in cryptography. 
            
            Please delegate this to the remote agent and ask them to:
            1. Explain the current state of quantum computing in cryptography
            2. Identify the main challenges and opportunities
            3. Provide recommendations for businesses preparing for the quantum future
            
            Make sure to get a comprehensive response that covers both technical and business perspectives."""
        ))
        
        # Process the thread with streaming
        logger.info("Processing thread with streaming...")
        print("\n" + "="*60)
        print("Tyler Agent Response:")
        print("="*60)
        
        async for event in agent.go(thread, stream=True):
            if event.type == EventType.LLM_STREAM_CHUNK:
                print(event.data.get("content_chunk", ""), end="", flush=True)
            elif event.type == EventType.MESSAGE_CREATED and event.data.get("message", {}).get("role") == "tool":
                tool_name = event.data.get("message", {}).get("name", "")
                print(f"\n\n[🔧 Tool execution: {tool_name}]")
                print()
            elif event.type == EventType.EXECUTION_COMPLETE:
                print("\n\n" + "="*60)
                print("Processing complete!")
                print("="*60)
        
        # Show final thread state
        print("\n\n" + "="*60)
        print("Final Thread Messages:")
        print("="*60)
        for i, msg in enumerate(thread.messages):
            print(f"\n{i+1}. [{msg.role.upper()}]:")
            if len(msg.content) > 300:
                print(f"{msg.content[:300]}...")
            else:
                print(msg.content)
                
    finally:
        # Clean up
        logger.info("Disconnecting from A2A agents...")
        await a2a.disconnect_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nClient interrupted by user")
    except ImportError as e:
        if "a2a" in str(e):
            print("Error: a2a-sdk not installed.")
            print("Please install it with: pip install a2a-sdk")
        else:
            raise
    except Exception as e:
        logger.error(f"Client error: {e}")
        raise