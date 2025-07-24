"""
Example from the introduction page of the documentation.
This demonstrates the simplest way to create and use an agent.
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
processed_thread, new_messages = asyncio.run(agent.go(thread))

# Print all messages in the conversation
for msg in processed_thread.messages:
    print(f"{msg.role.upper()}: {msg.content}")
    print("-" * 80)