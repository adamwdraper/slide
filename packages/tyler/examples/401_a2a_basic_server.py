"""Example of exposing a Tyler agent as an A2A server.

This example demonstrates how to expose a Tyler agent via the A2A protocol,
allowing other agents to delegate tasks to it.

Requirements:
- pip install a2a-sdk
- pip install uvicorn (for running the FastAPI server)

Run this server, then you can connect to it with 402_a2a_basic_client.py
or any other A2A-compatible client.
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

from tyler import Agent, Thread, Message
from tyler.a2a import A2AServer
from lye import WEB_TOOLS, FILES_TOOLS

# Add the parent directory to the path so we can import the example utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize weave tracing if WANDB_API_KEY is set
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-a2a-server")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    """Run the A2A server example."""
    
    # Create a Tyler agent with various capabilities
    tyler_agent = Agent(
        name="Research Assistant",
        model_name="gpt-4o-mini",
        purpose="""You are an expert research assistant specializing in technology, science, and business analysis. 
        
        Your strengths include:
        - Comprehensive research and analysis
        - Technical concept explanation
        - Business strategy recommendations
        - Future trend identification
        - Risk assessment and opportunity analysis
        
        You provide well-structured, actionable insights that combine technical depth with practical business value.""",
        tools=[*WEB_TOOLS, *FILES_TOOLS]  # Give the agent web and file tools
    )
    
    # Custom agent card for A2A exposure
    agent_card_data = {
        "name": "Tyler Research Assistant",
        "version": "1.0.0",
        "description": "Advanced AI research assistant powered by Tyler framework with web search and file processing capabilities",
        "capabilities": [
            "research_and_analysis",
            "web_search",
            "document_processing", 
            "technical_explanation",
            "business_strategy",
            "trend_analysis"
        ],
        "contact": {
            "name": "Tyler Framework Team",
            "email": "hello@tyler.ai"
        },
        "vendor": "Tyler Framework",
        "protocol_version": "1.0"
    }
    
    # Create A2A server
    try:
        a2a_server = A2AServer(
            tyler_agent=tyler_agent,
            agent_card=agent_card_data
        )
    except ImportError as e:
        if "a2a-sdk" in str(e):
            print("Skipping A2A server example - a2a-sdk not installed")
            return
        raise
    
    logger.info("Starting Tyler A2A server...")
    logger.info("The server will expose the Tyler agent via A2A protocol")
    logger.info("Other agents can connect and delegate tasks to this agent")
    
    print("\n" + "="*60)
    print("Tyler A2A Server")
    print("="*60)
    print(f"Agent Name: {agent_card_data['name']}")
    print(f"Description: {agent_card_data['description']}")
    print(f"Capabilities: {', '.join(agent_card_data['capabilities'])}")
    print("\nServer starting on http://localhost:8000")
    print("Agent card available at: http://localhost:8000/.well-known/agent")
    print("\nTo connect from another agent:")
    print("  base_url = 'http://localhost:8000'")
    print("\nTo test with the client example:")
    print("  python examples/402_a2a_basic_client.py")
    print("\nPress Ctrl+C to stop the server")
    print("="*60)
    
    try:
        # Start the server (this will block)
        await a2a_server.start_server(host="0.0.0.0", port=8000)
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested...")
        print("\n\nShutting down A2A server...")
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
        
    finally:
        # Clean up
        await a2a_server.stop_server()
        logger.info("A2A server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")
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
        logger.error(f"Server startup error: {e}")
        raise