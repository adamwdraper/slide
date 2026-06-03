#!/usr/bin/env python3
"""
Manual Weave tracing smoke test for Tyler agents.

Set OPENAI_API_KEY, WANDB_API_KEY, and WANDB_PROJECT in your environment or
root .env file before running this example. Tyler emits the existing weave.op
trace tree and, when supported by Weave, Agents session/turn/LLM/tool spans.
"""

import asyncio
import os
from collections import Counter

from dotenv import load_dotenv

load_dotenv()

import weave
from tyler import Agent, EventType, Message, Thread


def calculate(operation: str, x: float, y: float) -> str:
    """Perform basic arithmetic."""
    if operation == "add":
        return str(x + y)
    if operation == "subtract":
        return str(x - y)
    if operation == "multiply":
        return str(x * y)
    if operation == "divide":
        if y == 0:
            return "Error: division by zero"
        return str(x / y)
    return f"Error: unknown operation {operation}"


calculator_tool = {
    "definition": {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform basic arithmetic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                    },
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["operation", "x", "y"],
            },
        },
    },
    "implementation": calculate,
}


def build_agent(name: str) -> Agent:
    """Create an agent configured for manual tracing checks."""
    return Agent(
        name=name,
        model_name=os.getenv("TYLER_MANUAL_MODEL", "gpt-4.1-mini"),
        purpose="Use tools when helpful and answer concisely.",
        tools=[calculator_tool],
        temperature=0,
    )


async def run_example() -> None:
    """Run a complete non-streaming call and print execution details."""
    agent = build_agent("Weave Run Example Agent")
    thread = Thread()
    thread.add_message(
        Message(
            role="user",
            content="Use the calculate tool to multiply 9 by 6, then answer in one short sentence.",
        )
    )

    result = await agent.run(thread)

    print("run content:", result.content)
    print("run success:", result.success)
    print("run duration_ms:", result.execution.duration_ms)
    print("run total_tokens:", result.execution.total_tokens)
    for tool_call in result.execution.tool_calls:
        print(
            "run tool:",
            tool_call.tool_name,
            tool_call.arguments,
            "->",
            tool_call.result or tool_call.error,
        )


async def stream_example() -> None:
    """Run a streaming call and print events as they arrive."""
    agent = build_agent("Weave Stream Example Agent")
    thread = Thread()
    thread.add_message(
        Message(
            role="user",
            content="Use the calculate tool to add 17 and 25, then answer in one short sentence.",
        )
    )

    events = []
    print("\nstream content:", end=" ", flush=True)
    async for event in agent.stream(thread):
        events.append(event)
        if event.type == EventType.LLM_STREAM_CHUNK:
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type == EventType.TOOL_SELECTED:
            print(f"\nstream tool selected: {event.data.get('tool_name')}")
        elif event.type == EventType.TOOL_RESULT:
            print(f"stream tool result: {event.data.get('result')}")
        elif event.type == EventType.EXECUTION_COMPLETE:
            print(
                f"\nstream complete: duration_ms={event.data.get('duration_ms')} "
                f"total_tokens={event.data.get('total_tokens')}"
            )

    print("stream event counts:", dict(Counter(event.type.value for event in events)))


async def main() -> None:
    """Initialize Weave when configured, then run both examples."""
    weave_project = os.getenv("WANDB_PROJECT")
    if weave_project:
        weave.init(weave_project)
    else:
        print("WANDB_PROJECT is not set; running without Weave tracing.")

    await run_example()
    await stream_example()


if __name__ == "__main__":
    asyncio.run(main())
