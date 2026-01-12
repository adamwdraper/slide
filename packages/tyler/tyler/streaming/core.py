"""Canonical streaming step executor.

This module contains the shared implementation of "one agent step/turn" for streaming:

- stream the LLM completion
- accumulate content / thinking / tool calls
- create the assistant message
- execute tools (if requested) and append tool messages
- set `agent._last_step_stream_should_continue`

Streaming *modes* (events/openai/vercel) should only be responsible for formatting/yielding.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Literal, Optional

from narrator import Message

from tyler.models.execution import EventType, ExecutionEvent
from tyler.streaming.base import ChunkAccumulator, extract_thinking_content

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from tyler.models.thread import Thread


@dataclass(frozen=True)
class StepSignal:
    """A single yield from the canonical step executor."""

    kind: Literal["chunk", "event"]
    value: Any


async def execute_streaming_step(
    agent: "Agent",
    thread: "Thread",
) -> AsyncGenerator[StepSignal, None]:
    """Execute a single streaming step/turn.

    Yields:
      - StepSignal(kind="chunk", value=<raw litellm chunk>)
      - StepSignal(kind="event", value=<ExecutionEvent>)
    """
    logger = logging.getLogger(__name__)

    # Reset per-step flags
    agent._last_step_stream_had_tool_calls = False
    agent._last_step_stream_should_continue = False

    # LLM request event
    yield StepSignal(
        kind="event",
        value=ExecutionEvent(
            type=EventType.LLM_REQUEST,
            timestamp=datetime.now(timezone.utc),
            data={
                "message_count": len(thread.messages),
                "model": agent.model_name,
                "temperature": agent.temperature,
            },
        ),
    )

    # Get streaming completion
    try:
        streaming_response, metrics = await agent._get_streaming_completion(thread)
    except Exception as e:
        error_msg = f"Completion failed: {str(e)}"
        logger.error(error_msg)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            ),
        )
        message = agent._create_error_message(error_msg)
        thread.add_message(message)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            ),
        )
        if agent.thread_store:
            await agent.thread_store.save(thread)
        agent._last_step_stream_had_tool_calls = False
        agent._last_step_stream_should_continue = False
        return

    if not streaming_response:
        error_msg = "No response received from chat completion"
        logger.error(error_msg)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": "NoResponse", "message": error_msg},
            ),
        )
        message = agent._create_error_message(error_msg)
        thread.add_message(message)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            ),
        )
        if agent.thread_store:
            await agent.thread_store.save(thread)
        agent._last_step_stream_had_tool_calls = False
        agent._last_step_stream_should_continue = False
        return

    accumulator = ChunkAccumulator()
    accumulator.metrics = metrics

    # Stream chunks + derive events
    try:
        async for chunk in streaming_response:
            # Always expose the raw chunk to modes that want it
            yield StepSignal(kind="chunk", value=chunk)

            if not hasattr(chunk, "choices") or not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Content events
            if hasattr(delta, "content") and delta.content is not None:
                accumulator.add_content(delta.content)
                yield StepSignal(
                    kind="event",
                    value=ExecutionEvent(
                        type=EventType.LLM_STREAM_CHUNK,
                        timestamp=datetime.now(timezone.utc),
                        data={"content_chunk": delta.content},
                    ),
                )

            # Thinking events
            thinking_content, thinking_type = extract_thinking_content(delta)
            if thinking_content:
                accumulator.add_thinking(thinking_content)
                yield StepSignal(
                    kind="event",
                    value=ExecutionEvent(
                        type=EventType.LLM_THINKING_CHUNK,
                        timestamp=datetime.now(timezone.utc),
                        data={"thinking_chunk": thinking_content, "thinking_type": thinking_type},
                    ),
                )

            # Tool call deltas
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tool_call in delta.tool_calls:
                    accumulator.process_tool_call_delta(tool_call)

            # Usage updates
            accumulator.process_usage(chunk)

    except Exception as e:
        error_msg = f"Stream error: {str(e)}"
        logger.error(error_msg)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            ),
        )
        message = agent._create_error_message(error_msg)
        thread.add_message(message)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            ),
        )
        if agent.thread_store:
            await agent.thread_store.save(thread)
        agent._last_step_stream_had_tool_calls = False
        agent._last_step_stream_should_continue = False
        return

    # LLM response event
    content = accumulator.get_content()
    reasoning_content = accumulator.get_thinking()
    yield StepSignal(
        kind="event",
        value=ExecutionEvent(
            type=EventType.LLM_RESPONSE,
            timestamp=datetime.now(timezone.utc),
            data={
                "content": content,
                "reasoning_content": reasoning_content,
                "has_tool_calls": accumulator.has_tool_calls(),
                "tokens": accumulator.metrics.get("usage", {}),
                "latency_ms": accumulator.metrics.get("timing", {}).get("latency", 0),
            },
        ),
    )

    # Add assistant message
    assistant_message = Message(
        role="assistant",
        content=content,
        reasoning_content=reasoning_content,
        tool_calls=accumulator.tool_calls if accumulator.has_tool_calls() else None,
        source=agent._create_assistant_source(include_version=True),
        metrics=accumulator.metrics,
    )
    thread.add_message(assistant_message)
    yield StepSignal(
        kind="event",
        value=ExecutionEvent(
            type=EventType.MESSAGE_CREATED,
            timestamp=datetime.now(timezone.utc),
            data={"message": assistant_message},
        ),
    )

    # No tools => done
    if not accumulator.has_tool_calls():
        if agent.thread_store:
            await agent.thread_store.save(thread)
        agent._last_step_stream_had_tool_calls = False
        agent._last_step_stream_should_continue = False
        return

    agent._last_step_stream_had_tool_calls = True

    # TOOL_SELECTED events + parse args for tool execution
    parsed_tool_calls = []
    for tool_call in accumulator.tool_calls:
        tool_name = tool_call["function"]["name"]
        tool_call_id = tool_call["id"]
        args_raw = tool_call["function"]["arguments"]
        try:
            if isinstance(args_raw, str) and args_raw.strip():
                args_dict = json.loads(args_raw)
            elif isinstance(args_raw, dict):
                args_dict = args_raw
            else:
                args_dict = {}
        except json.JSONDecodeError:
            args_dict = {}

        # Normalize stored arguments to JSON string (consistent with existing behavior)
        tool_call["function"]["arguments"] = json.dumps(args_dict)
        parsed_tool_calls.append((tool_call, tool_name, tool_call_id, args_dict))

        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.TOOL_SELECTED,
                timestamp=datetime.now(timezone.utc),
                data={
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "arguments": args_dict,
                },
            ),
        )

    # Execute tools in parallel with duration tracking
    tool_start_times: Dict[str, datetime] = {}
    tool_tasks = []
    for tool_call, tool_name, tool_call_id, _args_dict in parsed_tool_calls:
        tool_start_times[tool_call_id] = datetime.now(timezone.utc)
        tool_tasks.append(agent._handle_tool_execution(tool_call))

    should_break = False
    try:
        tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)

        for i, result in enumerate(tool_results):
            tool_call, tool_name, tool_call_id, _args_dict = parsed_tool_calls[i]
            tool_end_time = datetime.now(timezone.utc)
            duration_ms = (
                tool_end_time - tool_start_times[tool_call_id]
            ).total_seconds() * 1000

            tool_message, break_iteration = agent._process_tool_result(result, tool_call, tool_name)
            thread.add_message(tool_message)

            if isinstance(result, Exception):
                yield StepSignal(
                    kind="event",
                    value=ExecutionEvent(
                        type=EventType.TOOL_ERROR,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "tool_name": tool_name,
                            "tool_call_id": tool_call_id,
                            "error": str(result),
                            "duration_ms": duration_ms,
                        },
                    ),
                )
            else:
                yield StepSignal(
                    kind="event",
                    value=ExecutionEvent(
                        type=EventType.TOOL_RESULT,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "tool_name": tool_name,
                            "tool_call_id": tool_call_id,
                            "result": tool_message.content,
                            "duration_ms": duration_ms,
                        },
                    ),
                )

            yield StepSignal(
                kind="event",
                value=ExecutionEvent(
                    type=EventType.MESSAGE_CREATED,
                    timestamp=datetime.now(timezone.utc),
                    data={"message": tool_message},
                ),
            )

            if break_iteration:
                should_break = True

        if agent.thread_store:
            await agent.thread_store.save(thread)

    except Exception as e:
        error_msg = f"Tool execution failed: {str(e)}"
        logger.error(error_msg)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            ),
        )
        message = agent._create_error_message(error_msg)
        thread.add_message(message)
        yield StepSignal(
            kind="event",
            value=ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            ),
        )
        if agent.thread_store:
            await agent.thread_store.save(thread)
        should_break = True

    agent._last_step_stream_should_continue = accumulator.has_tool_calls() and not should_break

