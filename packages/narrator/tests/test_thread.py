import pytest
from datetime import datetime, UTC, timedelta
from narrator import Thread, Message, Attachment

@pytest.fixture
def sample_thread():
    """Create a sample thread for testing."""
    thread = Thread(
        id="test-thread",
        title="Test Thread",
        attributes={"category": "test"},
        platforms={
            "slack": {
                "channel": "C123",
                "thread_ts": "1234567890.123"
            }
        }
    )
    thread.add_message(Message(role="system", content="You are a helpful assistant"))
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi there!"))
    return thread

def test_create_thread():
    """Test creating a new thread"""
    thread = Thread(id="test-thread", title="Test Thread")
    assert thread.id == "test-thread"
    assert thread.title == "Test Thread"
    assert isinstance(thread.created_at, datetime)
    assert thread.created_at.tzinfo == UTC
    assert isinstance(thread.updated_at, datetime)
    assert thread.updated_at.tzinfo == UTC
    assert thread.messages == []
    assert thread.attributes == {}
    assert thread.platforms == {}

def test_add_message():
    """Test adding a message to a thread"""
    thread = Thread(id="test-thread")
    message = Message(role="user", content="Hello")
    thread.add_message(message)
    assert len(thread.messages) == 1
    assert thread.messages[0].role == "user"
    assert thread.messages[0].content == "Hello"
    assert thread.messages[0].sequence == 1

def test_thread_serialization(sample_thread):
    """Test thread serialization to/from dict"""
    # Test model_dump() with JSON mode (default)
    data = sample_thread.model_dump(mode="json")
    assert data["id"] == "test-thread"
    assert data["title"] == "Test Thread"
    assert data["attributes"] == {"category": "test"}
    assert data["platforms"]["slack"]["channel"] == "C123"
    assert data["platforms"]["slack"]["thread_ts"] == "1234567890.123"
    assert len(data["messages"]) == 3
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][1]["role"] == "user"
    assert data["messages"][2]["role"] == "assistant"
    assert isinstance(data["created_at"], str)  # Expect ISO-formatted string
    assert isinstance(data["updated_at"], str)  # Expect ISO-formatted string
    
    # Test model_dump() with Python mode
    data_with_dates = sample_thread.model_dump(mode="python")
    assert isinstance(data_with_dates["created_at"], datetime)  # Expect datetime objects
    assert isinstance(data_with_dates["updated_at"], datetime)  # Expect datetime objects
    
    # Test model_validate() with datetime objects
    new_thread = Thread.model_validate(data_with_dates)
    assert new_thread.id == sample_thread.id
    assert new_thread.title == sample_thread.title
    assert new_thread.attributes == sample_thread.attributes
    assert new_thread.platforms == sample_thread.platforms
    assert len(new_thread.messages) == len(sample_thread.messages)
    for orig_msg, new_msg in zip(sample_thread.messages, new_thread.messages):
        assert new_msg.role == orig_msg.role
        assert new_msg.content == orig_msg.content
        assert new_msg.sequence == orig_msg.sequence

@pytest.mark.asyncio
async def test_get_messages_for_chat_completion(sample_thread):
    """Test getting messages in chat completion format"""
    messages = await sample_thread.get_messages_for_chat_completion()
    # System messages are now excluded from get_messages_for_chat_completion
    assert len(messages) == 2
    assert messages[0] == {
        "role": "user",
        "content": "Hello",
        "sequence": 1
    }
    assert messages[1] == {
        "role": "assistant",
        "content": "Hi there!",
        "sequence": 2
    }

def test_message_sequencing():
    """Test message sequence numbering"""
    thread = Thread(id="test-thread")
    
    # Add messages in different order
    msg1 = Message(role="user", content="First user message")
    msg2 = Message(role="assistant", content="First assistant message")
    msg3 = Message(role="system", content="System message")
    msg4 = Message(role="user", content="Second user message")
    
    thread.add_message(msg1)  # Should get sequence 1
    thread.add_message(msg2)  # Should get sequence 2
    thread.add_message(msg3)  # Should get sequence 0 and move to front
    thread.add_message(msg4)  # Should get sequence 3
    
    # Verify sequences
    assert len(thread.messages) == 4
    assert thread.messages[0].role == "system"
    assert thread.messages[0].sequence == 0
    
    # Get non-system messages in order
    non_system = [m for m in thread.messages if m.role != "system"]
    assert len(non_system) == 3
    assert non_system[0].content == "First user message"
    assert non_system[0].sequence == 1
    assert non_system[1].content == "First assistant message"
    assert non_system[1].sequence == 2
    assert non_system[2].content == "Second user message"
    assert non_system[2].sequence == 3

def test_thread_with_attachments():
    """Test thread with message attachments"""
    thread = Thread(id="test-thread")
    
    # Create message with attachment
    attachment = Attachment(
        filename="test.txt",
        content=b"Test content"
    )
    message = Message(
        role="user",
        content="Message with attachment",
        attachments=[attachment]
    )
    
    thread.add_message(message)
    assert len(thread.messages) == 1
    assert len(thread.messages[0].attachments) == 1
    assert thread.messages[0].attachments[0].filename == "test.txt"
    assert thread.messages[0].attachments[0].content == b"Test content"

def test_thread_with_tool_calls():
    """Test thread with tool call messages"""
    thread = Thread(id="test-thread")
    
    # Add assistant message with tool call
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    
    assistant_msg = Message(
        role="assistant",
        content="Using tool",
        tool_calls=[tool_call]
    )
    thread.add_message(assistant_msg)
    
    # Add tool response
    tool_msg = Message(
        role="tool",
        content="Tool result",
        tool_call_id="call_123",
        name="test_tool"
    )
    thread.add_message(tool_msg)
    
    assert len(thread.messages) == 2
    assert thread.messages[0].tool_calls == [tool_call]
    assert thread.messages[1].tool_call_id == "call_123"
    assert thread.messages[1].name == "test_tool"

def test_thread_usage_stats():
    """Test thread usage statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with metrics
    msg1 = Message(
        role="assistant",
        content="First response",
        metrics={
            "model": "gpt-4",
            "usage": {
                "completion_tokens": 100,
                "prompt_tokens": 50,
                "total_tokens": 150
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Second response",
        metrics={
            "model": "gpt-4",
            "usage": {
                "completion_tokens": 150,
                "prompt_tokens": 75,
                "total_tokens": 225
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    # Get usage stats
    usage = thread.get_total_tokens()
    assert usage["overall"]["completion_tokens"] == 250  # 100 + 150
    assert usage["overall"]["prompt_tokens"] == 125  # 50 + 75
    assert usage["overall"]["total_tokens"] == 375  # 150 + 225
    
    # Check model-specific stats
    assert "gpt-4" in usage["by_model"]
    assert usage["by_model"]["gpt-4"]["completion_tokens"] == 250
    assert usage["by_model"]["gpt-4"]["prompt_tokens"] == 125
    assert usage["by_model"]["gpt-4"]["total_tokens"] == 375

def test_thread_timestamps():
    """Test thread timestamp handling"""
    thread = Thread(id="test-thread")
    initial_created = thread.created_at
    initial_updated = thread.updated_at
    
    # Wait a moment and add a message
    import time
    time.sleep(0.1)
    
    thread.add_message(Message(role="user", content="Hello"))
    
    # created_at should not change
    assert thread.created_at == initial_created
    # updated_at should be later
    assert thread.updated_at > initial_updated

def test_thread_validation():
    """Test thread validation"""
    # Test valid minimal thread
    thread = Thread(id="test-thread")
    assert thread.id == "test-thread"
    assert thread.title == "Untitled Thread"  # default title

def test_thread_message_ordering():
    """Test message ordering in thread"""
    thread = Thread(id="test-thread")
    
    # Add messages with explicit timestamps
    base_time = datetime.now(UTC)
    msg1 = Message(role="user", content="First", timestamp=base_time)
    msg2 = Message(role="assistant", content="Second", timestamp=base_time + timedelta(minutes=1))
    msg3 = Message(role="user", content="Third", timestamp=base_time + timedelta(minutes=2))
    
    # Add in random order
    thread.add_message(msg2)
    thread.add_message(msg3)
    thread.add_message(msg1)
    
    # Messages should maintain sequence order
    messages = [m for m in thread.messages if m.role != "system"]
    assert len(messages) == 3
    assert messages[0].sequence == 1
    assert messages[1].sequence == 2
    assert messages[2].sequence == 3 

def test_get_total_tokens():
    """Test getting total token usage across all messages"""
    thread = Thread(id="test-thread")
    
    # Add messages with metrics
    msg1 = Message(
        role="user",
        content="Hello",
        metrics={
            "model": "gpt-4.1",
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 5,
                "total_tokens": 15
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Hi there!",
        metrics={
            "model": "gpt-4.1",
            "usage": {
                "completion_tokens": 20,
                "prompt_tokens": 15,
                "total_tokens": 35
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    token_usage = thread.get_total_tokens()
    assert token_usage["overall"]["completion_tokens"] == 30
    assert token_usage["overall"]["prompt_tokens"] == 20
    assert token_usage["overall"]["total_tokens"] == 50
    
    assert "gpt-4.1" in token_usage["by_model"]
    assert token_usage["by_model"]["gpt-4.1"]["completion_tokens"] == 30
    assert token_usage["by_model"]["gpt-4.1"]["prompt_tokens"] == 20
    assert token_usage["by_model"]["gpt-4.1"]["total_tokens"] == 50

def test_get_model_usage():
    """Test getting model usage statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with different models
    msg1 = Message(
        role="user",
        content="Hello",
        metrics={
            "model": "gpt-4.1",
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 5,
                "total_tokens": 15
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Hi there!",
        metrics={
            "model": "gpt-3.5-turbo",
            "usage": {
                "completion_tokens": 20,
                "prompt_tokens": 15,
                "total_tokens": 35
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    # Test getting all model usage
    all_usage = thread.get_model_usage()
    assert "gpt-4.1" in all_usage
    assert "gpt-3.5-turbo" in all_usage
    assert all_usage["gpt-4.1"]["calls"] == 1
    assert all_usage["gpt-3.5-turbo"]["calls"] == 1
    
    # Test getting specific model usage
    gpt4_usage = thread.get_model_usage("gpt-4.1")
    assert gpt4_usage["calls"] == 1
    assert gpt4_usage["completion_tokens"] == 10
    assert gpt4_usage["prompt_tokens"] == 5
    assert gpt4_usage["total_tokens"] == 15

def test_get_message_timing_stats():
    """Test getting message timing statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with timing metrics
    msg1 = Message(
        role="user",
        content="Hello",
        metrics={
            "timing": {
                "started_at": "2024-02-07T00:00:00+00:00",
                "ended_at": "2024-02-07T00:00:01+00:00",
                "latency": 1000.0  # 1 second = 1000 milliseconds
            }
        }
    )
    msg2 = Message(
        role="assistant",
        content="Hi there!",
        metrics={
            "timing": {
                "started_at": "2024-02-07T00:00:02+00:00",
                "ended_at": "2024-02-07T00:00:04+00:00",
                "latency": 2000.0  # 2 seconds = 2000 milliseconds
            }
        }
    )
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    timing_stats = thread.get_message_timing_stats()
    assert timing_stats["total_latency"] == 3000.0  # 3 seconds = 3000 milliseconds
    assert timing_stats["average_latency"] == 1500.0  # 1.5 seconds = 1500 milliseconds
    assert timing_stats["message_count"] == 2

def test_get_message_counts():
    """Test getting message counts by role"""
    thread = Thread(id="test-thread")
    
    # Add messages with different roles
    thread.add_message(Message(role="system", content="System message"))
    thread.add_message(Message(role="user", content="User message 1"))
    thread.add_message(Message(role="user", content="User message 2"))
    thread.add_message(Message(role="assistant", content="Assistant message"))
    thread.add_message(Message(role="tool", content="Tool message", tool_call_id="123"))
    
    counts = thread.get_message_counts()
    assert counts["system"] == 1
    assert counts["user"] == 2
    assert counts["assistant"] == 1
    assert counts["tool"] == 1

def test_get_tool_usage():
    """Test getting tool usage statistics"""
    thread = Thread(id="test-thread")
    
    # Add messages with tool calls
    tool_call1 = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    tool_call2 = {
        "id": "call_456",
        "type": "function",
        "function": {
            "name": "another_tool",
            "arguments": '{"arg": "value"}'
        }
    }
    
    thread.add_message(Message(
        role="assistant",
        content="Using tools",
        tool_calls=[tool_call1, tool_call2]
    ))
    thread.add_message(Message(
        role="assistant",
        content="Using tool again",
        tool_calls=[tool_call1]
    ))
    
    tool_usage = thread.get_tool_usage()
    assert tool_usage["total_calls"] == 3
    assert tool_usage["tools"]["test_tool"] == 2
    assert tool_usage["tools"]["another_tool"] == 1

def test_thread_with_multimodal_messages():
    """Test thread with multimodal messages (text and images)"""
    thread = Thread(id="test-thread")
    
    # Create a message with both text and image content
    image_content = {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
        }
    }
    text_content = {
        "type": "text",
        "text": "Check out this image"
    }
    
    message = Message(
        role="user",
        content=[text_content, image_content]
    )
    
    thread.add_message(message)
    assert len(thread.messages) == 1
    assert isinstance(thread.messages[0].content, list)
    assert len(thread.messages[0].content) == 2
    assert thread.messages[0].content[0]["type"] == "text"
    assert thread.messages[0].content[1]["type"] == "image_url"

def test_thread_reactions():
    """Test thread reaction functionality"""
    thread = Thread(id="test-thread")
    
    # Add a message
    message = Message(role="user", content="Hello!")
    thread.add_message(message)
    
    # Add reactions
    assert thread.add_reaction(message.id, ":thumbsup:", "user1")
    assert thread.add_reaction(message.id, ":heart:", "user2")
    assert thread.add_reaction(message.id, ":thumbsup:", "user3")
    
    # Try to add duplicate reaction
    assert not thread.add_reaction(message.id, ":thumbsup:", "user1")
    
    # Check reactions
    reactions = thread.get_reactions(message.id)
    assert ":thumbsup:" in reactions
    assert ":heart:" in reactions
    assert "user1" in reactions[":thumbsup:"]
    assert "user3" in reactions[":thumbsup:"]
    assert "user2" in reactions[":heart:"]
    
    # Remove reactions
    assert thread.remove_reaction(message.id, ":thumbsup:", "user1")
    assert not thread.remove_reaction(message.id, ":nonexistent:", "user1")
    
    # Check updated reactions
    updated_reactions = thread.get_reactions(message.id)
    assert "user1" not in updated_reactions[":thumbsup:"]
    assert "user3" in updated_reactions[":thumbsup:"]

def test_get_system_message():
    """Test getting system message from thread"""
    thread = Thread(id="test-thread")
    
    # No system message initially
    assert thread.get_system_message() is None
    
    # Add various messages
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi"))
    
    # Still no system message
    assert thread.get_system_message() is None
    
    # Add system message
    system_msg = Message(role="system", content="You are helpful")
    thread.add_message(system_msg)
    
    # Should find the system message
    found_system = thread.get_system_message()
    assert found_system is not None
    assert found_system.role == "system"
    assert found_system.content == "You are helpful"

def test_get_messages_in_sequence():
    """Test getting messages sorted by sequence"""
    thread = Thread(id="test-thread")
    
    # Add messages out of order
    msg1 = Message(role="user", content="First")
    msg2 = Message(role="assistant", content="Second") 
    msg3 = Message(role="system", content="System")
    
    thread.add_message(msg2)  # sequence 1
    thread.add_message(msg1)  # sequence 2
    thread.add_message(msg3)  # sequence 0 (system)
    
    # Get messages in sequence order
    ordered = thread.get_messages_in_sequence()
    assert len(ordered) == 3
    assert ordered[0].role == "system"  # sequence 0
    assert ordered[1].content == "Second"  # sequence 1
    assert ordered[2].content == "First"  # sequence 2

def test_get_message_by_id():
    """Test finding a message by ID"""
    thread = Thread(id="test-thread")
    
    # Add some messages
    msg1 = Message(role="user", content="Hello")
    msg2 = Message(role="assistant", content="Hi")
    
    thread.add_message(msg1)
    thread.add_message(msg2)
    
    # Find existing messages
    found1 = thread.get_message_by_id(msg1.id)
    assert found1 is not None
    assert found1.content == "Hello"
    
    found2 = thread.get_message_by_id(msg2.id)
    assert found2 is not None
    assert found2.content == "Hi"
    
    # Try to find non-existent message
    not_found = thread.get_message_by_id("nonexistent-id")
    assert not_found is None

def test_message_turn_assignment():
    """Test basic turn assignment for messages"""
    thread = Thread(id="test-thread")
    
    # Add messages normally - each should get its own turn
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi there"))
    thread.add_message(Message(role="user", content="How are you?"))
    
    # Verify turn assignments
    assert thread.messages[0].turn == 1
    assert thread.messages[1].turn == 2
    assert thread.messages[2].turn == 3
    
    # Verify current turn
    assert thread.get_current_turn() == 3

def test_same_turn_parameter():
    """Test the same_turn parameter for grouping messages"""
    thread = Thread(id="test-thread")
    
    # Add initial user message
    thread.add_message(Message(role="user", content="What's 2+2?"))
    assert thread.messages[0].turn == 1
    
    # Add multiple assistant responses for the same user question
    thread.add_message(Message(role="assistant", content="GPT-4: The answer is 4"), same_turn=True)
    thread.add_message(Message(role="assistant", content="Claude: 2+2 equals 4"), same_turn=True)
    thread.add_message(Message(role="assistant", content="Gemini: It's 4"), same_turn=True)
    
    # All assistant responses should have the same turn as the user message
    assert thread.messages[1].turn == 1
    assert thread.messages[2].turn == 1
    assert thread.messages[3].turn == 1
    
    # Current turn should still be 1
    assert thread.get_current_turn() == 1
    
    # Add next user message - should start new turn
    thread.add_message(Message(role="user", content="Thanks!"))
    assert thread.messages[4].turn == 2
    assert thread.get_current_turn() == 2

def test_add_messages_batch():
    """Test adding multiple messages as a batch"""
    thread = Thread(id="test-thread")
    
    # Add initial message
    thread.add_message(Message(role="user", content="Process multiple tools"))
    assert thread.messages[0].turn == 1
    
    # Add batch of messages
    batch_messages = [
        Message(role="assistant", content="I'll use multiple tools"),
        Message(role="tool", content="Weather: 72°F", tool_call_id="call_weather"),
        Message(role="tool", content="News: No major events", tool_call_id="call_news"),
        Message(role="assistant", content="Based on the tools: It's 72°F and no major news")
    ]
    
    thread.add_messages_batch(batch_messages)
    
    # All batch messages should have the same turn (turn 2)
    assert thread.messages[1].turn == 2
    assert thread.messages[2].turn == 2
    assert thread.messages[3].turn == 2
    assert thread.messages[4].turn == 2
    
    # Verify sequences are still incremental
    assert thread.messages[1].sequence == 2
    assert thread.messages[2].sequence == 3
    assert thread.messages[3].sequence == 4
    assert thread.messages[4].sequence == 5
    
    assert thread.get_current_turn() == 2

def test_get_messages_by_turn():
    """Test retrieving messages by turn number"""
    thread = Thread(id="test-thread")
    
    # Add messages in different turns
    thread.add_message(Message(role="user", content="Question 1"))  # turn 1
    thread.add_message(Message(role="assistant", content="Answer 1a"), same_turn=True)  # turn 1
    thread.add_message(Message(role="assistant", content="Answer 1b"), same_turn=True)  # turn 1
    thread.add_message(Message(role="user", content="Question 2"))  # turn 2
    thread.add_message(Message(role="assistant", content="Answer 2"))  # turn 3
    
    # Test getting messages from turn 1
    turn1_messages = thread.get_messages_by_turn(1)
    assert len(turn1_messages) == 3
    assert turn1_messages[0].content == "Question 1"
    assert turn1_messages[1].content == "Answer 1a"
    assert turn1_messages[2].content == "Answer 1b"
    
    # Test getting messages from turn 2
    turn2_messages = thread.get_messages_by_turn(2)
    assert len(turn2_messages) == 1
    assert turn2_messages[0].content == "Question 2"
    
    # Test getting messages from turn 3
    turn3_messages = thread.get_messages_by_turn(3)
    assert len(turn3_messages) == 1
    assert turn3_messages[0].content == "Answer 2"
    
    # Test non-existent turn
    empty_turn = thread.get_messages_by_turn(99)
    assert len(empty_turn) == 0

def test_get_current_turn():
    """Test getting the current turn number"""
    thread = Thread(id="test-thread")
    
    # Empty thread should have turn 0
    assert thread.get_current_turn() == 0
    
    # Add system message (turn 0)
    thread.add_message(Message(role="system", content="System prompt"))
    assert thread.get_current_turn() == 0  # System messages don't count
    
    # Add first user message
    thread.add_message(Message(role="user", content="Hello"))
    assert thread.get_current_turn() == 1
    
    # Add assistant response in same turn
    thread.add_message(Message(role="assistant", content="Hi"), same_turn=True)
    assert thread.get_current_turn() == 1  # Still turn 1
    
    # Add next message in new turn
    thread.add_message(Message(role="user", content="How are you?"))
    assert thread.get_current_turn() == 2

def test_get_turns_summary():
    """Test getting summary of all turns"""
    thread = Thread(id="test-thread")
    
    # Add system message (shouldn't appear in summary)
    thread.add_message(Message(role="system", content="System"))
    
    # Add messages in different turns with some timestamps
    base_time = datetime.now(UTC)
    thread.add_message(Message(role="user", content="Q1", timestamp=base_time))
    thread.add_message(Message(role="assistant", content="A1a"), same_turn=True)  # Same turn
    thread.add_message(Message(role="assistant", content="A1b"), same_turn=True)  # Same turn
    
    # Add second turn
    thread.add_message(Message(role="user", content="Q2", timestamp=base_time + timedelta(minutes=1)))
    thread.add_message(Message(role="assistant", content="A2"))
    
    summary = thread.get_turns_summary()
    
    # Should have 3 turns (1, 2, 3) - system messages excluded
    assert len(summary) == 3
    
    # Check turn 1 summary
    assert 1 in summary
    turn1 = summary[1]
    assert turn1["turn"] == 1
    assert turn1["message_count"] == 3  # user + 2 assistants
    assert turn1["roles"]["user"] == 1
    assert turn1["roles"]["assistant"] == 2
    
    # Check turn 2 summary
    assert 2 in summary
    turn2 = summary[2]
    assert turn2["turn"] == 2
    assert turn2["message_count"] == 1
    assert turn2["roles"]["user"] == 1
    
    # Check turn 3 summary
    assert 3 in summary
    turn3 = summary[3]
    assert turn3["turn"] == 3
    assert turn3["message_count"] == 1
    assert turn3["roles"]["assistant"] == 1

def test_system_message_turn_assignment():
    """Test that system messages get turn 0"""
    thread = Thread(id="test-thread")
    
    # Add regular messages first
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi"))
    
    # Add system message
    thread.add_message(Message(role="system", content="You are helpful"))
    
    # Verify system message has turn 0 and sequence 0
    system_msg = thread.get_system_message()
    assert system_msg is not None
    assert system_msg.turn == 0
    assert system_msg.sequence == 0
    
    # Verify system message is first in the list
    assert thread.messages[0].role == "system"
    assert thread.messages[0].turn == 0

@pytest.mark.asyncio
async def test_turn_serialization():
    """Test that turn field is included in serialization"""
    thread = Thread(id="test-thread")
    
    # Add messages with turns
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi"), same_turn=True)
    
    # Test thread serialization includes turn data
    thread_data = thread.model_dump(mode="json")
    assert len(thread_data["messages"]) == 2
    assert thread_data["messages"][0]["turn"] == 1
    assert thread_data["messages"][1]["turn"] == 1
    
    # Test message serialization
    msg_data = thread.messages[0].model_dump(mode="json")
    assert msg_data["turn"] == 1
    
    # Test chat completion format excludes turn (LLM APIs don't need it)
    chat_messages = await thread.get_messages_for_chat_completion()
    assert len(chat_messages) == 2
    assert "turn" not in chat_messages[0]  # Should not include turn field
    assert "sequence" in chat_messages[0]  # Should still include sequence

def test_turn_with_empty_thread():
    """Test turn functionality with empty thread"""
    thread = Thread(id="test-thread")
    
    # Empty thread tests
    assert thread.get_current_turn() == 0
    assert thread.get_messages_by_turn(1) == []
    assert thread.get_turns_summary() == {}

def test_mixed_turn_scenarios():
    """Test complex mixed scenarios with turns"""
    thread = Thread(id="test-thread")
    
    # Add system message
    thread.add_message(Message(role="system", content="System"))
    
    # Turn 1: User question with multiple responses
    thread.add_message(Message(role="user", content="What's the weather?"))
    thread.add_message(Message(role="assistant", content="Checking..."), same_turn=True)
    thread.add_message(Message(role="assistant", content="It's sunny"), same_turn=True)
    
    # Turn 2: Batch of tool operations
    batch = [
        Message(role="assistant", content="Let me get more data"),
        Message(role="tool", content="API result", tool_call_id="call_1"),
        Message(role="assistant", content="Based on API: Updated weather info")
    ]
    thread.add_messages_batch(batch)
    
    # Turn 3: Final user response
    thread.add_message(Message(role="user", content="Thanks!"))
    
    # Verify turn structure
    assert thread.get_current_turn() == 3
    
    # Turn 1 should have 3 messages (user + 2 assistants)
    turn1 = thread.get_messages_by_turn(1)
    assert len(turn1) == 3
    assert turn1[0].role == "user"
    assert turn1[1].role == "assistant"
    assert turn1[2].role == "assistant"
    
    # Turn 2 should have 3 messages (assistant + tool + assistant)
    turn2 = thread.get_messages_by_turn(2)
    assert len(turn2) == 3
    assert turn2[0].role == "assistant"
    assert turn2[1].role == "tool"
    assert turn2[2].role == "assistant"
    
    # Turn 3 should have 1 message (user)
    turn3 = thread.get_messages_by_turn(3)
    assert len(turn3) == 1
    assert turn3[0].role == "user"
    
    # Verify sequences are still correct
    all_messages = [m for m in thread.messages if m.role != "system"]
    sequences = [m.sequence for m in all_messages]
    assert sequences == [1, 2, 3, 4, 5, 6, 7]  # Should be sequential 