#!/usr/bin/env python3
"""
Example demonstrating the use of Weights & Biases workspace tools with Tyler.

This example shows how to:
1. Retrieve experiment runs from a W&B project
2. Create visualizations (line plots and scalar charts)  
3. Build a comprehensive workspace with multiple sections
4. Save workspace views for future reference

Prerequisites:
- W&B account with API key set (WANDB_API_KEY environment variable)
- wandb and wandb-workspaces packages installed
- Some existing runs in your W&B project
"""

# Load environment variables and configure logging first
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

# Now import everything else
import os
import asyncio
import weave
import sys
from tyler import Agent, Thread, Message

# Import W&B workspace tools
from lye import WANDB_TOOLS

try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-wandb-example")
        logger.debug("Weave tracing initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent with W&B workspace tools
agent = Agent(
    name="Buzz",
    model_name="gpt-4o", 
    purpose="To help create and manage Weights & Biases workspaces for ML experiment tracking and visualization",
    tools=WANDB_TOOLS  # All W&B workspace management tools
)

async def main():
    """
    Demonstrate comprehensive W&B workspace management workflow.
    """
    
    # Check if WANDB_API_KEY is set
    if not os.getenv("WANDB_API_KEY"):
        logger.warning("WANDB_API_KEY not found. Some tools may not work properly.")
        print("⚠️  To fully use this example, set your WANDB_API_KEY environment variable")
        print("   You can get your API key from: https://wandb.ai/authorize")
        print()
    
    # Create a thread for our conversation
    thread = Thread()
    
    print("🤖 W&B Workspace Management Demo")
    print("=" * 50)
    
    # Example 1: Get project runs and analyze them
    example_conversations = [
        {
            "description": "📊 Retrieve and analyze project runs",
            "message": """I want to analyze my ML experiments. Can you:
            1. Get the runs from my W&B project 'wandb-designers/simple-mnist-training' (limit to 10 runs)
            2. Look for runs with accuracy > 0.8
            3. Tell me about the top performing runs"""
        },
        
        {
            "description": "📈 Create visualization components", 
            "message": """Now let's create some visualizations:
            1. Create a line plot showing training loss and validation loss over steps
            2. Create a scalar chart showing final accuracy for each run
            3. Make the plots have meaningful titles"""
        },
        
        # {
        #     "description": "🏗️ Build a comprehensive workspace",
        #     "message": """Create a complete workspace called 'ML Experiment Dashboard' for entity 'my-entity' and project 'my-ml-project' with:
        #     1. A 'Training Metrics' section with the line plot for losses
        #     2. A 'Model Performance' section with the scalar chart for accuracy
        #     3. A 'Validation Metrics' section with validation accuracy over time
        #     4. Add appropriate descriptions for each section"""
        # },
        
        {
            "description": "💾 Save workspace view",
            "message": """Save this workspace as a view called 'Best Models Analysis' with description 'Analysis of top-performing model runs for quarterly review'"""
        }
    ]
    
    # Run through the examples
    for i, example in enumerate(example_conversations, 1):
        print(f"\n{example['description']}")
        print("-" * 30)
        
        logger.info("User: %s", example['message'])
        
        # Add user message
        message = Message(
            role="user", 
            content=example['message']
        )
        thread.add_message(message)
        
        try:
            # Process the thread
            processed_thread, new_messages = await agent.go(thread)
            
            # Log responses
            for message in new_messages:
                if message.role == "assistant":
                    logger.info("Assistant: %s", message.content)
                    print(f"🤖 Agent: {message.content}")
                elif message.role == "tool":
                    logger.info("Tool (%s): %s", message.name, message.content[:200] + "..." if len(message.content) > 200 else message.content)
                    print(f"🔧 Tool ({message.name}): {'Success' if 'success' in message.content and 'true' in message.content else 'Called'}")
            
        except Exception as e:
            logger.error(f"Error in example {i}: {e}")
            print(f"❌ Error: {e}")
        
        print()
    
    print("✅ W&B Workspace Demo Complete!")
    print()
    print("💡 Tips for using W&B workspace tools:")
    print("   • Make sure your WANDB_API_KEY is set")
    print("   • Replace 'my-entity/my-ml-project' with your actual W&B project")
    print("   • Use wandb-get_project_runs to analyze existing experiments")
    print("   • Combine multiple visualization types in workspace sections")
    print("   • Save important workspace configurations as views")

if __name__ == "__main__":
    try:
        # Run the main demo
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)