"""AGENTS.md example demonstrating project-level instructions.

AGENTS.md files provide project-level instructions that are eagerly loaded
into the agent's system prompt at init time. Unlike skills (progressively
disclosed on-demand), AGENTS.md content is always present in the prompt.

This example loads a sample AGENTS.md from the ./sample-project/ directory
and shows how it influences the agent's behavior.

Run:
    python 109_agents_md.py
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import os
import asyncio
import weave
import sys
from pathlib import Path
from tyler import Agent, Thread, Message

# Initialize weave tracing if WANDB_PROJECT is set
weave_project = os.getenv("WANDB_PROJECT")
if weave_project:
    try:
        weave.init(weave_project)
        logger.debug("Weave tracing initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")

# Resolve the sample AGENTS.md relative to this file
examples_dir = Path(__file__).parent
agents_md_path = examples_dir / "sample-project" / "AGENTS.md"

# Initialize the agent with AGENTS.md
agent = Agent(
    model_name="gpt-4o",
    purpose="To be a helpful coding assistant.",
    agents_md=str(agents_md_path),
)

async def main():
    print("=" * 60)
    print("Tyler AGENTS.md Example")
    print("=" * 60)
    print(f"\nLoaded AGENTS.md from: {agents_md_path}")
    print("The project instructions are now part of the system prompt.\n")

    # Show that the project instructions are in the prompt
    if "<project_instructions>" in agent._system_prompt:
        print("Project instructions detected in system prompt.")
    print()

    # Create a thread
    thread = Thread()

    # Ask a question that the AGENTS.md instructions should influence
    user_input = "Write a Python function that fetches user data from an API."

    logger.info("User: %s", user_input)

    message = Message(role="user", content=user_input)
    thread.add_message(message)

    # Process the thread — the agent should follow AGENTS.md guidelines
    result = await agent.run(thread)

    logger.info("Assistant: %s", result.content)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("\nTo use AGENTS.md in your project:")
    print("  1. Create an AGENTS.md file in your project root")
    print("  2. Add coding guidelines, style rules, or project context")
    print("  3. Pass the path to Agent(agents_md='./AGENTS.md')")
    print("  4. Or use agents_md=True for auto-discovery")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)
