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
        
        This method internally uses events mode and transforms the events
        into the Vercel AI SDK Data Stream Protocol format.
        
        Args:
            agent: The Agent instance
            thread: The Thread to process
            
        Yields:
            SSE-formatted strings ready to send to an HTTP response
        """
        from tyler.streaming.events import events_stream_mode
        
        formatter = VercelStreamFormatter()
        
        # Message start
        yield formatter.format_message_start()
        
        text_open = False
        reasoning_open = False
        step_open = False
        
        async for event in events_stream_mode.stream(agent, thread):
            # Handle iteration/step boundaries
            if event.type == EventType.ITERATION_START:
                if not step_open:
                    yield formatter.format_step_start()
                    step_open = True
            
            # Reasoning/thinking chunks
            elif event.type == EventType.LLM_THINKING_CHUNK:
                if not reasoning_open:
                    yield formatter.format_reasoning_start()
                    reasoning_open = True
                thinking_chunk = event.data.get("thinking_chunk", "")
                if thinking_chunk:
                    yield formatter.format_reasoning_delta(thinking_chunk)
            
            # Text content chunks
            elif event.type == EventType.LLM_STREAM_CHUNK:
                # Close reasoning block if transitioning to text
                if reasoning_open:
                    yield formatter.format_reasoning_end()
                    reasoning_open = False
                # Start text block if not already open
                if not text_open:
                    yield formatter.format_text_start()
                    text_open = True
                content_chunk = event.data.get("content_chunk", "")
                if content_chunk:
                    yield formatter.format_text_delta(content_chunk)
            
            # LLM response complete (end of content stream for this step)
            elif event.type == EventType.LLM_RESPONSE:
                if text_open:
                    yield formatter.format_text_end()
                    text_open = False
                if reasoning_open:
                    yield formatter.format_reasoning_end()
                    reasoning_open = False
            
            # Tool selected - emit tool input
            elif event.type == EventType.TOOL_SELECTED:
                tool_id = event.data.get("tool_call_id", "")
                tool_name = event.data.get("tool_name", "")
                args = event.data.get("arguments", {})
                
                yield formatter.format_tool_input_start(tool_id, tool_name)
                yield formatter.format_tool_input_available(tool_id, tool_name, args)
            
            # Tool result
            elif event.type == EventType.TOOL_RESULT:
                tool_id = event.data.get("tool_call_id", "")
                result = event.data.get("result", "")
                yield formatter.format_tool_output_available(tool_id, {"result": result})
                # Finish step after tool results
                if step_open:
                    yield formatter.format_step_finish()
                    step_open = False
            
            # Tool error
            elif event.type == EventType.TOOL_ERROR:
                tool_id = event.data.get("tool_call_id", "")
                error = event.data.get("error", "Tool execution failed")
                yield formatter.format_tool_output_error(tool_id, error)
            
            # Execution error
            elif event.type == EventType.EXECUTION_ERROR:
                error_msg = event.data.get("message", "Execution error")
                yield formatter.format_error(error_msg)
            
            # Execution complete
            elif event.type == EventType.EXECUTION_COMPLETE:
                # Close any open blocks
                if text_open:
                    yield formatter.format_text_end()
                    text_open = False
                if reasoning_open:
                    yield formatter.format_reasoning_end()
                    reasoning_open = False
                if step_open:
                    yield formatter.format_step_finish()
                    step_open = False
                
                yield formatter.format_finish(FinishReason.STOP)
                yield formatter.format_done()


# Singleton instance for use by the Agent
vercel_stream_mode = VercelStreamMode()
