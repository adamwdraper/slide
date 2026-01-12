"""Events streaming mode implementation.

This module provides the EventsStreamMode which yields ExecutionEvent objects
with detailed telemetry about agent execution.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncGenerator

from tyler.models.execution import ExecutionEvent, EventType
from narrator import Message
from tyler.streaming.base import BaseStreamMode
from tyler.streaming.core import execute_streaming_step

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
        """Execute a single streaming step and yield ExecutionEvents.

        This delegates all LLM/tool mechanics to the canonical executor and simply
        filters to `ExecutionEvent` yields.
        """
        async for signal in execute_streaming_step(agent, thread):
            if signal.kind == "event":
                yield signal.value

# Singleton instance for use by the Agent
events_stream_mode = EventsStreamMode()
