"""OpenAI-compatible streaming mode implementation.

This module provides the OpenAIStreamMode which yields raw LiteLLM chunks
in OpenAI-compatible format for direct integration with OpenAI clients.
"""
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

from tyler.streaming.base import BaseStreamMode
from tyler.streaming.core import execute_streaming_step

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from narrator import Thread


class OpenAIStreamMode(BaseStreamMode):
    """Streaming mode that yields raw LiteLLM chunks.
    
    This mode passes through raw chunks from the LLM provider in OpenAI-compatible
    format. Tools are still executed, but no ExecutionEvents are emitted.
    
    Best for:
    - Building OpenAI API proxies or gateways
    - Direct integration with OpenAI-compatible clients
    - Minimal latency requirements (no transformation overhead)
    """
    
    @property
    def name(self) -> str:
        return "openai"
    
    async def stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[Any, None]:
        """Stream raw LiteLLM chunks for agent execution.
        
        Args:
            agent: The Agent instance
            thread: The Thread to process
            
        Yields:
            Raw LiteLLM chunk objects in OpenAI-compatible format
        """
        agent._iteration_count = 0
        agent._tool_attributes_cache.clear()

        while agent._iteration_count < agent.max_tool_iterations:
            # Execute one step via agent.step_stream for proper Weave tracing
            async for chunk in agent.step_stream(thread, mode="openai"):
                yield chunk

            if not agent._last_step_stream_should_continue:
                break

            agent._iteration_count += 1

        # Handle max iterations limit (no events in openai mode)
        if agent._iteration_count >= agent.max_tool_iterations:
            logging.getLogger(__name__).warning(
                f"Hit max iterations ({agent.max_tool_iterations})"
            )
            message = agent.message_factory.create_max_iterations_message()
            thread.add_message(message)
            if agent.thread_store:
                await agent.thread_store.save(thread)

    async def _step_stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[Any, None]:
        """Execute a single streaming step yielding only raw chunks.

        All tool execution + thread updates happen in the canonical executor; this
        mode simply forwards raw chunks.
        """
        async for signal in execute_streaming_step(agent, thread):
            if signal.kind == "chunk":
                yield signal.value


# Singleton instance for use by the Agent
openai_stream_mode = OpenAIStreamMode()
