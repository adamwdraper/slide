#!/usr/bin/env python3
"""
Example demonstrating streaming updates with tool usage.
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
from tyler import Agent, Thread, Message, EventType

@weave.op(name="calculate")
def custom_calculator_implementation(operation: str, x: float, y: float) -> str:
    """
    Implementation of a simple calculator tool.
    """
    try:
        if operation == "add":
            result = x + y
        elif operation == "subtract":
            result = x - y
        elif operation == "multiply":
            result = x * y
        elif operation == "divide":
            if y == 0:
                return "Error: Division by zero"
            result = x / y
        else:
            return f"Error: Unknown operation {operation}"
        
        return f"Result of {operation}({x}, {y}) = {result}"
    except Exception as e:
        return f"Error performing calculation: {str(e)}"

# Define custom calculator tool
custom_calculator_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform basic mathematical operations",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "The mathematical operation to perform (add, subtract, multiply, divide)",
                        "enum": ["add", "subtract", "multiply", "divide"]
                    },
                    "x": {
                        "type": "number",
                        "description": "First number"
                    },
                    "y": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["operation", "x", "y"]
            }
        }
    },
    "implementation": custom_calculator_implementation
}

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
        logger.debug("Weave tracing initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Initialize the agent with both built-in and custom tools
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with calculations and web searches",
    tools=[
        "web",                    # Load the web tools module
        custom_calculator_tool,   # Add our calculator tool
    ]
)

async def main():
    # Create a thread
    thread = Thread()

    # Example conversation with web page fetch followed by calculations
    conversations = [
        "Can you fetch the content from https://adamwdraper.github.io/tyler/?",
        "Let's do a calculation: what is 537 divided by 3?"
    ]

    for user_input in conversations:
        logger.info("User: %s", user_input)
        
        # Add user message
        message = Message(
            role="user",
            content=user_input
        )
        thread.add_message(message)

        # Process the thread with streaming using the new API
        async for event in agent.stream(thread):
            if event.type == EventType.LLM_STREAM_CHUNK:
                # Real-time content streaming
                print(event.data.get("content_chunk", ""), end="", flush=True)
            elif event.type == EventType.TOOL_SELECTED:
                print()  # New line after content
                logger.info("Using tool: %s", event.data.get("tool_name"))
            elif event.type == EventType.TOOL_RESULT:
                logger.info("Tool result: %s", event.data.get("result")[:100] + "..." if len(str(event.data.get("result", ""))) > 100 else event.data.get("result"))
            elif event.type == EventType.MESSAGE_CREATED:
                msg = event.data.get("message")
                if msg and msg.role == "assistant" and msg.content:
                    print()  # Ensure we're on a new line
                    logger.info("Complete assistant message created")
            elif event.type == EventType.EXECUTION_ERROR:
                logger.error("Error: %s", event.data.get("message"))
            elif event.type == EventType.EXECUTION_COMPLETE:
                logger.info("Processing complete - Duration: %.2fms, Tokens: %d", 
                           event.data.get("duration_ms", 0),
                           event.data.get("total_tokens", 0))
        
        logger.info("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0) 