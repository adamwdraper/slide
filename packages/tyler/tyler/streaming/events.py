"""Events streaming mode implementation.

This module provides the EventsStreamMode which yields ExecutionEvent objects
with detailed telemetry about agent execution.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncGenerator, Dict, Optional

from tyler.models.execution import ExecutionEvent, EventType
from narrator import Message
from tyler.streaming.base import BaseStreamMode, ChunkAccumulator, extract_thinking_content

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from tyler.models.thread import Thread


class EventsStreamMode(BaseStreamMode):
    """Streaming mode that yields ExecutionEvent objects.
    
    This is the default and most feature-rich streaming mode, providing
    detailed telemetry about LLM requests/responses, tool usage, and execution state.
    """
    
    @property
    def name(self) -> str:
        return "events"
    
    async def stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Stream ExecutionEvent objects for agent execution.
        
        Args:
            agent: The Agent instance
            thread: The Thread to process
            
        Yields:
            ExecutionEvent objects with detailed telemetry
        """
        agent._iteration_count = 0
        agent._tool_attributes_cache.clear()
        start_time = datetime.now(timezone.utc)
        total_tokens = 0

        while agent._iteration_count < agent.max_tool_iterations:
            # Yield iteration start event
            yield ExecutionEvent(
                type=EventType.ITERATION_START,
                timestamp=datetime.now(timezone.utc),
                data={
                    "iteration_number": agent._iteration_count,
                    "max_iterations": agent.max_tool_iterations,
                },
            )

            # Execute one step via agent.step_stream for proper Weave tracing
            async for event in agent.step_stream(thread, mode="events"):
                if event.type == EventType.LLM_RESPONSE:
                    toks = (event.data or {}).get("tokens") or {}
                    if isinstance(toks, dict):
                        total_tokens += int(toks.get("total_tokens", 0) or 0)
                yield event

            if not agent._last_step_stream_should_continue:
                break

            agent._iteration_count += 1

        # Handle max iterations limit
        if agent._iteration_count >= agent.max_tool_iterations:
            message = agent.message_factory.create_max_iterations_message()
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            yield ExecutionEvent(
                type=EventType.ITERATION_LIMIT,
                timestamp=datetime.now(timezone.utc),
                data={"iterations_used": agent._iteration_count},
            )
            if agent.thread_store:
                await agent.thread_store.save(thread)

        # Emit execution complete
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        yield ExecutionEvent(
            type=EventType.EXECUTION_COMPLETE,
            timestamp=datetime.now(timezone.utc),
            data={"duration_ms": duration_ms, "total_tokens": total_tokens},
        )

    async def _step_stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute a single streaming step with ExecutionEvent yields.
        
        Handles LLM completion, chunk processing, and tool execution.
        """
        logger = logging.getLogger(__name__)
        
        # Yield LLM request event
        yield ExecutionEvent(
            type=EventType.LLM_REQUEST,
            timestamp=datetime.now(timezone.utc),
            data={
                "message_count": len(thread.messages),
                "model": agent.model_name,
                "temperature": agent.temperature,
            },
        )

        # Get streaming completion
        try:
            streaming_response, metrics = await agent._get_streaming_completion(thread)
        except Exception as e:
            async for event in self._handle_error(agent, thread, f"Completion failed: {str(e)}", e):
                yield event
            return

        if not streaming_response:
            async for event in self._handle_error(
                agent, thread, "No response received from chat completion", None
            ):
                yield event
            return

        # Process streaming chunks
        accumulator = ChunkAccumulator()
        accumulator.metrics = metrics

        try:
            async for chunk in streaming_response:
                if not hasattr(chunk, "choices") or not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Content chunks
                if hasattr(delta, "content") and delta.content is not None:
                    accumulator.add_content(delta.content)
                    yield ExecutionEvent(
                        type=EventType.LLM_STREAM_CHUNK,
                        timestamp=datetime.now(timezone.utc),
                        data={"content_chunk": delta.content},
                    )

                # Thinking/reasoning chunks
                thinking_content, thinking_type = extract_thinking_content(delta)
                if thinking_content:
                    accumulator.add_thinking(thinking_content)
                    yield ExecutionEvent(
                        type=EventType.LLM_THINKING_CHUNK,
                        timestamp=datetime.now(timezone.utc),
                        data={"thinking_chunk": thinking_content, "thinking_type": thinking_type},
                    )

                # Tool call deltas
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        accumulator.process_tool_call_delta(tool_call)

                # Usage updates
                accumulator.process_usage(chunk)

        except Exception as e:
            async for event in self._handle_error(agent, thread, f"Stream error: {str(e)}", e):
                yield event
            return

        # Create assistant message with accumulated content
        content = accumulator.get_content()
        reasoning_content = accumulator.get_thinking()

        yield ExecutionEvent(
            type=EventType.LLM_RESPONSE,
            timestamp=datetime.now(timezone.utc),
            data={
                "content": content,
                "reasoning_content": reasoning_content,
                "has_tool_calls": accumulator.has_tool_calls(),
                "tokens": accumulator.metrics.get("usage"),
            },
        )

        # Build and add assistant message
        assistant_message = Message(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=accumulator.tool_calls if accumulator.has_tool_calls() else None,
            source=agent._create_assistant_source(include_version=True),
            metrics=accumulator.metrics,
        )
        thread.add_message(assistant_message)

        yield ExecutionEvent(
            type=EventType.MESSAGE_CREATED,
            timestamp=datetime.now(timezone.utc),
            data={"message": assistant_message},
        )

        # If no tool calls, we're done
        if not accumulator.has_tool_calls():
            if agent.thread_store:
                await agent.thread_store.save(thread)
            agent._last_step_stream_had_tool_calls = False
            agent._last_step_stream_should_continue = False
            return

        agent._last_step_stream_had_tool_calls = True

        # Execute tools
        should_break = False
        try:
            # Parse tool arguments
            for tool_call in accumulator.tool_calls:
                args = tool_call["function"]["arguments"]
                try:
                    if isinstance(args, str) and args.strip():
                        parsed_args = json.loads(args)
                    elif isinstance(args, dict):
                        parsed_args = args
                    else:
                        parsed_args = {}
                except json.JSONDecodeError:
                    parsed_args = {}
                tool_call["function"]["arguments"] = json.dumps(parsed_args)

            # Yield tool selected events first
            for tool_call in accumulator.tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_call_id = tool_call["id"]
                
                try:
                    args_dict = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    args_dict = {}

                yield ExecutionEvent(
                    type=EventType.TOOL_SELECTED,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "tool_name": tool_name,
                        "tool_call_id": tool_call_id,
                        "arguments": args_dict,
                    },
                )

            # Execute tools in parallel with timing
            tool_start_times: Dict[str, datetime] = {}
            tool_tasks = []
            
            for tool_call in accumulator.tool_calls:
                tool_id = tool_call["id"]
                tool_start_times[tool_id] = datetime.now(timezone.utc)
                tool_tasks.append(agent._handle_tool_execution(tool_call))
            
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(tool_results):
                tool_call = accumulator.tool_calls[i]
                tool_name = tool_call["function"]["name"]
                tool_call_id = tool_call["id"]
                
                # Calculate duration
                tool_end_time = datetime.now(timezone.utc)
                tool_duration_ms = (tool_end_time - tool_start_times[tool_call_id]).total_seconds() * 1000

                # Process result
                tool_message, break_iteration = agent._process_tool_result(result, tool_call, tool_name)
                thread.add_message(tool_message)

                # Yield tool result/error event
                if isinstance(result, Exception):
                    yield ExecutionEvent(
                        type=EventType.TOOL_ERROR,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "tool_name": tool_name,
                            "tool_call_id": tool_call_id,
                            "error": str(result),
                            "duration_ms": tool_duration_ms,
                        },
                    )
                else:
                    yield ExecutionEvent(
                        type=EventType.TOOL_RESULT,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "tool_name": tool_name,
                            "tool_call_id": tool_call_id,
                            "result": tool_message.content,
                            "duration_ms": tool_duration_ms,
                        },
                    )

                yield ExecutionEvent(
                    type=EventType.MESSAGE_CREATED,
                    timestamp=datetime.now(timezone.utc),
                    data={"message": tool_message},
                )

                if break_iteration:
                    should_break = True

            if agent.thread_store:
                await agent.thread_store.save(thread)

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(error_msg)
            yield ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            )
            message = agent._create_error_message(error_msg)
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            if agent.thread_store:
                await agent.thread_store.save(thread)
            should_break = True

        agent._last_step_stream_should_continue = accumulator.has_tool_calls() and not should_break

    async def _handle_error(
        self,
        agent: "Agent",
        thread: "Thread",
        error_msg: str,
        exception: Optional[Exception],
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Handle an error during streaming, yielding appropriate events."""
        logging.getLogger(__name__).error(error_msg)
        
        yield ExecutionEvent(
            type=EventType.EXECUTION_ERROR,
            timestamp=datetime.now(timezone.utc),
            data={
                "error_type": type(exception).__name__ if exception else "NoResponse",
                "message": error_msg,
            },
        )
        
        message = agent._create_error_message(error_msg)
        thread.add_message(message)
        
        yield ExecutionEvent(
            type=EventType.MESSAGE_CREATED,
            timestamp=datetime.now(timezone.utc),
            data={"message": message},
        )
        
        if agent.thread_store:
            await agent.thread_store.save(thread)
        
        agent._last_step_stream_had_tool_calls = False
        agent._last_step_stream_should_continue = False


# Singleton instance for use by the Agent
events_stream_mode = EventsStreamMode()
