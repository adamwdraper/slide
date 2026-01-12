"""Vercel AI SDK Data Stream Protocol streaming mode (object/dict output).

This module provides the VercelObjectsStreamMode which yields chunk dictionaries
directly, suitable for integration with frameworks like marimo's mo.ui.chat()
that expect Vercel chunk objects rather than SSE strings.

Protocol reference: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol
"""
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional, Union
import uuid

from tyler.models.execution import EventType
from tyler.streaming.base import BaseStreamMode
from tyler.streaming.vercel_protocol import (
    FinishReason,
    TextStartChunk,
    TextDeltaChunk,
    TextEndChunk,
    ReasoningStartChunk,
    ReasoningDeltaChunk,
    ReasoningEndChunk,
    ToolInputStartChunk,
    ToolInputAvailableChunk,
    ToolOutputAvailableChunk,
    ToolOutputErrorChunk,
    ErrorChunk,
    StartStepChunk,
    FinishStepChunk,
    StartChunk,
    FinishChunk,
    UIMessageChunk,
)

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from tyler.models.thread import Thread


class VercelObjectsFormatter:
    """Generates Vercel AI SDK chunk dictionaries (without SSE wrapping).
    
    This formatter is identical to VercelStreamFormatter but returns raw
    chunk dicts instead of SSE-formatted strings. This is useful for
    frameworks like marimo that expect chunk objects directly.
    """
    
    def __init__(self, message_id: Optional[str] = None):
        self.message_id = message_id or f"msg_{uuid.uuid4().hex}"
        self._text_id: Optional[str] = None
        self._reasoning_id: Optional[str] = None
        self._text_started: bool = False
        self._reasoning_started: bool = False
    
    def create_message_start(self, metadata: Optional[Dict[str, Any]] = None) -> StartChunk:
        """Create start chunk."""
        chunk: StartChunk = {"type": "start", "messageId": self.message_id}
        if metadata is not None:
            chunk["messageMetadata"] = metadata
        return chunk
    
    def create_text_start(self) -> TextStartChunk:
        """Create text-start chunk."""
        self._text_id = f"text_{uuid.uuid4().hex[:24]}"
        self._text_started = True
        return {"type": "text-start", "id": self._text_id}
    
    def create_text_delta(self, content: str) -> TextDeltaChunk:
        """Create text-delta chunk."""
        if self._text_id is None:
            raise ValueError("create_text_start() must be called before create_text_delta()")
        return {"type": "text-delta", "id": self._text_id, "delta": content}
    
    def create_text_end(self) -> TextEndChunk:
        """Create text-end chunk."""
        if self._text_id is None:
            raise ValueError("create_text_start() must be called before create_text_end()")
        self._text_started = False
        return {"type": "text-end", "id": self._text_id}
    
    def create_reasoning_start(self) -> ReasoningStartChunk:
        """Create reasoning-start chunk."""
        self._reasoning_id = f"reasoning_{uuid.uuid4().hex[:16]}"
        self._reasoning_started = True
        return {"type": "reasoning-start", "id": self._reasoning_id}
    
    def create_reasoning_delta(self, content: str) -> ReasoningDeltaChunk:
        """Create reasoning-delta chunk."""
        if self._reasoning_id is None:
            raise ValueError("create_reasoning_start() must be called before create_reasoning_delta()")
        return {"type": "reasoning-delta", "id": self._reasoning_id, "delta": content}
    
    def create_reasoning_end(self) -> ReasoningEndChunk:
        """Create reasoning-end chunk."""
        if self._reasoning_id is None:
            raise ValueError("create_reasoning_start() must be called before create_reasoning_end()")
        self._reasoning_started = False
        return {"type": "reasoning-end", "id": self._reasoning_id}
    
    def create_tool_input_start(self, tool_call_id: str, tool_name: str) -> ToolInputStartChunk:
        """Create tool-input-start chunk."""
        return {
            "type": "tool-input-start",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
        }
    
    def create_tool_input_available(
        self,
        tool_call_id: str,
        tool_name: str,
        input_args: Dict[str, Any],
    ) -> ToolInputAvailableChunk:
        """Create tool-input-available chunk."""
        return {
            "type": "tool-input-available",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
            "input": input_args,
        }
    
    def create_tool_output_available(
        self,
        tool_call_id: str,
        output: Any,
    ) -> ToolOutputAvailableChunk:
        """Create tool-output-available chunk."""
        if not isinstance(output, dict):
            output = {"result": str(output)}
        return {
            "type": "tool-output-available",
            "toolCallId": tool_call_id,
            "output": output,
        }
    
    def create_tool_output_error(self, tool_call_id: str, error_text: str) -> ToolOutputErrorChunk:
        """Create tool-output-error chunk."""
        return {
            "type": "tool-output-error",
            "toolCallId": tool_call_id,
            "errorText": error_text,
        }
    
    def create_step_start(self) -> StartStepChunk:
        """Create start-step chunk."""
        return {"type": "start-step"}
    
    def create_step_finish(self) -> FinishStepChunk:
        """Create finish-step chunk."""
        return {"type": "finish-step"}
    
    def create_error(self, error_text: str) -> ErrorChunk:
        """Create error chunk."""
        return {"type": "error", "errorText": error_text}
    
    def create_finish(
        self,
        finish_reason: Optional[FinishReason] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FinishChunk:
        """Create finish chunk."""
        chunk: FinishChunk = {"type": "finish"}
        if finish_reason is not None:
            chunk["finishReason"] = finish_reason.value
        if metadata is not None:
            chunk["messageMetadata"] = metadata
        return chunk
    
    @property
    def text_started(self) -> bool:
        """Whether a text block is currently open."""
        return self._text_started
    
    @property
    def reasoning_started(self) -> bool:
        """Whether a reasoning block is currently open."""
        return self._reasoning_started


class VercelObjectsStreamMode(BaseStreamMode):
    """Streaming mode that yields Vercel AI SDK chunk dictionaries.
    
    This mode transforms ExecutionEvents into chunk dictionaries compatible
    with the Vercel AI SDK protocol, but without SSE formatting. This is 
    ideal for integration with frameworks like marimo's mo.ui.chat() that
    expect Vercel chunk objects directly.
    
    Best for:
    - marimo mo.ui.chat(vercel_messages=True) integration
    - Custom frontends that handle chunk objects directly
    - Python-native streaming consumers
    """
    
    @property
    def name(self) -> str:
        return "vercel_objects"
    
    async def stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[UIMessageChunk, None]:
        """Stream chunk dictionaries for Vercel AI SDK.
        
        This method orchestrates the full agent run by repeatedly calling
        `agent.step_stream(..., mode="vercel_objects")` until completion.
        
        Args:
            agent: The Agent instance
            thread: The Thread to process
            
        Yields:
            Vercel AI SDK chunk dictionaries
        """
        formatter = VercelObjectsFormatter()
        
        # Message start
        yield formatter.create_message_start()

        # Per-run orchestration, step by step (turns)
        agent._iteration_count = 0
        agent._tool_attributes_cache.clear()

        while agent._iteration_count < agent.max_tool_iterations:
            async for chunk in agent.step_stream(thread, mode="vercel_objects"):
                yield chunk

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
            yield formatter.create_step_start()
            yield formatter.create_text_start()
            if message.content:
                yield formatter.create_text_delta(message.content)
            yield formatter.create_text_end()
            yield formatter.create_step_finish()

        # Message finish (no [DONE] marker for object mode)
        yield formatter.create_finish(FinishReason.STOP)

    async def _step_stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[UIMessageChunk, None]:
        """Stream a single agent step as Vercel AI SDK chunk dictionaries.

        This is the `step_stream(mode="vercel_objects")` implementation.

        Expected output shape:
        - start-step
        - (optional) reasoning/text/tool events for this step
        - finish-step
        """
        from tyler.streaming.events import events_stream_mode

        formatter = VercelObjectsFormatter()

        # Step start
        yield formatter.create_step_start()

        text_open = False
        reasoning_open = False

        async for event in events_stream_mode._step_stream(agent, thread):
            if event.type == EventType.LLM_THINKING_CHUNK:
                if not reasoning_open:
                    yield formatter.create_reasoning_start()
                    reasoning_open = True
                thinking_chunk = event.data.get("thinking_chunk", "")
                if thinking_chunk:
                    yield formatter.create_reasoning_delta(thinking_chunk)

            elif event.type == EventType.LLM_STREAM_CHUNK:
                # Close reasoning block if transitioning to text
                if reasoning_open:
                    yield formatter.create_reasoning_end()
                    reasoning_open = False
                if not text_open:
                    yield formatter.create_text_start()
                    text_open = True
                content_chunk = event.data.get("content_chunk", "")
                if content_chunk:
                    yield formatter.create_text_delta(content_chunk)

            elif event.type == EventType.LLM_RESPONSE:
                if text_open:
                    yield formatter.create_text_end()
                    text_open = False
                if reasoning_open:
                    yield formatter.create_reasoning_end()
                    reasoning_open = False

            elif event.type == EventType.TOOL_SELECTED:
                tool_id = event.data.get("tool_call_id", "")
                tool_name = event.data.get("tool_name", "")
                args = event.data.get("arguments", {})
                yield formatter.create_tool_input_start(tool_id, tool_name)
                yield formatter.create_tool_input_available(tool_id, tool_name, args)

            elif event.type == EventType.TOOL_RESULT:
                tool_id = event.data.get("tool_call_id", "")
                result = event.data.get("result", "")
                yield formatter.create_tool_output_available(tool_id, {"result": result})

            elif event.type == EventType.TOOL_ERROR:
                tool_id = event.data.get("tool_call_id", "")
                error = event.data.get("error", "Tool execution failed")
                yield formatter.create_tool_output_error(tool_id, error)

            elif event.type == EventType.EXECUTION_ERROR:
                error_msg = event.data.get("message", "Execution error")
                yield formatter.create_error(error_msg)

        # Close any open blocks and finish the step
        if text_open:
            yield formatter.create_text_end()
        if reasoning_open:
            yield formatter.create_reasoning_end()
        yield formatter.create_step_finish()


# Singleton instance for use by the Agent
vercel_objects_stream_mode = VercelObjectsStreamMode()
