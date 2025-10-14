"""
Tests for thinking tokens support in Tyler streaming.

Following TDD approach:
1. Write failing test
2. Implement minimal code to pass
3. Refactor while keeping tests green
"""

import pytest
from unittest.mock import AsyncMock, patch
from tyler import Agent, Thread, Message, EventType
from litellm import ModelResponse
from types import SimpleNamespace


def create_streaming_chunk_with_thinking(content=None, reasoning_content=None, role="assistant"):
    """Helper to create streaming chunks with thinking/reasoning tokens"""
    delta = {"role": role}
    if content is not None:
        delta["content"] = content
    if reasoning_content is not None:
        delta["reasoning_content"] = reasoning_content
    
    delta_obj = SimpleNamespace(**delta)
    chunk = {
        "id": "chunk-id",
        "choices": [{
            "index": 0,
            "delta": delta_obj,
            "finish_reason": None
        }]
    }
    return ModelResponse(**chunk)


@pytest.mark.asyncio
async def test_thinking_chunks_emitted_for_anthropic():
    """
    AC1: Test that thinking chunks are emitted as separate events from content.
    
    Given: An agent using a reasoning-capable model (Anthropic Claude)
    When: The model emits reasoning_content in streaming chunks
    Then: LLM_THINKING_CHUNK events are emitted separately from LLM_STREAM_CHUNK events
    """
    # Arrange: Create agent with Anthropic model
    agent = Agent(
        name="thinking-agent",
        model_name="anthropic/claude-3-7-sonnet-20250219"
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="What is 2+2?"
    ))
    
    # Mock LiteLLM streaming response with reasoning_content
    mock_chunks = [
        # First chunk: Thinking/reasoning
        create_streaming_chunk_with_thinking(reasoning_content="Let me calculate this..."),
        # Second chunk: More thinking
        create_streaming_chunk_with_thinking(reasoning_content="2 plus 2 equals 4."),
        # Third chunk: Actual content/response
        create_streaming_chunk_with_thinking(content="The answer is 4."),
        # Final chunk with finish
        create_streaming_chunk_with_thinking(content=""),
    ]
    mock_chunks[-1].choices[0].finish_reason = "stop"
    
    async def mock_streaming_response():
        for chunk in mock_chunks:
            yield chunk
    
    # Act: Stream the response
    with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
        mock_step.return_value = (mock_streaming_response(), {})
        
        events = []
        async for event in agent.go(thread, stream=True):
            events.append(event)
    
    # Assert: Verify thinking and content events are separated
    # Should have: LLM_REQUEST, LLM_THINKING_CHUNK (x2), LLM_STREAM_CHUNK, LLM_RESPONSE, MESSAGE_CREATED, EXECUTION_COMPLETE
    
    thinking_events = [e for e in events if e.type == EventType.LLM_THINKING_CHUNK]
    content_events = [e for e in events if e.type == EventType.LLM_STREAM_CHUNK]
    
    # Verify thinking chunks were emitted
    assert len(thinking_events) == 2, f"Expected 2 thinking events, got {len(thinking_events)}"
    assert thinking_events[0].data["thinking_chunk"] == "Let me calculate this..."
    assert thinking_events[1].data["thinking_chunk"] == "2 plus 2 equals 4."
    assert thinking_events[0].data["thinking_type"] == "reasoning"
    
    # Verify content chunks were emitted separately
    assert len(content_events) >= 1, f"Expected at least 1 content event, got {len(content_events)}"
    assert content_events[0].data["content_chunk"] == "The answer is 4."
    
    # Verify thinking and content are NOT mixed
    for thinking_event in thinking_events:
        assert "content_chunk" not in thinking_event.data, "Thinking events should not contain content"
    
    for content_event in content_events:
        assert "thinking_chunk" not in content_event.data, "Content events should not contain thinking"


@pytest.mark.asyncio
async def test_reasoning_stored_in_message_top_level():
    """
    AC2: Test that reasoning_content is stored as top-level Message field.
    
    Given: Streaming completes with thinking tokens
    When: The assistant Message is created
    Then: The Message has reasoning_content as a top-level field
    And: reasoning_content is NOT in metrics
    """
    # Arrange
    agent = Agent(
        name="thinking-agent",
        model_name="anthropic/claude-3-7-sonnet-20250219",
        reasoning="low"  # Updated to use unified parameter
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock streaming with thinking
    mock_chunks = [
        create_streaming_chunk_with_thinking(reasoning_content="Thinking..."),
        create_streaming_chunk_with_thinking(content="Answer."),
    ]
    mock_chunks[-1].choices[0].finish_reason = "stop"
    
    async def mock_streaming_response():
        for chunk in mock_chunks:
            yield chunk
    
    # Act
    with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
        mock_step.return_value = (mock_streaming_response(), {})
        
        events = []
        async for event in agent.go(thread, stream=True):
            events.append(event)
    
    # Assert: Check message has reasoning as top-level field
    message_events = [e for e in events if e.type == EventType.MESSAGE_CREATED]
    assistant_messages = [e.data["message"] for e in message_events if e.data["message"].role == "assistant"]
    
    assert len(assistant_messages) >= 1, "Should have at least one assistant message"
    
    assistant_msg = assistant_messages[0]
    # Check top-level field
    assert hasattr(assistant_msg, 'reasoning_content'), "Message should have reasoning_content attribute"
    assert assistant_msg.reasoning_content == "Thinking...", "reasoning_content should contain thinking text"
    # Verify NOT in metrics
    assert "reasoning_content" not in assistant_msg.metrics, "reasoning_content should NOT be in metrics"


@pytest.mark.asyncio
async def test_non_reasoning_model_no_thinking_events():
    """
    AC5: Test that non-reasoning models work unchanged (no thinking events).
    
    Given: An agent using a non-reasoning model (GPT-4)
    When: Streaming a response
    Then: No LLM_THINKING_CHUNK events are emitted
    And: Regular LLM_STREAM_CHUNK events work as before
    """
    # Arrange
    agent = Agent(
        name="regular-agent",
        model_name="gpt-4"
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Mock streaming WITHOUT reasoning_content
    mock_chunks = [
        create_streaming_chunk_with_thinking(content="Hello! "),
        create_streaming_chunk_with_thinking(content="How can I help?"),
    ]
    mock_chunks[-1].choices[0].finish_reason = "stop"
    
    async def mock_streaming_response():
        for chunk in mock_chunks:
            yield chunk
    
    # Act
    with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
        mock_step.return_value = (mock_streaming_response(), {})
        
        events = []
        async for event in agent.go(thread, stream=True):
            events.append(event)
    
    # Assert: No thinking events, but content events present
    thinking_events = [e for e in events if e.type == EventType.LLM_THINKING_CHUNK]
    content_events = [e for e in events if e.type == EventType.LLM_STREAM_CHUNK]
    
    assert len(thinking_events) == 0, "Non-reasoning model should not emit thinking events"
    assert len(content_events) >= 2, "Content events should work normally"


@pytest.mark.asyncio
async def test_malformed_reasoning_graceful_degradation():
    """
    Negative case: Test graceful handling of malformed reasoning data.
    
    Given: LiteLLM returns malformed reasoning data
    When: Tyler processes the chunks
    Then: Tyler gracefully skips the malformed thinking
    And: Regular content streaming continues normally
    """
    # Arrange
    agent = Agent(name="test-agent", model_name="anthropic/claude-3-7-sonnet-20250219")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock with malformed reasoning_content (None, empty, weird type)
    chunk1 = create_streaming_chunk_with_thinking(reasoning_content=None)
    chunk2 = create_streaming_chunk_with_thinking(content="Good content")
    chunk2.choices[0].finish_reason = "stop"
    
    mock_chunks = [chunk1, chunk2]
    
    async def mock_streaming_response():
        for chunk in mock_chunks:
            yield chunk
    
    # Act - Should not raise exception
    with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
        mock_step.return_value = (mock_streaming_response(), {})
        
        events = []
        async for event in agent.go(thread, stream=True):
            events.append(event)
    
    # Assert: Content streaming worked despite malformed thinking
    content_events = [e for e in events if e.type == EventType.LLM_STREAM_CHUNK]
    assert len(content_events) >= 1, "Content streaming should continue"
    
    # No exception was raised (if we got here, test passes)

