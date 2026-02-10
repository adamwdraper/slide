"""Agent Skills example demonstrating progressive skill disclosure.

Skills let you package reusable instructions as SKILL.md files. Only skill
names and descriptions appear in the system prompt — the full instructions
are loaded on-demand when the agent calls the activate_skill tool.

This example uses two sample skills included in the ./skills/ directory:
  - code-review: Review code for bugs and style issues
  - summarize: Summarize text into concise key points

Run:
    python 108_skills.py
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

# Resolve skill paths relative to this file
examples_dir = Path(__file__).parent
skills_dir = examples_dir / "skills"

# Initialize the agent with skills
agent = Agent(
    model_name="gpt-4o",
    purpose="To be a helpful assistant with specialized skills.",
    skills=[
        str(skills_dir / "code-review"),
        str(skills_dir / "summarize"),
    ]
)

async def main():
    print("=" * 60)
    print("Tyler Skills Example")
    print("=" * 60)
    print(f"\nLoaded skills: code-review, summarize")
    print("The agent will activate skills on-demand as needed.\n")

    # Create a thread
    thread = Thread()

    # Ask the agent to review some code — this should trigger the
    # code-review skill activation
    user_input = (
        "Please review this Python function:\n\n"
        "```python\n"
        "def get_user(id):\n"
        "    query = f\"SELECT * FROM users WHERE id = {id}\"\n"
        "    result = db.execute(query)\n"
        "    return result[0]\n"
        "```"
    )

    logger.info("User: %s", user_input)

    message = Message(role="user", content=user_input)
    thread.add_message(message)

    # Process the thread
    result = await agent.run(thread)

    logger.info("Assistant: %s", result.content)

    # Show tool usage — should include activate_skill
    tool_usage = result.thread.get_tool_usage()
    if tool_usage["total_calls"] > 0:
        logger.info("Tools used:")
        for tool_name, count in tool_usage["tools"].items():
            logger.info("  %s (%d calls)", tool_name, count)

    logger.info("-" * 60)

    # Second turn: ask for a summary — should trigger the summarize skill
    user_input_2 = (
        "Now summarize this: Machine learning is a subset of artificial "
        "intelligence that enables systems to learn from data. It uses "
        "algorithms to find patterns in large datasets, improving over "
        "time without explicit programming. Key techniques include "
        "supervised learning, unsupervised learning, and reinforcement "
        "learning. Applications range from recommendation engines to "
        "autonomous vehicles."
    )

    logger.info("User: %s", user_input_2)

    message_2 = Message(role="user", content=user_input_2)
    thread.add_message(message_2)

    result_2 = await agent.run(thread)

    logger.info("Assistant: %s", result_2.content)

    tool_usage_2 = result_2.thread.get_tool_usage()
    if tool_usage_2["total_calls"] > 0:
        logger.info("Tools used:")
        for tool_name, count in tool_usage_2["tools"].items():
            logger.info("  %s (%d calls)", tool_name, count)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("\nTo create your own skills:")
    print("  1. Create a directory (e.g. ./my-skill/)")
    print("  2. Add a SKILL.md with YAML frontmatter (name, description)")
    print("  3. Write instructions in the markdown body")
    print("  4. Pass the path to Agent(skills=[...])")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Exiting gracefully...")
        sys.exit(0)
