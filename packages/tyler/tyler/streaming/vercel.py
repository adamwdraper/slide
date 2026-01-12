"""Vercel AI SDK Data Stream Protocol streaming mode.

This module provides the VercelStreamMode which yields SSE-formatted strings
compatible with the Vercel AI SDK's useChat hook.

Protocol reference: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol
"""
from typing import TYPE_CHECKING, AsyncGenerator

from tyler.models.execution import EventType
from tyler.streaming.base import BaseStreamMode
from tyler.streaming.vercel_protocol import VercelStreamFormatter, FinishReason

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from tyler.models.thread import Thread


class VercelStreamMode(BaseStreamMode):
    """Streaming mode that yields Vercel AI SDK Data Stream Protocol SSE strings.
    
    This mode transforms ExecutionEvents into SSE-formatted strings compatible
    with the Vercel AI SDK's useChat hook, making it easy to build React/Next.js
    chat interfaces.
    
    Best for:
    - React/Next.js frontends using @ai-sdk/react
    - Vercel AI SDK ecosystem integration
    - Pre-formatted SSE streams ready for HTTP response
    """
    
    @property
    def name(self) -> str:
        return "vercel"
    
    async def stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[str, None]:
        """Stream SSE-formatted strings for Vercel AI SDK.
        
        This method orchestrates the full agent run by repeatedly calling
        `agent.step_stream(..., mode="vercel")` until completion, while emitting
        the message-level protocol markers (`start`, `finish`, `[DONE]`) once.
        
        Args:
            agent: The Agent instance
            thread: The Thread to process
            
        Yields:
            SSE-formatted strings ready to send to an HTTP response
        """
        formatter = VercelStreamFormatter()
        
        # Message start
        yield formatter.format_message_start()

        # Per-run orchestration, step by step (turns)
        agent._iteration_count = 0
        agent._tool_attributes_cache.clear()

        while agent._iteration_count < agent.max_tool_iterations:
            async for sse in agent.step_stream(thread, mode="vercel"):
                yield sse

            if not agent._last_step_stream_should_continue:
                break

            agent._iteration_count += 1

        # If we hit max iterations, persist + stream a max-iterations message as a final step
        if agent._iteration_count >= agent.max_tool_iterations:
            message = agent.message_factory.create_max_iterations_message()
            thread.add_message(message)
            if agent.thread_store:
                await agent.thread_store.save(thread)

            # Stream it as a final step-local text block
            yield formatter.format_step_start()
            yield formatter.format_text_start()
            if message.content:
                yield formatter.format_text_delta(message.content)
            yield formatter.format_text_end()
            yield formatter.format_step_finish()

        # Message finish + done marker
        yield formatter.format_finish(FinishReason.STOP)
        yield formatter.format_done()

    async def _step_stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[str, None]:
        """Stream a single agent step as Vercel AI SDK SSE strings.

        This is the `step_stream(mode="vercel")` implementation. It yields a
        *step-local* SSE sequence and intentionally does NOT emit the message-level
        start/finish/[DONE] markers, since those belong to the full `stream(mode="vercel")`
        orchestration.

        Expected output shape:
        - start-step
        - (optional) reasoning/text/tool events for this step
        - finish-step
        """
        from tyler.streaming.events import events_stream_mode

        formatter = VercelStreamFormatter()

        # Step start
        yield formatter.format_step_start()

        text_open = False
        reasoning_open = False

        async for event in events_stream_mode._step_stream(agent, thread):
            if event.type == EventType.LLM_THINKING_CHUNK:
                if not reasoning_open:
                    yield formatter.format_reasoning_start()
                    reasoning_open = True
                thinking_chunk = event.data.get("thinking_chunk", "")
                if thinking_chunk:
                    yield formatter.format_reasoning_delta(thinking_chunk)

            elif event.type == EventType.LLM_STREAM_CHUNK:
                # Close reasoning block if transitioning to text
                if reasoning_open:
                    yield formatter.format_reasoning_end()
                    reasoning_open = False
                if not text_open:
                    yield formatter.format_text_start()
                    text_open = True
                content_chunk = event.data.get("content_chunk", "")
                if content_chunk:
                    yield formatter.format_text_delta(content_chunk)

            elif event.type == EventType.LLM_RESPONSE:
                if text_open:
                    yield formatter.format_text_end()
                    text_open = False
                if reasoning_open:
                    yield formatter.format_reasoning_end()
                    reasoning_open = False

            elif event.type == EventType.TOOL_SELECTED:
                tool_id = event.data.get("tool_call_id", "")
                tool_name = event.data.get("tool_name", "")
                args = event.data.get("arguments", {})
                yield formatter.format_tool_input_start(tool_id, tool_name)
                yield formatter.format_tool_input_available(tool_id, tool_name, args)

            elif event.type == EventType.TOOL_RESULT:
                tool_id = event.data.get("tool_call_id", "")
                result = event.data.get("result", "")
                yield formatter.format_tool_output_available(tool_id, {"result": result})

            elif event.type == EventType.TOOL_ERROR:
                tool_id = event.data.get("tool_call_id", "")
                error = event.data.get("error", "Tool execution failed")
                yield formatter.format_tool_output_error(tool_id, error)

            elif event.type == EventType.EXECUTION_ERROR:
                error_msg = event.data.get("message", "Execution error")
                yield formatter.format_error(error_msg)

        # Close any open blocks and finish the step
        if text_open:
            yield formatter.format_text_end()
        if reasoning_open:
            yield formatter.format_reasoning_end()
        yield formatter.format_step_finish()


# Singleton instance for use by the Agent
vercel_stream_mode = VercelStreamMode()
