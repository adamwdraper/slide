"""OpenAI-compatible streaming mode implementation.

This module provides the OpenAIStreamMode which yields raw LiteLLM chunks
in OpenAI-compatible format for direct integration with OpenAI clients.
"""
import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

from narrator import Message
from tyler.streaming.base import BaseStreamMode, ChunkAccumulator

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from tyler.models.thread import Thread


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
        """Execute a single streaming step yielding raw chunks.
        
        Handles LLM completion, chunk processing, and tool execution silently.
        """
        logger = logging.getLogger(__name__)
        
        # Get streaming completion
        try:
            streaming_response, metrics = await agent._get_streaming_completion(thread)
        except Exception as e:
            logger.error(f"Completion failed: {e}")
            agent._last_step_stream_had_tool_calls = False
            agent._last_step_stream_should_continue = False
            return

        if not streaming_response:
            logger.error("No response received from chat completion")
            agent._last_step_stream_had_tool_calls = False
            agent._last_step_stream_should_continue = False
            return

        # Process streaming chunks
        accumulator = ChunkAccumulator()
        accumulator.metrics = metrics

        try:
            async for chunk in streaming_response:
                # Yield raw chunk immediately
                yield chunk

                if not hasattr(chunk, "choices") or not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Accumulate content for message creation
                if hasattr(delta, "content") and delta.content is not None:
                    accumulator.add_content(delta.content)

                # Accumulate tool calls
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        accumulator.process_tool_call_delta(tool_call)

                # Track usage
                accumulator.process_usage(chunk)

        except Exception as e:
            logger.error(f"Stream error: {e}")
            agent._last_step_stream_had_tool_calls = False
            agent._last_step_stream_should_continue = False
            return

        # Create assistant message with accumulated content
        content = accumulator.get_content()
        assistant_message = Message(
            role="assistant",
            content=content,
            tool_calls=accumulator.tool_calls if accumulator.has_tool_calls() else None,
            source=agent._create_assistant_source(include_version=True),
            metrics=accumulator.metrics,
        )
        thread.add_message(assistant_message)

        # If no tool calls, we're done
        if not accumulator.has_tool_calls():
            if agent.thread_store:
                await agent.thread_store.save(thread)
            agent._last_step_stream_had_tool_calls = False
            agent._last_step_stream_should_continue = False
            return

        agent._last_step_stream_had_tool_calls = True

        # Execute tools silently (no events yielded)
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

            # Execute tools in parallel
            tool_tasks = [agent._handle_tool_execution(tc) for tc in accumulator.tool_calls]
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(tool_results):
                tool_call = accumulator.tool_calls[i]
                tool_name = tool_call["function"]["name"]
                tool_message, break_iteration = agent._process_tool_result(result, tool_call, tool_name)
                thread.add_message(tool_message)
                if break_iteration:
                    should_break = True

            if agent.thread_store:
                await agent.thread_store.save(thread)

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(error_msg)
            message = agent._create_error_message(error_msg)
            thread.add_message(message)
            if agent.thread_store:
                await agent.thread_store.save(thread)
            should_break = True

        agent._last_step_stream_should_continue = accumulator.has_tool_calls() and not should_break


# Singleton instance for use by the Agent
openai_stream_mode = OpenAIStreamMode()
