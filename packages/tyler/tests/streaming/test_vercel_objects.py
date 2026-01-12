"""Tests for vercel_objects streaming mode and VercelObjectsFormatter."""
import pytest
from tyler.streaming.vercel_objects import (
    VercelObjectsFormatter,
    VercelObjectsStreamMode,
    vercel_objects_stream_mode,
)
from tyler.streaming.vercel_protocol import FinishReason


class TestVercelObjectsFormatter:
    """Tests for VercelObjectsFormatter class."""

    def test_formatter_generates_message_id(self):
        """Test that formatter auto-generates a message ID."""
        formatter = VercelObjectsFormatter()
        assert formatter.message_id.startswith("msg_")
        
    def test_formatter_accepts_custom_message_id(self):
        """Test that formatter accepts a custom message ID."""
        formatter = VercelObjectsFormatter(message_id="custom_msg_123")
        assert formatter.message_id == "custom_msg_123"

    def test_create_message_start(self):
        """Test create_message_start returns correct dict."""
        formatter = VercelObjectsFormatter(message_id="test_msg")
        result = formatter.create_message_start()
        
        assert isinstance(result, dict)
        assert result["type"] == "start"
        assert result["messageId"] == "test_msg"
        
    def test_create_message_start_with_metadata(self):
        """Test create_message_start includes metadata when provided."""
        formatter = VercelObjectsFormatter(message_id="test_msg")
        result = formatter.create_message_start(metadata={"custom": "data"})
        
        assert result["type"] == "start"
        assert result["messageMetadata"] == {"custom": "data"}

    def test_create_text_start(self):
        """Test create_text_start returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_text_start()
        
        assert isinstance(result, dict)
        assert result["type"] == "text-start"
        assert "id" in result
        assert result["id"].startswith("text_")
        
    def test_create_text_delta(self):
        """Test create_text_delta returns correct dict."""
        formatter = VercelObjectsFormatter()
        formatter.create_text_start()  # Must start first
        result = formatter.create_text_delta("Hello, world!")
        
        assert isinstance(result, dict)
        assert result["type"] == "text-delta"
        assert result["delta"] == "Hello, world!"
        assert "id" in result
        
    def test_create_text_delta_requires_start(self):
        """Test create_text_delta raises error if text not started."""
        formatter = VercelObjectsFormatter()
        with pytest.raises(ValueError, match="create_text_start.*must be called"):
            formatter.create_text_delta("test")
            
    def test_create_text_end(self):
        """Test create_text_end returns correct dict."""
        formatter = VercelObjectsFormatter()
        formatter.create_text_start()
        result = formatter.create_text_end()
        
        assert isinstance(result, dict)
        assert result["type"] == "text-end"
        assert "id" in result
        
    def test_create_text_end_requires_start(self):
        """Test create_text_end raises error if text not started."""
        formatter = VercelObjectsFormatter()
        with pytest.raises(ValueError, match="create_text_start.*must be called"):
            formatter.create_text_end()

    def test_create_reasoning_start(self):
        """Test create_reasoning_start returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_reasoning_start()
        
        assert isinstance(result, dict)
        assert result["type"] == "reasoning-start"
        assert "id" in result
        assert result["id"].startswith("reasoning_")
        
    def test_create_reasoning_delta(self):
        """Test create_reasoning_delta returns correct dict."""
        formatter = VercelObjectsFormatter()
        formatter.create_reasoning_start()
        result = formatter.create_reasoning_delta("thinking about this...")
        
        assert isinstance(result, dict)
        assert result["type"] == "reasoning-delta"
        assert result["delta"] == "thinking about this..."
        assert "id" in result
        
    def test_create_reasoning_delta_requires_start(self):
        """Test create_reasoning_delta raises error if reasoning not started."""
        formatter = VercelObjectsFormatter()
        with pytest.raises(ValueError, match="create_reasoning_start.*must be called"):
            formatter.create_reasoning_delta("test")
            
    def test_create_reasoning_end(self):
        """Test create_reasoning_end returns correct dict."""
        formatter = VercelObjectsFormatter()
        formatter.create_reasoning_start()
        result = formatter.create_reasoning_end()
        
        assert isinstance(result, dict)
        assert result["type"] == "reasoning-end"
        assert "id" in result
        
    def test_create_reasoning_end_requires_start(self):
        """Test create_reasoning_end raises error if reasoning not started."""
        formatter = VercelObjectsFormatter()
        with pytest.raises(ValueError, match="create_reasoning_start.*must be called"):
            formatter.create_reasoning_end()

    def test_create_tool_input_start(self):
        """Test create_tool_input_start returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_tool_input_start("call_123", "get_weather")
        
        assert isinstance(result, dict)
        assert result["type"] == "tool-input-start"
        assert result["toolCallId"] == "call_123"
        assert result["toolName"] == "get_weather"
        
    def test_create_tool_input_available(self):
        """Test create_tool_input_available returns correct dict."""
        formatter = VercelObjectsFormatter()
        args = {"city": "San Francisco", "units": "celsius"}
        result = formatter.create_tool_input_available("call_123", "get_weather", args)
        
        assert isinstance(result, dict)
        assert result["type"] == "tool-input-available"
        assert result["toolCallId"] == "call_123"
        assert result["toolName"] == "get_weather"
        assert result["input"] == args

    def test_create_tool_output_available_with_dict(self):
        """Test create_tool_output_available with dict output."""
        formatter = VercelObjectsFormatter()
        output = {"temperature": 72, "condition": "sunny"}
        result = formatter.create_tool_output_available("call_123", output)
        
        assert isinstance(result, dict)
        assert result["type"] == "tool-output-available"
        assert result["toolCallId"] == "call_123"
        assert result["output"] == output
        
    def test_create_tool_output_available_with_string(self):
        """Test create_tool_output_available wraps string output in result dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_tool_output_available("call_123", "Success!")
        
        assert isinstance(result, dict)
        assert result["type"] == "tool-output-available"
        assert result["output"] == {"result": "Success!"}
        
    def test_create_tool_output_error(self):
        """Test create_tool_output_error returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_tool_output_error("call_123", "API rate limit exceeded")
        
        assert isinstance(result, dict)
        assert result["type"] == "tool-output-error"
        assert result["toolCallId"] == "call_123"
        assert result["errorText"] == "API rate limit exceeded"

    def test_create_step_start(self):
        """Test create_step_start returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_step_start()
        
        assert isinstance(result, dict)
        assert result["type"] == "start-step"
        
    def test_create_step_finish(self):
        """Test create_step_finish returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_step_finish()
        
        assert isinstance(result, dict)
        assert result["type"] == "finish-step"

    def test_create_error(self):
        """Test create_error returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_error("Something went wrong")
        
        assert isinstance(result, dict)
        assert result["type"] == "error"
        assert result["errorText"] == "Something went wrong"

    def test_create_finish(self):
        """Test create_finish returns correct dict."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_finish()
        
        assert isinstance(result, dict)
        assert result["type"] == "finish"
        
    def test_create_finish_with_reason(self):
        """Test create_finish includes finish reason when provided."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_finish(FinishReason.STOP)
        
        assert result["type"] == "finish"
        assert result["finishReason"] == "stop"
        
    def test_create_finish_with_tool_calls_reason(self):
        """Test create_finish with tool-calls finish reason."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_finish(FinishReason.TOOL_CALLS)
        
        assert result["finishReason"] == "tool-calls"
        
    def test_create_finish_with_metadata(self):
        """Test create_finish includes metadata when provided."""
        formatter = VercelObjectsFormatter()
        result = formatter.create_finish(metadata={"tokens": 100})
        
        assert result["type"] == "finish"
        assert result["messageMetadata"] == {"tokens": 100}

    def test_text_started_property(self):
        """Test text_started property tracks state correctly."""
        formatter = VercelObjectsFormatter()
        assert formatter.text_started is False
        
        formatter.create_text_start()
        assert formatter.text_started is True
        
        formatter.create_text_end()
        assert formatter.text_started is False
        
    def test_reasoning_started_property(self):
        """Test reasoning_started property tracks state correctly."""
        formatter = VercelObjectsFormatter()
        assert formatter.reasoning_started is False
        
        formatter.create_reasoning_start()
        assert formatter.reasoning_started is True
        
        formatter.create_reasoning_end()
        assert formatter.reasoning_started is False


class TestVercelObjectsStreamMode:
    """Tests for VercelObjectsStreamMode class."""
    
    def test_stream_mode_name(self):
        """Test that stream mode has correct name."""
        mode = VercelObjectsStreamMode()
        assert mode.name == "vercel_objects"
        
    def test_singleton_instance_exists(self):
        """Test that singleton instance is available."""
        assert vercel_objects_stream_mode is not None
        assert isinstance(vercel_objects_stream_mode, VercelObjectsStreamMode)


class TestCompleteStreamSequence:
    """Integration tests for complete streaming sequences."""

    def test_simple_text_stream(self):
        """Test a complete simple text streaming sequence."""
        formatter = VercelObjectsFormatter(message_id="msg_test")
        
        events = [
            formatter.create_message_start(),
            formatter.create_text_start(),
            formatter.create_text_delta("Hello"),
            formatter.create_text_delta(", "),
            formatter.create_text_delta("world!"),
            formatter.create_text_end(),
            formatter.create_finish(FinishReason.STOP),
        ]
        
        # Verify all events are dicts with type field
        for event in events:
            assert isinstance(event, dict)
            assert "type" in event
            
        # Verify sequence of types
        types = [e["type"] for e in events]
        assert types == [
            "start",
            "text-start",
            "text-delta",
            "text-delta",
            "text-delta",
            "text-end",
            "finish",
        ]
        
    def test_stream_with_reasoning_then_text(self):
        """Test streaming that transitions from reasoning to text."""
        formatter = VercelObjectsFormatter()
        
        events = [
            formatter.create_message_start(),
            formatter.create_reasoning_start(),
            formatter.create_reasoning_delta("Let me think..."),
            formatter.create_reasoning_delta(" The answer is..."),
            formatter.create_reasoning_end(),
            formatter.create_text_start(),
            formatter.create_text_delta("42"),
            formatter.create_text_end(),
            formatter.create_finish(FinishReason.STOP),
        ]
        
        types = [e["type"] for e in events]
            
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
        formatter = VercelObjectsFormatter()
        
        events = [
            formatter.create_message_start(),
            formatter.create_text_start(),
            formatter.create_text_delta("Let me check the weather."),
            formatter.create_text_end(),
            formatter.create_step_start(),
            formatter.create_tool_input_start("call_123", "get_weather"),
            formatter.create_tool_input_available("call_123", "get_weather", {"city": "SF"}),
            formatter.create_tool_output_available("call_123", {"temp": 72}),
            formatter.create_step_finish(),
            formatter.create_text_start(),
            formatter.create_text_delta("It's 72°F in SF."),
            formatter.create_text_end(),
            formatter.create_finish(FinishReason.STOP),
        ]
        
        types = [e["type"] for e in events]
            
        assert "tool-input-start" in types
        assert "tool-input-available" in types
        assert "tool-output-available" in types
        assert types.index("start-step") < types.index("tool-input-start")
        assert types.index("tool-output-available") < types.index("finish-step")


class TestMarimoCompatibility:
    """Tests for marimo integration compatibility."""
    
    def test_chunk_format_matches_marimo_expected_format(self):
        """Test that chunks match what marimo expects for vercel_messages=True."""
        formatter = VercelObjectsFormatter()
        
        # marimo expects chunks like:
        # {"type": "text-delta", "id": "text-1", "delta": "Hello"}
        
        formatter.create_text_start()
        chunk = formatter.create_text_delta("Hello")
        
        # Verify required fields for marimo
        assert "type" in chunk
        assert chunk["type"] == "text-delta"
        assert "id" in chunk
        assert "delta" in chunk
        assert chunk["delta"] == "Hello"
        
    def test_chunk_uses_camel_case_keys(self):
        """Test that chunk keys use camelCase as marimo/Vercel SDK expects."""
        formatter = VercelObjectsFormatter()
        
        # Tool-related chunks should use camelCase
        tool_start = formatter.create_tool_input_start("call_123", "search")
        assert "toolCallId" in tool_start  # camelCase, not tool_call_id
        assert "toolName" in tool_start    # camelCase, not tool_name
        
        tool_input = formatter.create_tool_input_available("call_123", "search", {"q": "test"})
        assert "toolCallId" in tool_input
        assert "toolName" in tool_input
        
        tool_output = formatter.create_tool_output_available("call_123", {"result": "found"})
        assert "toolCallId" in tool_output
        
        # Finish chunk should use camelCase
        finish = formatter.create_finish(FinishReason.STOP)
        assert "finishReason" in finish  # camelCase, not finish_reason
        
        # Start chunk should use camelCase  
        start = formatter.create_message_start()
        assert "messageId" in start  # camelCase, not message_id
        
    def test_yields_dicts_not_pydantic_objects(self):
        """Test that formatter yields plain dicts, not pydantic objects."""
        formatter = VercelObjectsFormatter()
        
        chunk = formatter.create_text_start()
        
        # Should be a plain dict
        assert isinstance(chunk, dict)
        assert type(chunk) is dict  # Not a subclass
        
        # Should not have pydantic methods
        assert not hasattr(chunk, "model_dump")
        assert not hasattr(chunk, "dict")
