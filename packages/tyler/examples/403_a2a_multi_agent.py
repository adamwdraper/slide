"""Advanced example showing multi-agent coordination via A2A protocol.

This example demonstrates:
1. Multiple Tyler agents exposed as A2A servers
2. A coordinator agent that delegates to specialized agents
3. Complex multi-step workflows across agents

Requirements:
- pip install a2a-sdk
- pip install uvicorn

This example starts multiple servers, so run it and then interact via the coordinator.
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
import signal
from typing import List, Dict, Any

from tyler import Agent, Thread, Message, EventType
from tyler.a2a import A2AServer, A2AAdapter
from lye import WEB_TOOLS, FILES_TOOLS, COMMAND_LINE_TOOLS

# Add the parent directory to the path so we can import the example utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize weave tracing if WANDB_API_KEY is set
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-a2a-multi")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Global variable to track running servers
running_servers = []


async def create_research_agent_server(port: int) -> A2AServer:
    """Create a research specialist agent server."""
    research_agent = Agent(
        name="Research Specialist",
        model_name="gpt-4o-mini",
        purpose="""You are a research specialist focused on gathering and analyzing information.
        
        Your expertise includes:
        - Web research and fact-finding
        - Academic literature analysis  
        - Market research and competitive analysis
        - Data collection and validation
        
        You provide comprehensive, well-sourced research reports.""",
        tools=[*WEB_TOOLS]
    )
    
    agent_card = {
        "name": "Tyler Research Specialist",
        "description": "Web research and information gathering specialist",
        "capabilities": ["web_research", "fact_checking", "market_analysis", "data_collection"],
        "specialization": "research"
    }
    
    try:
        server = A2AServer(tyler_agent=research_agent, agent_card=agent_card)
    except ImportError as e:
        if "a2a-sdk" in str(e):
            print("Skipping A2A server creation - a2a-sdk not installed")
            return None
        raise
    
    # Start server in background task
    asyncio.create_task(server.start_server(host="127.0.0.1", port=port))
    await asyncio.sleep(2)  # Give server time to start
    
    return server


async def create_analysis_agent_server(port: int) -> A2AServer:
    """Create an analysis specialist agent server."""
    analysis_agent = Agent(
        name="Analysis Specialist", 
        model_name="gpt-4o-mini",
        purpose="""You are an analysis specialist focused on processing and interpreting data.
        
        Your expertise includes:
        - Data analysis and interpretation
        - Pattern recognition and insights
        - Strategic recommendations
        - Risk assessment
        - Trend identification
        
        You transform raw information into actionable business intelligence.""",
        tools=[*FILES_TOOLS, *COMMAND_LINE_TOOLS]
    )
    
    agent_card = {
        "name": "Tyler Analysis Specialist",
        "description": "Data analysis and strategic insights specialist", 
        "capabilities": ["data_analysis", "pattern_recognition", "strategic_planning", "risk_assessment"],
        "specialization": "analysis"
    }
    
    try:
        server = A2AServer(tyler_agent=analysis_agent, agent_card=agent_card)
    except ImportError as e:
        if "a2a-sdk" in str(e):
            print("Skipping A2A server creation - a2a-sdk not installed")
            return None
        raise
    
    # Start server in background task
    asyncio.create_task(server.start_server(host="127.0.0.1", port=port))
    await asyncio.sleep(2)  # Give server time to start
    
    return server


async def create_coordinator_agent() -> Agent:
    """Create a coordinator agent that delegates to specialist agents."""
    
    # Create A2A adapter to connect to specialist agents
    try:
        a2a = A2AAdapter()
    except ImportError as e:
        if "a2a-sdk" in str(e):
            print("Skipping A2A multi-agent example - a2a-sdk not installed")
            # Return a basic agent for test compatibility
            return Agent(name="Test Agent", model_name="gpt-4o-mini"), None
        raise
    
    # Connect to specialist agents
    research_connected = await a2a.connect(
        name="research_specialist",
        base_url="http://127.0.0.1:8001"
    )
    
    analysis_connected = await a2a.connect(
        name="analysis_specialist", 
        base_url="http://127.0.0.1:8002"
    )
    
    if not research_connected:
        logger.warning("Failed to connect to research specialist")
    if not analysis_connected:
        logger.warning("Failed to connect to analysis specialist")
    
    # Get delegation tools
    delegation_tools = a2a.get_tools_for_agent()
    
    # Create coordinator agent
    coordinator = Agent(
        name="Project Coordinator",
        model_name="gpt-4o",
        purpose="""You are a project coordinator that manages complex multi-agent workflows.
        
        Your role is to:
        1. Break down complex requests into specialized tasks
        2. Delegate research tasks to the Research Specialist  
        3. Delegate analysis tasks to the Analysis Specialist
        4. Coordinate between agents to ensure comprehensive results
        5. Synthesize results into cohesive final deliverables
        
        You have access to specialist agents via delegation tools. Use them strategically to leverage their expertise.
        
        When delegating:
        - Be specific about what you need from each specialist
        - Provide clear context and requirements
        - Ask follow-up questions if needed
        - Combine insights from multiple specialists""",
        tools=delegation_tools
    )
    
    return coordinator, a2a


async def run_interactive_session(coordinator: Agent, adapter: A2AAdapter):
    """Run an interactive session with the coordinator."""
    print("\n" + "="*80)
    print("Tyler Multi-Agent A2A Coordination System")
    print("="*80)
    print("Available Agents:")
    print("  🔍 Research Specialist (port 8001) - Web research and fact-finding")
    print("  📊 Analysis Specialist (port 8002) - Data analysis and insights")
    print("  🎯 Project Coordinator (this session) - Orchestrates multi-agent workflows")
    print()
    print("The coordinator will delegate tasks to specialists as needed.")
    print("Try complex requests that require both research and analysis!")
    print()
    print("Example requests:")
    print("  - 'Analyze the competitive landscape for electric vehicles'")
    print("  - 'Research quantum computing trends and assess business opportunities'") 
    print("  - 'Create a comprehensive report on AI regulation developments'")
    print()
    print("Type 'quit' to exit")
    print("="*80)
    
    while True:
        try:
            user_input = input("\nYour request: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            if not user_input:
                continue
            
            # Create thread for the request
            thread = Thread()
            thread.add_message(Message(role="user", content=user_input))
            
            print(f"\n{'='*60}")
            print("Coordinator Response:")
            print('='*60)
            
            # Process with streaming
            async for event in coordinator.go(thread, stream=True):
                if event.type == EventType.LLM_STREAM_CHUNK:
                    print(event.data.get("content_chunk", ""), end="", flush=True)
                elif event.type == EventType.MESSAGE_CREATED and event.data.get("message", {}).get("role") == "tool":
                    tool_name = event.data.get("message", {}).get("name", "")
                    if "delegate_to_research" in tool_name:
                        print(f"\n\n[🔍 Delegating to Research Specialist...]")
                    elif "delegate_to_analysis" in tool_name:
                        print(f"\n\n[📊 Delegating to Analysis Specialist...]")
                    else:
                        print(f"\n\n[🔧 Using tool: {tool_name}]")
                    print()
                elif update.type.name == "COMPLETE":
                    print(f"\n\n{'='*60}")
                    print("Response complete!")
                    print('='*60)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError processing request: {e}")
            logger.error(f"Session error: {e}")
    
    print("\nEnding interactive session...")


async def main():
    """Run the multi-agent A2A coordination example."""
    global running_servers
    
    try:
        logger.info("Starting multi-agent A2A coordination system...")
        print("🚀 Starting Tyler Multi-Agent A2A System...")
        print("   Setting up specialist agents...")
        
        # Start specialist agent servers
        print("   📡 Starting Research Specialist server (port 8001)...")
        research_server = await create_research_agent_server(8001)
        if research_server:
            running_servers.append(research_server)
        
        print("   📡 Starting Analysis Specialist server (port 8002)...")
        analysis_server = await create_analysis_agent_server(8002)
        if analysis_server:
            running_servers.append(analysis_server)
        
        # Check if A2A is available
        if not research_server or not analysis_server:
            print("Skipping multi-agent example - a2a-sdk not installed")
            return
        
        print("   🎯 Creating Project Coordinator...")
        coordinator, adapter = await create_coordinator_agent()
        
        print("   ✅ All agents ready!")
        
        # Run interactive session
        await run_interactive_session(coordinator, adapter)
        
    except Exception as e:
        logger.error(f"Multi-agent system error: {e}")
        raise
        
    finally:
        # Clean up
        logger.info("Shutting down multi-agent system...")
        print("\n🛑 Shutting down agents...")
        
        if 'adapter' in locals():
            await adapter.disconnect_all()
        
        for server in running_servers:
            try:
                await server.stop_server()
            except Exception as e:
                logger.warning(f"Error stopping server: {e}")
        
        print("✅ All agents stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print("\n\n🛑 Shutdown signal received...")
    # The asyncio event loop will handle the cleanup in the finally block
    raise KeyboardInterrupt


if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Multi-agent system stopped by user")
    except ImportError as e:
        if "a2a" in str(e):
            print("Error: a2a-sdk not installed.")
            print("Please install it with: pip install a2a-sdk")
        elif "uvicorn" in str(e):
            print("Error: uvicorn not installed.")  
            print("Please install it with: pip install uvicorn")
        else:
            raise
    except Exception as e:
        logger.error(f"System error: {e}")
        raise