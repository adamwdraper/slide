import pytest
from datetime import datetime, UTC
from narrator import Message, Attachment


def test_message_creation():
    """Test creating a basic message"""
    message = Message(role="user", content="Hello world")
    
    assert message.role == "user"
    assert message.content == "Hello world"
    assert message.sequence is None  # Not set until added to thread
    assert message.turn is None  # Not set until added to thread
    assert isinstance(message.timestamp, datetime)
    assert message.timestamp.tzinfo == UTC
    assert message.id is not None  # Should generate ID


def test_message_with_turn():
    """Test message with explicit turn assignment"""
    message = Message(role="assistant", content="Response", turn=5, sequence=10)
    
    assert message.turn == 5
    assert message.sequence == 10


def test_message_turn_in_serialization():
    """Test that turn field is included in message serialization"""
    message = Message(role="user", content="Test", turn=3, sequence=7)
    
    # Test JSON serialization
    data = message.model_dump(mode="json")
    assert data["turn"] == 3
    assert data["sequence"] == 7
    assert data["role"] == "user"
    assert data["content"] == "Test"
    
    # Test Python serialization
    python_data = message.model_dump(mode="python")
    assert python_data["turn"] == 3
    assert isinstance(python_data["timestamp"], datetime)


def test_message_chat_completion_format():
    """Test that turn field is excluded from chat completion format"""
    message = Message(role="assistant", content="Hello", turn=2, sequence=5)
    
    chat_format = message.to_chat_completion_message()
    
    assert chat_format["role"] == "assistant"
    assert chat_format["content"] == "Hello"
    assert chat_format["sequence"] == 5
    assert "turn" not in chat_format  # Should not include turn field


def test_message_id_includes_turn():
    """Test that message ID generation includes turn field"""
    # Create two identical messages except for turn
    msg1 = Message(role="user", content="Hello", turn=1, sequence=1)
    msg2 = Message(role="user", content="Hello", turn=2, sequence=1)
    
    # IDs should be different because turn is different
    assert msg1.id != msg2.id


def test_tool_message_validation():
    """Test that tool messages require tool_call_id"""
    # Valid tool message
    tool_msg = Message(
        role="tool",
        content="Tool result",
        tool_call_id="call_123",
        turn=1
    )
    assert tool_msg.role == "tool"
    assert tool_msg.tool_call_id == "call_123"
    assert tool_msg.turn == 1
    
    # Invalid tool message (missing tool_call_id)
    with pytest.raises(ValueError, match="tool_call_id is required for tool messages"):
        Message(role="tool", content="Tool result")


def test_message_with_attachments():
    """Test message with attachments includes turn data"""
    attachment = Attachment(filename="test.txt", content=b"Test content")
    message = Message(
        role="user",
        content="Message with file",
        attachments=[attachment],
        turn=3,
        sequence=8
    )
    
    assert message.turn == 3
    assert message.sequence == 8
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "test.txt"


def test_message_with_tool_calls():
    """Test assistant message with tool calls includes turn data"""
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_function",
            "arguments": '{"param": "value"}'
        }
    }
    
    message = Message(
        role="assistant",
        content="Using tool",
        tool_calls=[tool_call],
        turn=2,
        sequence=4
    )
    
    assert message.turn == 2
    assert message.sequence == 4
    assert len(message.tool_calls) == 1
    assert message.tool_calls[0]["id"] == "call_123"


def test_message_reactions_with_turns():
    """Test message reactions work with turn data"""
    message = Message(role="user", content="Hello", turn=1, sequence=1)
    
    # Add reactions
    assert message.add_reaction(":thumbsup:", "user1")
    assert message.add_reaction(":heart:", "user2")
    
    # Verify reactions
    reactions = message.get_reactions()
    assert ":thumbsup:" in reactions
    assert ":heart:" in reactions
    assert "user1" in reactions[":thumbsup:"]
    assert "user2" in reactions[":heart:"]
    
    # Turn data should be preserved
    assert message.turn == 1
    assert message.sequence == 1


def test_message_metrics_with_turns():
    """Test message metrics work with turn data"""
    message = Message(
        role="assistant",
        content="Response",
        turn=3,
        sequence=7,
        metrics={
            "model": "gpt-4.1",
            "usage": {
                "completion_tokens": 50,
                "prompt_tokens": 25,
                "total_tokens": 75
            },
            "timing": {
                "latency": 1500.0
            }
        }
    )
    
    assert message.turn == 3
    assert message.sequence == 7
    assert message.metrics["model"] == "gpt-4.1"
    assert message.metrics["usage"]["total_tokens"] == 75
    assert message.metrics["timing"]["latency"] == 1500.0


def test_message_source_with_turns():
    """Test message source information with turn data"""
    source = {
        "id": "agent_123",
        "name": "GPT-4",
        "type": "agent"
    }
    
    message = Message(
        role="assistant",
        content="AI response",
        source=source,
        turn=2,
        sequence=5
    )
    
    assert message.turn == 2
    assert message.sequence == 5
    assert message.source["id"] == "agent_123"
    assert message.source["name"] == "GPT-4"
    assert message.source["type"] == "agent"


def test_message_platforms_with_turns():
    """Test message platform data with turn data"""
    platforms = {
        "slack": {
            "channel": "C123456",
            "ts": "1234567890.123456"
        }
    }
    
    message = Message(
        role="user",
        content="Slack message",
        platforms=platforms,
        turn=1,
        sequence=3
    )
    
    assert message.turn == 1
    assert message.sequence == 3
    assert message.platforms["slack"]["channel"] == "C123456"
    assert message.platforms["slack"]["ts"] == "1234567890.123456"


def test_multimodal_message_with_turns():
    """Test multimodal message (text + image) with turn data"""
    content = [
        {"type": "text", "text": "Check this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc123"}}
    ]
    
    message = Message(
        role="user",
        content=content,
        turn=4,
        sequence=9
    )
    
    assert message.turn == 4
    assert message.sequence == 9
    assert isinstance(message.content, list)
    assert len(message.content) == 2
    assert message.content[0]["type"] == "text"
    assert message.content[1]["type"] == "image_url"


def test_message_validation():
    """Test message field validation"""
    # Valid roles
    for role in ["system", "user", "assistant", "tool"]:
        if role == "tool":
            msg = Message(role=role, content="Test", tool_call_id="call_123")
        else:
            msg = Message(role=role, content="Test")
        assert msg.role == role
    
    # Invalid role
    with pytest.raises(Exception):  # Pydantic raises ValidationError for literal type errors
        Message(role="invalid", content="Test")


def test_message_turn_none_handling():
    """Test that messages handle None turn values properly"""
    message = Message(role="user", content="Test")
    
    # Turn should be None initially
    assert message.turn is None
    assert message.sequence is None
    
    # Should serialize properly with None values
    data = message.model_dump()
    assert data["turn"] is None
    assert data["sequence"] is None 