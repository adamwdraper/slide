"""
Example from the introduction page of the documentation.
This demonstrates the simplest way to create and use an agent.
Now updated with the new execution observability API!
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from tyler import Agent, Thread, Message
from lye import WEB_TOOLS

# Create an AI agent that can browse the web
agent = Agent(
    name="web_summarizer",
    model_name="gpt-4o",
    purpose="To summarize web content clearly and concisely",
    tools=WEB_TOOLS
)

# Ask your agent to visit and summarize a webpage
thread = Thread()
message = Message(
    role="user", 
    content="Why should I use https://slide.mintlify.app/introduction?"
)
thread.add_message(message)

# The agent will visit the page and provide a summary
result = asyncio.run(agent.go(thread))

# Print the response
print(f"ASSISTANT: {result.output}")
print("-" * 80)

# Show execution metrics
print(f"Execution time: {result.execution.duration_ms:.2f}ms")
print(f"Total tokens: {result.execution.total_tokens}")

# Show tool usage if any
if result.execution.tool_calls:
    print(f"\nTools used:")
    for tool_call in result.execution.tool_calls:
        print(f"  - {tool_call.tool_name}")
print("-" * 80)