"""
Example script demonstrating agent-to-agent delegation using the parent-child approach.

This script creates multiple specialized agents and attaches them to
a main coordinator agent which can delegate tasks to them.
"""
import asyncio
import os
from tyler import Agent, Thread, Message
from tyler.utils.logging import get_logger
import weave

# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

logger = get_logger(__name__)

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
        logger.debug("Weave tracing initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

async def main():
    # Create specialized agents
    research_agent = Agent(
        name="Research",  # Using simple, unique names
        model_name="gpt-4o",
        purpose="To conduct in-depth research on topics and provide comprehensive information.",
        tools=["web"]  # Give research agent web search tools
    )
    
    code_agent = Agent(
        name="Code",  # Using simple, unique names
        model_name="gpt-4o",
        purpose="To write, review, and explain code in various programming languages.",
        tools=[]  # No additional tools needed for coding
    )
    
    creative_agent = Agent(
        name="Creative",  # Using simple, unique names
        model_name="gpt-4o",
        purpose="To generate creative content such as stories, poems, and marketing copy.",
        tools=[]  # No additional tools needed for creative writing
    )
    
    # Create main agent with specialized agents as a list
    main_agent = Agent(
        name="Coordinator",
        model_name="gpt-4o",
        purpose="To coordinate work by delegating tasks to specialized agents when appropriate.",
        tools=[],  # No additional tools needed since agents will be added as tools
        agents=[research_agent, code_agent, creative_agent]  # Simple list instead of dictionary
    )
    
    # Initialize a thread with a complex query that requires delegation
    thread = Thread()
    
    # Add a message that will likely require delegation
    thread.add_message(Message(
        role="user",
        content="""I need help with a few things:
        
1. I need research on the latest advancements in quantum computing
2. I need a short Python script that can convert CSV to JSON
3. I need a creative tagline for my tech startup called "QuantumLeap"
        
Please help me with these tasks.
        """
    ))
    
    # Print configured child agents
    child_agent_names = [agent.name for agent in main_agent.agents]
    logger.info(f"Configured child agents: {child_agent_names}")
    logger.info(f"Available delegation tools: {len([t for t in main_agent._processed_tools if 'delegate_to_' in t.get('function', {}).get('name', '')])}")
    
    # Process with the main agent using the new API
    result = await main_agent.run(thread)
    
    # Print the results
    print("\n=== FINAL CONVERSATION ===\n")
    print(f"Final Response:\n{result.content}")
    
    # Show execution details
    print(f"\n=== EXECUTION DETAILS ===")
    print(f"New messages: {len(result.new_messages)}")
    
    # Show delegation details from messages
    for msg in result.new_messages:
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get('function', {}).get('name', '')
                if 'delegate_to_' in tool_name:
                    delegated_agent = tool_name.replace('delegate_to_', '')
                    print(f"\nDelegated to agent: {delegated_agent}")
    
    # Show all messages for debugging
    print("\n=== FULL CONVERSATION TRACE ===\n")
    for message in thread.messages:
        if message.role == "user":
            print(f"\nUser: {message.content}\n")
        elif message.role == "assistant":
            print(f"\nAssistant: {message.content}\n")
            if message.tool_calls:
                print(f"[Tool calls: {', '.join([tc['function']['name'] for tc in message.tool_calls])}]")
        elif message.role == "tool":
            print(f"\nTool ({message.name}): {message.content[:200]}...\n" if len(message.content) > 200 else f"\nTool ({message.name}): {message.content}\n")

if __name__ == "__main__":
    asyncio.run(main()) 