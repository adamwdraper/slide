"""Tests for Vercel AI SDK Data Stream Protocol implementation."""
import json
import pytest
from tyler.streaming.vercel_protocol import (
    VercelStreamFormatter,
    VERCEL_STREAM_HEADERS,
    FinishReason,
    to_sse,
    done_sse,
)


class TestVercelStreamHeaders:
    """Tests for VERCEL_STREAM_HEADERS constant."""

    def test_headers_contains_required_fields(self):
        """Test that headers include all required fields for Vercel AI SDK."""
        assert "content-type" in VERCEL_STREAM_HEADERS
        assert VERCEL_STREAM_HEADERS["content-type"] == "text/event-stream"
        
    def test_headers_contains_cache_control(self):
        """Test cache-control header is set correctly."""
        assert "cache-control" in VERCEL_STREAM_HEADERS
        assert VERCEL_STREAM_HEADERS["cache-control"] == "no-cache"
        
    def test_headers_contains_connection(self):
        """Test connection header is set correctly."""
        assert "connection" in VERCEL_STREAM_HEADERS
        assert VERCEL_STREAM_HEADERS["connection"] == "keep-alive"
        
    def test_headers_contains_vercel_version(self):
        """Test x-vercel-ai-ui-message-stream header is set to v1."""
        assert "x-vercel-ai-ui-message-stream" in VERCEL_STREAM_HEADERS
        assert VERCEL_STREAM_HEADERS["x-vercel-ai-ui-message-stream"] == "v1"
        
    def test_headers_contains_nginx_buffering(self):
        """Test x-accel-buffering header disables nginx buffering."""
        assert "x-accel-buffering" in VERCEL_STREAM_HEADERS
        assert VERCEL_STREAM_HEADERS["x-accel-buffering"] == "no"


class TestSSEFormatting:
    """Tests for SSE formatting functions."""

    def test_to_sse_formats_dict_correctly(self):
        """Test that to_sse formats a dict as SSE."""
        chunk = {"type": "text-delta", "id": "123", "delta": "Hello"}
        result = to_sse(chunk)
        
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        
        # Parse the JSON content
        json_content = result[6:-2]  # Remove "data: " and "\n\n"
        parsed = json.loads(json_content)
        assert parsed == chunk
        
    def test_done_sse_returns_done_marker(self):
        """Test that done_sse returns the [DONE] marker."""
        result = done_sse()
        assert result == "data: [DONE]\n\n"


class TestVercelStreamFormatter:
    """Tests for VercelStreamFormatter class."""

    def test_formatter_generates_message_id(self):
        """Test that formatter auto-generates a message ID."""
        formatter = VercelStreamFormatter()
        assert formatter.message_id.startswith("msg_")
        
    def test_formatter_accepts_custom_message_id(self):
        """Test that formatter accepts a custom message ID."""
        formatter = VercelStreamFormatter(message_id="custom_msg_123")
        assert formatter.message_id == "custom_msg_123"

    def test_format_message_start(self):
        """Test format_message_start creates correct SSE event."""
        formatter = VercelStreamFormatter(message_id="test_msg")
        result = formatter.format_message_start()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "start"
        assert parsed["messageId"] == "test_msg"
        
    def test_format_message_start_with_metadata(self):
        """Test format_message_start includes metadata when provided."""
        formatter = VercelStreamFormatter(message_id="test_msg")
        result = formatter.format_message_start(metadata={"custom": "data"})
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "start"
        assert parsed["messageMetadata"] == {"custom": "data"}

    def test_format_text_start(self):
        """Test format_text_start creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_text_start()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "text-start"
        assert "id" in parsed
        assert parsed["id"].startswith("text_")
        
    def test_format_text_delta(self):
        """Test format_text_delta creates correct SSE event."""
        formatter = VercelStreamFormatter()
        formatter.format_text_start()  # Must start first
        result = formatter.format_text_delta("Hello, world!")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "text-delta"
        assert parsed["delta"] == "Hello, world!"
        assert "id" in parsed
        
    def test_format_text_delta_requires_start(self):
        """Test format_text_delta raises error if text not started."""
        formatter = VercelStreamFormatter()
        with pytest.raises(ValueError, match="format_text_start.*must be called"):
            formatter.format_text_delta("test")
            
    def test_format_text_end(self):
        """Test format_text_end creates correct SSE event."""
        formatter = VercelStreamFormatter()
        formatter.format_text_start()
        result = formatter.format_text_end()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "text-end"
        assert "id" in parsed
        
    def test_format_text_end_requires_start(self):
        """Test format_text_end raises error if text not started."""
        formatter = VercelStreamFormatter()
        with pytest.raises(ValueError, match="format_text_start.*must be called"):
            formatter.format_text_end()

    def test_format_reasoning_start(self):
        """Test format_reasoning_start creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_reasoning_start()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "reasoning-start"
        assert "id" in parsed
        assert parsed["id"].startswith("reasoning_")
        
    def test_format_reasoning_delta(self):
        """Test format_reasoning_delta creates correct SSE event."""
        formatter = VercelStreamFormatter()
        formatter.format_reasoning_start()
        result = formatter.format_reasoning_delta("thinking about this...")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "reasoning-delta"
        assert parsed["delta"] == "thinking about this..."
        assert "id" in parsed
        
    def test_format_reasoning_delta_requires_start(self):
        """Test format_reasoning_delta raises error if reasoning not started."""
        formatter = VercelStreamFormatter()
        with pytest.raises(ValueError, match="format_reasoning_start.*must be called"):
            formatter.format_reasoning_delta("test")
            
    def test_format_reasoning_end(self):
        """Test format_reasoning_end creates correct SSE event."""
        formatter = VercelStreamFormatter()
        formatter.format_reasoning_start()
        result = formatter.format_reasoning_end()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "reasoning-end"
        assert "id" in parsed
        
    def test_format_reasoning_end_requires_start(self):
        """Test format_reasoning_end raises error if reasoning not started."""
        formatter = VercelStreamFormatter()
        with pytest.raises(ValueError, match="format_reasoning_start.*must be called"):
            formatter.format_reasoning_end()

    def test_format_tool_input_start(self):
        """Test format_tool_input_start creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_tool_input_start("call_123", "get_weather")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "tool-input-start"
        assert parsed["toolCallId"] == "call_123"
        assert parsed["toolName"] == "get_weather"
        
    def test_format_tool_input_delta(self):
        """Test format_tool_input_delta creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_tool_input_delta("call_123", '{"city":')
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "tool-input-delta"
        assert parsed["toolCallId"] == "call_123"
        assert parsed["inputTextDelta"] == '{"city":'
        
    def test_format_tool_input_available(self):
        """Test format_tool_input_available creates correct SSE event."""
        formatter = VercelStreamFormatter()
        args = {"city": "San Francisco", "units": "celsius"}
        result = formatter.format_tool_input_available("call_123", "get_weather", args)
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "tool-input-available"
        assert parsed["toolCallId"] == "call_123"
        assert parsed["toolName"] == "get_weather"
        assert parsed["input"] == args

    def test_format_tool_output_available_with_dict(self):
        """Test format_tool_output_available with dict output."""
        formatter = VercelStreamFormatter()
        output = {"temperature": 72, "condition": "sunny"}
        result = formatter.format_tool_output_available("call_123", output)
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "tool-output-available"
        assert parsed["toolCallId"] == "call_123"
        assert parsed["output"] == output
        
    def test_format_tool_output_available_with_string(self):
        """Test format_tool_output_available wraps string output in result dict."""
        formatter = VercelStreamFormatter()
        result = formatter.format_tool_output_available("call_123", "Success!")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "tool-output-available"
        assert parsed["output"] == {"result": "Success!"}
        
    def test_format_tool_output_error(self):
        """Test format_tool_output_error creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_tool_output_error("call_123", "API rate limit exceeded")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "tool-output-error"
        assert parsed["toolCallId"] == "call_123"
        assert parsed["errorText"] == "API rate limit exceeded"

    def test_format_step_start(self):
        """Test format_step_start creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_step_start()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "start-step"
        
    def test_format_step_finish(self):
        """Test format_step_finish creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_step_finish()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "finish-step"

    def test_format_error(self):
        """Test format_error creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_error("Something went wrong")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "error"
        assert parsed["errorText"] == "Something went wrong"

    def test_format_finish(self):
        """Test format_finish creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_finish()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "finish"
        
    def test_format_finish_with_reason(self):
        """Test format_finish includes finish reason when provided."""
        formatter = VercelStreamFormatter()
        result = formatter.format_finish(FinishReason.STOP)
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "finish"
        assert parsed["finishReason"] == "stop"
        
    def test_format_finish_with_tool_calls_reason(self):
        """Test format_finish with tool-calls finish reason."""
        formatter = VercelStreamFormatter()
        result = formatter.format_finish(FinishReason.TOOL_CALLS)
        
        parsed = json.loads(result[6:-2])
        assert parsed["finishReason"] == "tool-calls"
        
    def test_format_finish_with_metadata(self):
        """Test format_finish includes metadata when provided."""
        formatter = VercelStreamFormatter()
        result = formatter.format_finish(metadata={"tokens": 100})
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "finish"
        assert parsed["messageMetadata"] == {"tokens": 100}

    def test_format_abort(self):
        """Test format_abort creates correct SSE event."""
        formatter = VercelStreamFormatter()
        result = formatter.format_abort()
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "abort"
        
    def test_format_abort_with_reason(self):
        """Test format_abort includes reason when provided."""
        formatter = VercelStreamFormatter()
        result = formatter.format_abort("User cancelled")
        
        parsed = json.loads(result[6:-2])
        assert parsed["type"] == "abort"
        assert parsed["reason"] == "User cancelled"

    def test_format_done(self):
        """Test format_done returns [DONE] marker."""
        result = VercelStreamFormatter.format_done()
        assert result == "data: [DONE]\n\n"

    def test_text_started_property(self):
        """Test text_started property tracks state correctly."""
        formatter = VercelStreamFormatter()
        assert formatter.text_started is False
        
        formatter.format_text_start()
        assert formatter.text_started is True
        
        formatter.format_text_end()
        assert formatter.text_started is False
        
    def test_reasoning_started_property(self):
        """Test reasoning_started property tracks state correctly."""
        formatter = VercelStreamFormatter()
        assert formatter.reasoning_started is False
        
        formatter.format_reasoning_start()
        assert formatter.reasoning_started is True
        
        formatter.format_reasoning_end()
        assert formatter.reasoning_started is False


class TestCompleteStream:
    """Integration tests for complete streaming sequences."""

    def test_simple_text_stream(self):
        """Test a complete simple text streaming sequence."""
        formatter = VercelStreamFormatter(message_id="msg_test")
        
        events = [
            formatter.format_message_start(),
            formatter.format_text_start(),
            formatter.format_text_delta("Hello"),
            formatter.format_text_delta(", "),
            formatter.format_text_delta("world!"),
            formatter.format_text_end(),
            formatter.format_finish(FinishReason.STOP),
            formatter.format_done(),
        ]
        
        # Verify all events are valid SSE format
        for event in events[:-1]:  # All except [DONE]
            assert event.startswith("data: ")
            assert event.endswith("\n\n")
            json.loads(event[6:-2])  # Should not raise
            
        # Verify [DONE] marker
        assert events[-1] == "data: [DONE]\n\n"
        
    def test_stream_with_reasoning_then_text(self):
        """Test streaming that transitions from reasoning to text."""
        formatter = VercelStreamFormatter()
        
        events = [
            formatter.format_message_start(),
            formatter.format_reasoning_start(),
            formatter.format_reasoning_delta("Let me think..."),
            formatter.format_reasoning_delta(" The answer is..."),
            formatter.format_reasoning_end(),
            formatter.format_text_start(),
            formatter.format_text_delta("42"),
            formatter.format_text_end(),
            formatter.format_finish(FinishReason.STOP),
            formatter.format_done(),
        ]
        
        # Extract types from events
        types = []
        for event in events[:-1]:
            parsed = json.loads(event[6:-2])
            types.append(parsed["type"])
            
        assert types == [
            "start",
            "reasoning-start",
            "reasoning-delta",
            "reasoning-delta",
            "reasoning-end",
            "text-start",
            "text-delta",
            "text-end",
            "finish",
        ]
        
    def test_stream_with_tool_call(self):
        """Test streaming with a tool call."""
        formatter = VercelStreamFormatter()
        
        events = [
            formatter.format_message_start(),
            formatter.format_text_start(),
            formatter.format_text_delta("Let me check the weather."),
            formatter.format_text_end(),
            formatter.format_step_start(),
            formatter.format_tool_input_start("call_123", "get_weather"),
            formatter.format_tool_input_available("call_123", "get_weather", {"city": "SF"}),
            formatter.format_tool_output_available("call_123", {"temp": 72}),
            formatter.format_step_finish(),
            formatter.format_text_start(),
            formatter.format_text_delta("It's 72°F in SF."),
            formatter.format_text_end(),
            formatter.format_finish(FinishReason.STOP),
            formatter.format_done(),
        ]
        
        # Extract types
        types = []
        for event in events[:-1]:
            parsed = json.loads(event[6:-2])
            types.append(parsed["type"])
            
        assert "tool-input-start" in types
        assert "tool-input-available" in types
        assert "tool-output-available" in types
        assert types.index("start-step") < types.index("tool-input-start")
        assert types.index("tool-output-available") < types.index("finish-step")


class TestFinishReason:
    """Tests for FinishReason enum."""
    
    def test_finish_reason_values(self):
        """Test that FinishReason has correct string values."""
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.CONTENT_FILTER.value == "content-filter"
        assert FinishReason.TOOL_CALLS.value == "tool-calls"
        assert FinishReason.ERROR.value == "error"
        assert FinishReason.OTHER.value == "other"
