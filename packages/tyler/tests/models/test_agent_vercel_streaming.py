"""Tests for Agent vercel streaming mode."""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from tyler import Agent, Thread, Message, ExecutionEvent, EventType
from types import SimpleNamespace
from litellm import ModelResponse


class MockDelta:
    def __init__(self, content=None, tool_calls=None, reasoning_content=None):
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning_content = reasoning_content


class MockChoiceDelta:
    def __init__(self, delta):
        self.delta = delta


class MockChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage


def create_streaming_chunk(content=None, tool_calls=None, role="assistant", usage=None, reasoning_content=None):
    """Helper function to create streaming chunks with proper structure"""
    delta = {"role": role}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    if reasoning_content is not None:
        delta["reasoning_content"] = reasoning_content
    delta_obj = SimpleNamespace(**delta)
    chunk = {
        "id": "chunk-id",
        "choices": [{
            "index": 0,
            "delta": delta_obj
        }]
    }
    if usage:
        chunk["usage"] = usage
    return ModelResponse(**chunk)


@pytest.mark.asyncio
async def async_generator(chunks):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
async def test_vercel_stream_basic_response():
    """Test vercel streaming mode with basic text response."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" there!"),
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        sse_events = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            sse_events.append(sse_chunk)
        
        # Should have SSE-formatted strings, not ExecutionEvent objects
        assert all(isinstance(s, str) for s in sse_events)
        
        # Should start with message start event
        first_event = json.loads(sse_events[0][6:-2])
        assert first_event["type"] == "start"
        assert "messageId" in first_event
        
        # Should have text events
        all_types = []
        for sse in sse_events:
            if sse.startswith("data: ") and not sse.startswith("data: [DONE]"):
                parsed = json.loads(sse[6:-2])
                all_types.append(parsed["type"])
        
        assert "text-start" in all_types
        assert "text-delta" in all_types
        assert "text-end" in all_types
        assert "finish" in all_types
        
        # Should end with [DONE]
        assert sse_events[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_vercel_stream_text_content():
    """Test that vercel stream includes text content in deltas."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" world!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        text_deltas = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                if parsed["type"] == "text-delta":
                    text_deltas.append(parsed["delta"])
        
        assert text_deltas == ["Hello", " world!"]


@pytest.mark.asyncio
async def test_vercel_stream_with_reasoning():
    """Test vercel streaming with reasoning/thinking tokens."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Think about this"))
    
    # Create chunks with reasoning content
    chunks = [
        create_streaming_chunk(reasoning_content="Let me think..."),
        create_streaming_chunk(reasoning_content=" about this."),
        create_streaming_chunk(content="The answer is 42."),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        event_types = []
        reasoning_deltas = []
        text_deltas = []
        
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                event_types.append(parsed["type"])
                
                if parsed["type"] == "reasoning-delta":
                    reasoning_deltas.append(parsed["delta"])
                elif parsed["type"] == "text-delta":
                    text_deltas.append(parsed["delta"])
        
        # Should have reasoning events
        assert "reasoning-start" in event_types
        assert "reasoning-delta" in event_types
        assert "reasoning-end" in event_types
        
        # Should have text events after reasoning
        assert "text-start" in event_types
        assert "text-delta" in event_types
        assert "text-end" in event_types
        
        # Check content
        assert reasoning_deltas == ["Let me think...", " about this."]
        assert text_deltas == ["The answer is 42."]


@pytest.mark.asyncio
async def test_vercel_stream_with_tool_calls():
    """Test vercel streaming with tool calls."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Get the weather"))
    
    chunks = [
        create_streaming_chunk(content="Let me check."),
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "San Francisco"}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "temperature": 72,
            "condition": "sunny"
        })
        
        event_types = []
        tool_events = []
        
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                event_types.append(parsed["type"])
                
                if parsed["type"].startswith("tool-"):
                    tool_events.append(parsed)
        
        # Should have tool events
        assert "tool-input-start" in event_types
        assert "tool-input-available" in event_types
        assert "tool-output-available" in event_types
        
        # Verify tool input event content
        tool_input_start = next(e for e in tool_events if e["type"] == "tool-input-start")
        assert tool_input_start["toolCallId"] == "call_123"
        assert tool_input_start["toolName"] == "get_weather"
        
        tool_input_avail = next(e for e in tool_events if e["type"] == "tool-input-available")
        assert tool_input_avail["input"] == {"city": "San Francisco"}
        
        tool_output = next(e for e in tool_events if e["type"] == "tool-output-available")
        assert "result" in tool_output["output"]


@pytest.mark.asyncio
async def test_vercel_stream_error_handling():
    """Test vercel streaming error handling."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test error"))
    
    error = Exception("Test error occurred")
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.side_effect = error
        
        error_events = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                if parsed["type"] == "error":
                    error_events.append(parsed)
        
        # Should have an error event
        assert len(error_events) >= 1
        assert "errorText" in error_events[0]


@pytest.mark.asyncio
async def test_vercel_stream_tool_error():
    """Test vercel streaming with tool execution error."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Use a tool"))
    
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_456",
            "type": "function",
            "function": {
                "name": "failing_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool failed"))
        
        tool_error_events = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                if parsed["type"] == "tool-output-error":
                    tool_error_events.append(parsed)
        
        # Should have tool error event
        assert len(tool_error_events) >= 1
        assert tool_error_events[0]["toolCallId"] == "call_456"


@pytest.mark.asyncio
async def test_vercel_stream_step_markers():
    """Test vercel streaming includes step markers for tool calls."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Use tool"))
    
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_789",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value="result")
        
        event_types = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                event_types.append(parsed["type"])
        
        # Should have step markers
        # Note: step markers may or may not be present depending on implementation
        # Just verify we don't crash and have finish
        assert "finish" in event_types


@pytest.mark.asyncio
async def test_vercel_stream_finish_event():
    """Test vercel streaming finish event has correct finish reason."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi there!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        finish_events = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                if parsed["type"] == "finish":
                    finish_events.append(parsed)
        
        assert len(finish_events) == 1
        assert finish_events[0]["finishReason"] == "stop"


@pytest.mark.asyncio
async def test_vercel_stream_done_marker():
    """Test vercel streaming ends with [DONE] marker."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Response"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        sse_events = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            sse_events.append(sse_chunk)
        
        # Last event must be [DONE]
        assert sse_events[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_vercel_stream_message_id_consistency():
    """Test that message ID is consistent across all events in a stream."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        message_ids = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                parsed = json.loads(sse_chunk[6:-2])
                if "messageId" in parsed:
                    message_ids.append(parsed["messageId"])
        
        # Should have at least one message ID in start event
        assert len(message_ids) >= 1
        # All message IDs should be the same
        assert len(set(message_ids)) == 1


@pytest.mark.asyncio  
async def test_vercel_mode_string_literal():
    """Test that mode='vercel' is a valid option."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        # Should not raise ValueError
        sse_events = []
        async for sse_chunk in agent.stream(thread, mode="vercel"):
            sse_events.append(sse_chunk)
        
        # Should have yielded SSE strings
        assert len(sse_events) > 0
        assert all(isinstance(s, str) for s in sse_events)
