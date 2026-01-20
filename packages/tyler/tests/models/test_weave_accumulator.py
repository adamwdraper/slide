"""
Tests for the _weave_stream_accumulator function.

This module tests that the Weave stream accumulator correctly captures
content and thinking tokens across all streaming modes:
- events: ExecutionEvent objects
- openai: Raw LiteLLM chunks with choices[].delta
- vercel: SSE-formatted strings
- vercel_objects: Dict chunks with "type" key
"""
import pytest
from types import SimpleNamespace
from tyler.models.agent import _weave_stream_accumulator
from tyler.models.execution import ExecutionEvent, EventType
from datetime import datetime, timezone


# =============================================================================
# Events Mode Tests
# =============================================================================

class TestEventsMode:
    """Tests for events mode (ExecutionEvent objects)."""
    
    def test_content_accumulation(self):
        """Test that content chunks are accumulated correctly."""
        state = None
        
        # Simulate streaming content chunks
        event1 = ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            timestamp=datetime.now(timezone.utc),
            data={"content_chunk": "Hello, "}
        )
        event2 = ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            timestamp=datetime.now(timezone.utc),
            data={"content_chunk": "world!"}
        )
        
        state = _weave_stream_accumulator(state, event1)
        state = _weave_stream_accumulator(state, event2)
        
        assert state["mode"] == "events"
        assert state["content"] == "Hello, world!"
        assert state["events"]["counts"]["llm_stream_chunk"] == 2
    
    def test_thinking_accumulation(self):
        """Test that thinking chunks are accumulated correctly."""
        state = None
        
        event1 = ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            timestamp=datetime.now(timezone.utc),
            data={"thinking_chunk": "Let me think..."}
        )
        event2 = ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            timestamp=datetime.now(timezone.utc),
            data={"thinking_chunk": " about this."}
        )
        
        state = _weave_stream_accumulator(state, event1)
        state = _weave_stream_accumulator(state, event2)
        
        assert state["mode"] == "events"
        assert state["thinking"] == "Let me think... about this."
        assert state["events"]["counts"]["llm_thinking_chunk"] == 2
    
    def test_mixed_thinking_and_content(self):
        """Test that thinking and content are accumulated separately."""
        state = None
        
        # Thinking first, then content
        thinking_event = ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            timestamp=datetime.now(timezone.utc),
            data={"thinking_chunk": "Reasoning here"}
        )
        content_event = ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            timestamp=datetime.now(timezone.utc),
            data={"content_chunk": "Final answer"}
        )
        
        state = _weave_stream_accumulator(state, thinking_event)
        state = _weave_stream_accumulator(state, content_event)
        
        assert state["thinking"] == "Reasoning here"
        assert state["content"] == "Final answer"
    
    def test_tool_selection(self):
        """Test that tool selection events are captured."""
        state = None
        
        event = ExecutionEvent(
            type=EventType.TOOL_SELECTED,
            timestamp=datetime.now(timezone.utc),
            data={
                "tool_name": "web_search",
                "tool_call_id": "call_123",
                "arguments": {"query": "test"}
            }
        )
        
        state = _weave_stream_accumulator(state, event)
        
        assert len(state["tools"]) == 1
        assert state["tools"][0]["tool_name"] == "web_search"
        assert state["tools"][0]["status"] == "selected"
    
    def test_tool_result(self):
        """Test that tool result events are captured."""
        state = None
        
        event = ExecutionEvent(
            type=EventType.TOOL_RESULT,
            timestamp=datetime.now(timezone.utc),
            data={
                "tool_name": "web_search",
                "tool_call_id": "call_123",
                "result": "Search results...",
                "duration_ms": 150
            }
        )
        
        state = _weave_stream_accumulator(state, event)
        
        assert len(state["tools"]) == 1
        assert state["tools"][0]["status"] == "result"
        assert state["tools"][0]["duration_ms"] == 150
    
    def test_tool_error(self):
        """Test that tool error events are captured."""
        state = None
        
        event = ExecutionEvent(
            type=EventType.TOOL_ERROR,
            timestamp=datetime.now(timezone.utc),
            data={
                "tool_name": "web_search",
                "tool_call_id": "call_123",
                "error": "Connection failed"
            }
        )
        
        state = _weave_stream_accumulator(state, event)
        
        assert len(state["errors"]) == 1
        assert state["errors"][0]["error"] == "Connection failed"


# =============================================================================
# OpenAI Mode Tests
# =============================================================================

class TestOpenAIMode:
    """Tests for OpenAI mode (raw LiteLLM chunks)."""
    
    def _create_chunk(self, content=None, reasoning_content=None, thinking=None, extended_thinking=None):
        """Helper to create a mock LiteLLM chunk."""
        delta = SimpleNamespace()
        if content is not None:
            delta.content = content
        if reasoning_content is not None:
            delta.reasoning_content = reasoning_content
        if thinking is not None:
            delta.thinking = thinking
        if extended_thinking is not None:
            delta.extended_thinking = extended_thinking
        
        choice = SimpleNamespace(delta=delta)
        chunk = SimpleNamespace(choices=[choice])
        return chunk
    
    def test_content_accumulation(self):
        """Test that content is accumulated from delta.content."""
        state = None
        
        chunk1 = self._create_chunk(content="Hello, ")
        chunk2 = self._create_chunk(content="world!")
        
        state = _weave_stream_accumulator(state, chunk1)
        state = _weave_stream_accumulator(state, chunk2)
        
        assert state["mode"] == "openai"
        assert state["content"] == "Hello, world!"
    
    def test_reasoning_content_accumulation(self):
        """Test that reasoning_content is accumulated as thinking."""
        state = None
        
        chunk1 = self._create_chunk(reasoning_content="Let me think...")
        chunk2 = self._create_chunk(reasoning_content=" about this.")
        
        state = _weave_stream_accumulator(state, chunk1)
        state = _weave_stream_accumulator(state, chunk2)
        
        assert state["mode"] == "openai"
        assert state["thinking"] == "Let me think... about this."
    
    def test_thinking_attribute_accumulation(self):
        """Test that delta.thinking is accumulated (alternative provider format)."""
        state = None
        
        chunk = self._create_chunk(thinking="Provider-specific thinking")
        state = _weave_stream_accumulator(state, chunk)
        
        assert state["thinking"] == "Provider-specific thinking"
    
    def test_extended_thinking_accumulation(self):
        """Test that delta.extended_thinking is accumulated."""
        state = None
        
        chunk = self._create_chunk(extended_thinking="Extended reasoning")
        state = _weave_stream_accumulator(state, chunk)
        
        assert state["thinking"] == "Extended reasoning"
    
    def test_mixed_content_and_reasoning(self):
        """Test that content and reasoning are accumulated separately."""
        state = None
        
        # First reasoning, then content
        chunk1 = self._create_chunk(reasoning_content="Thinking...")
        chunk2 = self._create_chunk(content="Answer")
        
        state = _weave_stream_accumulator(state, chunk1)
        state = _weave_stream_accumulator(state, chunk2)
        
        assert state["thinking"] == "Thinking..."
        assert state["content"] == "Answer"
    
    def test_both_content_and_reasoning_in_same_chunk(self):
        """Test chunk with both content and reasoning_content."""
        state = None
        
        chunk = self._create_chunk(content="Answer", reasoning_content="Thinking")
        state = _weave_stream_accumulator(state, chunk)
        
        assert state["content"] == "Answer"
        assert state["thinking"] == "Thinking"


# =============================================================================
# Vercel Objects Mode Tests
# =============================================================================

class TestVercelObjectsMode:
    """Tests for Vercel objects mode (dict chunks with "type" key)."""
    
    def test_text_delta_accumulation(self):
        """Test that text-delta chunks are accumulated as content."""
        state = None
        
        chunk1 = {"type": "text-delta", "id": "text_1", "delta": "Hello, "}
        chunk2 = {"type": "text-delta", "id": "text_1", "delta": "world!"}
        
        state = _weave_stream_accumulator(state, chunk1)
        state = _weave_stream_accumulator(state, chunk2)
        
        assert state["mode"] == "vercel_objects"
        assert state["content"] == "Hello, world!"
    
    def test_reasoning_delta_accumulation(self):
        """Test that reasoning-delta chunks are accumulated as thinking."""
        state = None
        
        chunk1 = {"type": "reasoning-delta", "id": "r_1", "delta": "Let me "}
        chunk2 = {"type": "reasoning-delta", "id": "r_1", "delta": "think..."}
        
        state = _weave_stream_accumulator(state, chunk1)
        state = _weave_stream_accumulator(state, chunk2)
        
        assert state["mode"] == "vercel_objects"
        assert state["thinking"] == "Let me think..."
    
    def test_mixed_reasoning_and_text(self):
        """Test that reasoning and text are accumulated separately."""
        state = None
        
        # Reasoning first, then text
        r_chunk = {"type": "reasoning-delta", "id": "r_1", "delta": "Reasoning"}
        t_chunk = {"type": "text-delta", "id": "t_1", "delta": "Answer"}
        
        state = _weave_stream_accumulator(state, r_chunk)
        state = _weave_stream_accumulator(state, t_chunk)
        
        assert state["thinking"] == "Reasoning"
        assert state["content"] == "Answer"
    
    def test_tool_input_available(self):
        """Test that tool-input-available chunks are captured."""
        state = None
        
        chunk = {
            "type": "tool-input-available",
            "toolCallId": "call_123",
            "toolName": "web_search",
            "input": {"query": "test"}
        }
        
        state = _weave_stream_accumulator(state, chunk)
        
        assert len(state["tools"]) == 1
        assert state["tools"][0]["tool_name"] == "web_search"
        assert state["tools"][0]["tool_call_id"] == "call_123"
        assert state["tools"][0]["status"] == "selected"
    
    def test_tool_output_available(self):
        """Test that tool-output-available chunks are captured."""
        state = None
        
        chunk = {
            "type": "tool-output-available",
            "toolCallId": "call_123",
            "output": {"result": "Search results"}
        }
        
        state = _weave_stream_accumulator(state, chunk)
        
        assert len(state["tools"]) == 1
        assert state["tools"][0]["status"] == "result"
        assert state["tools"][0]["result"] == {"result": "Search results"}
    
    def test_tool_output_error(self):
        """Test that tool-output-error chunks are captured."""
        state = None
        
        chunk = {
            "type": "tool-output-error",
            "toolCallId": "call_123",
            "errorText": "Tool failed"
        }
        
        state = _weave_stream_accumulator(state, chunk)
        
        assert len(state["errors"]) == 1
        assert state["errors"][0]["error"] == "Tool failed"
    
    def test_error_chunk(self):
        """Test that error chunks are captured."""
        state = None
        
        chunk = {"type": "error", "errorText": "Something went wrong"}
        state = _weave_stream_accumulator(state, chunk)
        
        assert len(state["errors"]) == 1
        assert state["errors"][0]["error"] == "Something went wrong"
    
    def test_empty_delta_ignored(self):
        """Test that empty deltas don't add empty strings."""
        state = None
        
        chunk = {"type": "text-delta", "id": "t_1", "delta": ""}
        state = _weave_stream_accumulator(state, chunk)
        
        assert state["content"] == ""  # Should remain empty string from init
    
    def test_other_chunk_types_ignored(self):
        """Test that non-content chunk types don't break accumulation."""
        state = None
        
        # These should be ignored gracefully
        chunks = [
            {"type": "start", "messageId": "msg_1"},
            {"type": "text-start", "id": "t_1"},
            {"type": "text-end", "id": "t_1"},
            {"type": "finish", "finishReason": "stop"},
        ]
        
        for chunk in chunks:
            state = _weave_stream_accumulator(state, chunk)
        
        # Should have mode set but no content
        assert state["mode"] == "vercel_objects"
        assert state["content"] == ""
        assert state["thinking"] == ""


# =============================================================================
# Vercel SSE Mode Tests
# =============================================================================

class TestVercelSSEMode:
    """Tests for Vercel SSE mode (SSE-formatted strings)."""
    
    def test_text_delta_accumulation(self):
        """Test that text-delta SSE chunks are accumulated as content."""
        state = None
        
        sse1 = 'data: {"type": "text-delta", "id": "t_1", "delta": "Hello, "}\n\n'
        sse2 = 'data: {"type": "text-delta", "id": "t_1", "delta": "world!"}\n\n'
        
        state = _weave_stream_accumulator(state, sse1)
        state = _weave_stream_accumulator(state, sse2)
        
        assert state["mode"] == "vercel"
        assert state["content"] == "Hello, world!"
    
    def test_reasoning_delta_accumulation(self):
        """Test that reasoning-delta SSE chunks are accumulated as thinking."""
        state = None
        
        sse1 = 'data: {"type": "reasoning-delta", "id": "r_1", "delta": "Thinking "}\n\n'
        sse2 = 'data: {"type": "reasoning-delta", "id": "r_1", "delta": "deeply..."}\n\n'
        
        state = _weave_stream_accumulator(state, sse1)
        state = _weave_stream_accumulator(state, sse2)
        
        assert state["mode"] == "vercel"
        assert state["thinking"] == "Thinking deeply..."
    
    def test_mixed_reasoning_and_text(self):
        """Test that reasoning and text SSE are accumulated separately."""
        state = None
        
        sse_r = 'data: {"type": "reasoning-delta", "id": "r_1", "delta": "Reasoning"}\n\n'
        sse_t = 'data: {"type": "text-delta", "id": "t_1", "delta": "Answer"}\n\n'
        
        state = _weave_stream_accumulator(state, sse_r)
        state = _weave_stream_accumulator(state, sse_t)
        
        assert state["thinking"] == "Reasoning"
        assert state["content"] == "Answer"
    
    def test_tool_input_available(self):
        """Test that tool-input-available SSE chunks are captured."""
        state = None
        
        sse = 'data: {"type": "tool-input-available", "toolCallId": "call_1", "toolName": "search", "input": {"q": "test"}}\n\n'
        state = _weave_stream_accumulator(state, sse)
        
        assert len(state["tools"]) == 1
        assert state["tools"][0]["tool_name"] == "search"
        assert state["tools"][0]["status"] == "selected"
    
    def test_tool_output_available(self):
        """Test that tool-output-available SSE chunks are captured."""
        state = None
        
        sse = 'data: {"type": "tool-output-available", "toolCallId": "call_1", "output": {"result": "found"}}\n\n'
        state = _weave_stream_accumulator(state, sse)
        
        assert len(state["tools"]) == 1
        assert state["tools"][0]["status"] == "result"
    
    def test_tool_output_error(self):
        """Test that tool-output-error SSE chunks are captured."""
        state = None
        
        sse = 'data: {"type": "tool-output-error", "toolCallId": "call_1", "errorText": "Failed"}\n\n'
        state = _weave_stream_accumulator(state, sse)
        
        assert len(state["errors"]) == 1
        assert state["errors"][0]["error"] == "Failed"
    
    def test_error_chunk(self):
        """Test that error SSE chunks are captured."""
        state = None
        
        sse = 'data: {"type": "error", "errorText": "Server error"}\n\n'
        state = _weave_stream_accumulator(state, sse)
        
        assert len(state["errors"]) == 1
        assert state["errors"][0]["error"] == "Server error"
    
    def test_done_marker_ignored(self):
        """Test that [DONE] marker is ignored gracefully."""
        state = None
        
        sse1 = 'data: {"type": "text-delta", "id": "t_1", "delta": "Hello"}\n\n'
        sse_done = 'data: [DONE]\n\n'
        
        state = _weave_stream_accumulator(state, sse1)
        state = _weave_stream_accumulator(state, sse_done)
        
        assert state["content"] == "Hello"  # Should not be affected
    
    def test_malformed_sse_ignored(self):
        """Test that malformed SSE is ignored gracefully."""
        state = None
        
        sse_good = 'data: {"type": "text-delta", "id": "t_1", "delta": "Hello"}\n\n'
        sse_bad = 'data: {invalid json}\n\n'
        
        state = _weave_stream_accumulator(state, sse_good)
        state = _weave_stream_accumulator(state, sse_bad)
        
        # Should still have content from good chunk
        assert state["content"] == "Hello"
        # Should not have errored out
        assert state["mode"] == "vercel"
    
    def test_non_sse_string_not_parsed(self):
        """Test that non-SSE strings fall through to OpenAI mode."""
        state = None
        
        # A string that doesn't start with "data: "
        non_sse = "Just a plain string"
        state = _weave_stream_accumulator(state, non_sse)
        
        # Should fall through to OpenAI mode (which won't find choices)
        assert state["mode"] == "openai"


# =============================================================================
# Edge Cases and State Initialization
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and state initialization."""
    
    def test_initial_state_creation(self):
        """Test that initial state is created correctly."""
        state = _weave_stream_accumulator(None, {"type": "start"})
        
        assert state["mode"] is not None
        assert state["content"] == ""
        assert state["thinking"] == ""
        assert state["tools"] == []
        assert state["errors"] == []
        assert state["events"] == {"counts": {}}
        assert state["metrics"] == {}
    
    def test_state_persistence(self):
        """Test that state persists across accumulator calls."""
        state = None
        
        # First call creates state
        state = _weave_stream_accumulator(state, {"type": "text-delta", "delta": "A"})
        assert state["content"] == "A"
        
        # Second call uses existing state
        state = _weave_stream_accumulator(state, {"type": "text-delta", "delta": "B"})
        assert state["content"] == "AB"
    
    def test_none_values_handled(self):
        """Test that None values in chunks don't cause errors."""
        state = None
        
        # Chunk with None delta
        chunk = {"type": "text-delta", "id": "t_1", "delta": None}
        state = _weave_stream_accumulator(state, chunk)
        
        # Should not crash, content should remain empty
        assert state["content"] == ""
    
    def test_mode_consistency(self):
        """Test that mode is set on first chunk and preserved."""
        state = None
        
        # First chunk sets mode
        state = _weave_stream_accumulator(state, {"type": "text-delta", "delta": "A"})
        assert state["mode"] == "vercel_objects"
        
        # Mode should not change on subsequent chunks
        # (In practice, streams don't mix modes, but the first detection should stick)
        original_mode = state["mode"]
        state = _weave_stream_accumulator(state, {"type": "text-delta", "delta": "B"})
        assert state["mode"] == original_mode
