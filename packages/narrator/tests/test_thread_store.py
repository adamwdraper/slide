import pytest
import pytest_asyncio
import os
from pathlib import Path
import tempfile
from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from narrator import Thread, Message, Attachment, ThreadStore
from narrator.database.storage_backend import MemoryBackend, SQLBackend
from narrator.database.models import Base

pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def env_vars():
    """Save and restore environment variables."""
    yield

@pytest_asyncio.fixture
async def thread_store():
    """Create a ThreadStore for testing using SQLBackend with an in-memory DB."""
    # Use factory pattern for immediate initialization
    store = await ThreadStore.create(":memory:")
    async with store._backend.engine.begin() as conn:
        # Reset tables for testing
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield store
    await store._backend.engine.dispose()

@pytest.fixture
def sample_thread():
    """Create a sample thread for testing."""
    thread = Thread(id="test-thread-1", title="Test Thread")
    thread.add_message(Message(role="user", content="Hello"))
    thread.updated_at = datetime.now(UTC)
    return thread

@pytest.mark.asyncio
async def test_thread_store_init():
    """Test ThreadStore initialization using factory pattern"""
    # Use the factory pattern for creation and initialization
    store = await ThreadStore.create(":memory:")
    assert store.engine is not None
    assert store._initialized is True
    
    # Verify we can save and retrieve a thread
    thread = Thread(title="Test Init")
    await store.save(thread)
    
    retrieved = await store.get(thread.id)
    assert retrieved is not None
    assert retrieved.title == "Test Init"
    
    # Clean up
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_factory_pattern():
    """Test the ThreadStore.create factory method"""
    # Create with in-memory backend
    memory_store = await ThreadStore.create()
    assert isinstance(memory_store._backend, MemoryBackend)
    assert memory_store._initialized is True
    
    # Create with SQL backend
    sql_store = await ThreadStore.create(":memory:")
    assert isinstance(sql_store._backend, SQLBackend)
    assert sql_store._initialized is True
    assert sql_store.engine is not None
    
    # Create and use
    store = await ThreadStore.create(":memory:")
    thread = Thread(title="Factory Pattern Test")
    await store.save(thread)
    
    retrieved = await store.get(thread.id)
    assert retrieved is not None
    assert retrieved.title == "Factory Pattern Test"
    
    # Clean up
    await sql_store._backend.engine.dispose()
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_auto_initialization():
    """Test that ThreadStore initializes automatically when operations are performed."""
    # Create store without explicitly initializing
    store = ThreadStore(":memory:")
    
    # Verify not initialized yet
    assert not store._initialized
    
    # Create a thread
    thread = Thread(title="Test Auto Init")
    
    # Save thread - should trigger automatic initialization
    await store.save(thread)
    
    # Verify now initialized
    assert store._initialized
    
    # Verify thread was saved
    retrieved = await store.get(thread.id)
    assert retrieved is not None
    assert retrieved.title == "Test Auto Init"
    
    # Clean up
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_default_url():
    """Test ThreadStore initialization with default behavior."""
    # Test both initialization methods
    
    # Traditional method
    traditional_store = ThreadStore()
    assert isinstance(traditional_store._backend, MemoryBackend)
    assert traditional_store.database_url is None
    
    # Factory method
    factory_store = await ThreadStore.create()
    assert isinstance(factory_store._backend, MemoryBackend)
    assert factory_store.database_url is None
    assert factory_store._initialized is True

@pytest.mark.asyncio
async def test_save_thread(thread_store, sample_thread):
    """Test saving a thread"""
    # Save the thread
    await thread_store.save(sample_thread)
    
    # Verify it was saved correctly using thread_store.get
    fetched = await thread_store.get(sample_thread.id)
    assert fetched is not None
    assert fetched.title == sample_thread.title
    assert len(fetched.messages) == 1
    assert fetched.messages[0].role == "user"

@pytest.mark.asyncio
async def test_get_thread(thread_store, sample_thread):
    """Test retrieving a thread"""
    # Save the thread first
    await thread_store.save(sample_thread)
    
    # Retrieve the thread
    retrieved_thread = await thread_store.get(sample_thread.id)
    assert retrieved_thread is not None
    assert retrieved_thread.id == sample_thread.id
    assert retrieved_thread.title == sample_thread.title
    assert len(retrieved_thread.messages) == 1
    assert retrieved_thread.messages[0].role == "user"
    assert retrieved_thread.messages[0].content == "Hello"

@pytest.mark.asyncio
async def test_get_nonexistent_thread(thread_store):
    """Test retrieving a non-existent thread"""
    thread = await thread_store.get("nonexistent-id")
    assert thread is None

@pytest.mark.asyncio
async def test_list_recent(thread_store):
    """Test listing recent threads"""
    # Create and save multiple threads
    threads = []
    for i in range(3):
        thread = Thread(
            id=f"test-thread-{i}",
            title=f"Test Thread {i}"
        )
        thread.add_message(Message(role="user", content=f"Message {i}"))
        await thread_store.save(thread)
        threads.append(thread)
    
    # List recent threads
    recent_threads = await thread_store.list_recent(limit=2)
    assert len(recent_threads) == 2
    # Should be in reverse order (most recent first)
    assert recent_threads[0].id == "test-thread-2"
    assert recent_threads[1].id == "test-thread-1"

@pytest.mark.asyncio
async def test_delete_thread(thread_store, sample_thread):
    """Test deleting a thread"""
    # Save the thread first
    await thread_store.save(sample_thread)
    
    # Delete the thread
    success = await thread_store.delete(sample_thread.id)
    assert success is True
    
    # Verify it's gone
    fetched = await thread_store.get(sample_thread.id)
    assert fetched is None

@pytest.mark.asyncio
async def test_delete_nonexistent_thread(thread_store):
    """Test deleting a non-existent thread"""
    success = await thread_store.delete("nonexistent-id")
    assert success is False

@pytest.mark.asyncio
async def test_find_by_attributes(thread_store):
    """Test finding threads by attributes"""
    # Create threads with different attributes
    thread1 = Thread(id="thread-1", title="Thread 1")
    thread1.attributes = {"category": "work", "priority": "high"}
    await thread_store.save(thread1)
    
    thread2 = Thread(id="thread-2", title="Thread 2")
    thread2.attributes = {"category": "personal", "priority": "low"}
    await thread_store.save(thread2)
    
    # Search by attributes using the ThreadStore API
    results = await thread_store.find_by_attributes({"category": "work"})
    
    assert len(results) == 1
    assert results[0].id == "thread-1"

@pytest.mark.asyncio
async def test_find_by_platform(thread_store):
    """Test finding threads by platform"""
    # Create threads with different platforms
    thread1 = Thread(id="thread-1", title="Thread 1")
    thread1.platforms = {"slack": {"channel": "general"}}
    await thread_store.save(thread1)
    
    thread2 = Thread(id="thread-2", title="Thread 2")
    thread2.platforms = {"notion": {"page_id": "123"}}
    await thread_store.save(thread2)
    
    # Search by platform using the ThreadStore API
    results = await thread_store.find_by_platform("slack", {})
    
    assert len(results) == 1
    assert results[0].id == "thread-1"

@pytest.mark.asyncio
async def test_thread_update(thread_store, sample_thread):
    """Test updating an existing thread"""
    # Save the initial thread
    await thread_store.save(sample_thread)
    
    # Modify the thread
    sample_thread.title = "Updated Title"
    sample_thread.add_message(Message(role="assistant", content="Response"))
    
    # Save the updates
    await thread_store.save(sample_thread)
    
    # Verify the updates
    updated_thread = await thread_store.get(sample_thread.id)
    assert updated_thread.title == "Updated Title"
    assert len(updated_thread.messages) == 2
    assert updated_thread.messages[1].role == "assistant"
    assert updated_thread.messages[1].content == "Response"

@pytest.mark.asyncio
async def test_thread_store_temp_cleanup():
    """Test that temporary database files are cleaned up."""
    # Create store with temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "threads.db")
        store = ThreadStore(f"sqlite+aiosqlite:///{db_path}")
        await store.initialize()
        
        # Save a thread
        thread = Thread(id="test-thread", title="Test Thread")
        await store.save(thread)
        
        # Verify thread was saved using the store API
        retrieved_thread = await store.get(thread.id)
        assert retrieved_thread is not None
        assert retrieved_thread.title == thread.title
        
        # Close store
        await store._backend.engine.dispose()
        
        # Verify database file exists in temp directory
        assert os.path.exists(db_path)
    
    # After exiting temp directory context, verify it's gone
    assert not os.path.exists(db_path)

@pytest.mark.asyncio
async def test_thread_store_connection_management():
    """Test proper connection management."""
    store = ThreadStore(":memory:")
    await store.initialize()
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create and save multiple threads
    threads = []
    for i in range(5):
        thread = Thread()
        await store.save(thread)
        threads.append(thread)
    
    # Verify all threads can be retrieved
    for thread in threads:
        retrieved = await store.get(thread.id)
        assert retrieved is not None
        assert retrieved.id == thread.id
    
    # Close all connections
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_concurrent_access():
    """Test concurrent access to thread store."""
    store = ThreadStore(":memory:")
    await store.initialize()
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    thread = Thread()
    await store.save(thread)
    
    # Simulate concurrent access
    async def update_thread():
        # Each operation should get its own session
        retrieved = await store.get(thread.id)
        retrieved.title = "Updated"
        await store.save(retrieved)
    
    # Run multiple updates
    for _ in range(5):
        await update_thread()
    
    # Verify final state
    final = await store.get(thread.id)
    assert final.title == "Updated"
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_json_serialization():
    """Test JSON serialization of complex thread data."""
    store = ThreadStore(":memory:")
    await store.initialize()
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    thread = Thread()
    
    # Add complex data
    thread.attributes = {
        "nested": {"key": "value"},
        "list": [1, 2, 3],
        "null": None,
        "bool": True
    }
    
    # Save and retrieve
    await store.save(thread)
    retrieved = await store.get(thread.id)
    
    # Verify complex data is preserved
    assert retrieved.attributes == thread.attributes
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_error_handling():
    """Test error handling in thread store operations."""
    store = ThreadStore(":memory:")
    await store.initialize()
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Test invalid thread ID
    assert await store.get("nonexistent") is None
    
    # Test invalid JSON data
    thread = Thread()
    thread.attributes = {"invalid": object()}  # Object that can't be JSON serialized
    
    with pytest.raises(Exception):
        await store.save(thread)
        
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_thread_store_pagination():
    """Test thread listing with pagination."""
    store = ThreadStore(":memory:")
    await store.initialize()
    
    # Create tables
    async with store._backend.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create 15 threads
    threads = []
    for i in range(15):
        thread = Thread()
        thread.title = f"Thread {i}"
        await store.save(thread)
        threads.append(thread)
    
    # Test different page sizes
    page1 = await store.list(limit=5)
    assert len(page1) == 5
    page2 = await store.list(limit=10, offset=5)
    assert len(page2) == 10
    all_threads = await store.list(limit=20)
    assert len(all_threads) == 15
    
    # Test ordering
    recent = await store.list(limit=5)
    assert recent[0].title == "Thread 14"  # Most recent first
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_message_sequence_preservation(thread_store):
    """Test that message sequences are preserved correctly in database while system messages are filtered"""
    # Create a thread with system and non-system messages
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="First user message"))
    thread.add_message(Message(role="assistant", content="First assistant message"))
    thread.add_message(Message(role="system", content="System message"))
    thread.add_message(Message(role="user", content="Second user message"))
    
    # Keep track of original message count
    original_message_count = len(thread.messages)
    
    # Save thread
    saved_thread = await thread_store.save(thread)
    
    # Original thread should still have system message intact
    assert len(saved_thread.messages) == original_message_count
    assert any(m.role == "system" for m in saved_thread.messages)
    
    # Retrieve thread from database
    loaded_thread = await thread_store.get(thread.id)
    
    # Verify system messages are not present in the loaded thread
    assert len(loaded_thread.messages) == 3, "Expected only non-system messages to be persisted"
    assert all(m.role != "system" for m in loaded_thread.messages), "System messages should not be persisted"
    
    # Verify the non-system messages are in the correct order with proper sequences
    assert loaded_thread.messages[0].content == "First user message"
    assert loaded_thread.messages[0].sequence == 1
    assert loaded_thread.messages[1].content == "First assistant message"
    assert loaded_thread.messages[1].sequence == 2
    assert loaded_thread.messages[2].content == "Second user message"
    assert loaded_thread.messages[2].sequence == 3

@pytest.mark.asyncio
async def test_save_thread_with_attachments(thread_store):
    """Test saving a thread with attachments ensures they are stored before returning"""
    # Create a thread with an attachment
    thread = Thread()
    message = Message(role="user", content="Test with attachment")
    attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain"
    )
    message.attachments.append(attachment)
    thread.add_message(message)
    
    # Save the thread - this should automatically process and store attachments
    saved_thread = await thread_store.save(thread)
    
    # Verify attachment was processed
    assert len(saved_thread.messages[0].attachments) == 1
    stored_attachment = saved_thread.messages[0].attachments[0]
    assert stored_attachment.file_id is not None
    assert stored_attachment.storage_path is not None
    
    # Verify we can retrieve it and attachment data persists
    retrieved_thread = await thread_store.get(thread.id)
    assert len(retrieved_thread.messages[0].attachments) == 1
    retrieved_attachment = retrieved_thread.messages[0].attachments[0]
    assert retrieved_attachment.file_id is not None
    assert retrieved_attachment.storage_path is not None

@pytest.mark.asyncio
async def test_save_thread_with_multiple_attachments(thread_store):
    """Test saving a thread with multiple messages and attachments"""
    thread = Thread()
    
    # Add first message with attachment
    msg1 = Message(role="user", content="First message")
    att1 = Attachment(filename="test1.txt", content=b"Content 1", mime_type="text/plain")
    msg1.attachments.append(att1)
    thread.add_message(msg1)
    
    # Add second message with two attachments
    msg2 = Message(role="assistant", content="Second message")
    att2 = Attachment(filename="test2.txt", content=b"Content 2", mime_type="text/plain")
    att3 = Attachment(filename="test3.txt", content=b"Content 3", mime_type="text/plain")
    msg2.attachments.extend([att2, att3])
    thread.add_message(msg2)
    
    # Save the thread
    saved_thread = await thread_store.save(thread)
    
    # Verify all attachments were processed
    assert len(saved_thread.messages[0].attachments) == 1
    assert len(saved_thread.messages[1].attachments) == 2
    
    # Verify all attachments have file_id and storage_path
    for msg in saved_thread.messages:
        for att in msg.attachments:
            assert att.file_id is not None
            assert att.storage_path is not None
    
    # Verify we can retrieve everything
    retrieved_thread = await thread_store.get(thread.id)
    assert len(retrieved_thread.messages[0].attachments) == 1
    assert len(retrieved_thread.messages[1].attachments) == 2

@pytest.mark.asyncio
async def test_default_backend():
    """Test that ThreadStore defaults to MemoryBackend when no URL is provided"""
    store = ThreadStore()
    assert isinstance(store._backend, MemoryBackend)

@pytest.mark.asyncio
async def test_explicit_sql_backend():
    """Test that ThreadStore uses SQLBackend when URL is provided"""
    store = ThreadStore(":memory:")
    assert isinstance(store._backend, SQLBackend)

@pytest.mark.asyncio
async def test_system_messages_not_persisted(thread_store):
    """Test that system messages are not persisted to database"""
    # Create thread with system message
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="system", content="System message"))
    thread.add_message(Message(role="user", content="User message"))
    
    # Save thread
    await thread_store.save(thread)
    
    # Retrieve thread
    retrieved_thread = await thread_store.get(thread.id)
    
    # System message should not be in persisted thread
    assert len(retrieved_thread.messages) == 1
    assert retrieved_thread.messages[0].role == "user"
    assert retrieved_thread.messages[0].content == "User message"

@pytest.mark.asyncio
async def test_system_prompt_preserved_in_memory():
    """Test that system messages are preserved in memory thread but not persisted"""
    # Create thread with system message
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="system", content="System message"))
    thread.add_message(Message(role="user", content="User message"))
    
    # Thread in memory should have system message
    assert len(thread.messages) == 2
    assert thread.messages[0].role == "system"
    assert thread.messages[1].role == "user"
    
    # Save thread
    thread_store = await ThreadStore.create(":memory:")
    await thread_store.save(thread)
    
    # Thread in memory should still have system message after save
    assert len(thread.messages) == 2
    assert thread.messages[0].role == "system"
    assert thread.messages[1].role == "user"
    
    # Retrieved thread should not have system message
    retrieved_thread = await thread_store.get(thread.id)
    assert len(retrieved_thread.messages) == 1
    assert retrieved_thread.messages[0].role == "user"
    
    await thread_store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_reaction_persistence():
    """Test that message reactions are persisted correctly"""
    thread_store = await ThreadStore.create(":memory:")
    
    # Create thread with message
    thread = Thread(id="test-thread")
    message = Message(role="user", content="Test message")
    thread.add_message(message)
    
    # Add reactions
    thread.add_reaction(message.id, ":thumbsup:", "user1")
    thread.add_reaction(message.id, ":heart:", "user2")
    
    # Save thread
    await thread_store.save(thread)
    
    # Retrieve thread
    retrieved_thread = await thread_store.get(thread.id)
    
    # Check reactions are persisted
    reactions = retrieved_thread.get_reactions(message.id)
    assert ":thumbsup:" in reactions
    assert ":heart:" in reactions
    assert "user1" in reactions[":thumbsup:"]
    assert "user2" in reactions[":heart:"]
    
    await thread_store._backend.engine.dispose()

@pytest.mark.asyncio 
async def test_turn_data_persistence():
    """Test that turn data is properly persisted to and retrieved from database"""
    store = await ThreadStore.create(":memory:")
    thread = Thread(title="Turn Persistence Test")
    
    # Add messages with various turn configurations
    thread.add_message(Message(role="user", content="Question 1"))  # turn 1
    thread.add_message(Message(role="assistant", content="Answer 1a"), same_turn=True)  # turn 1
    thread.add_message(Message(role="assistant", content="Answer 1b"), same_turn=True)  # turn 1
    
    # Add batch messages
    batch = [
        Message(role="assistant", content="Processing..."),
        Message(role="tool", content="Tool result", tool_call_id="call_1"),
        Message(role="assistant", content="Complete")
    ]
    thread.add_messages_batch(batch)  # turn 2
    
    # Add system message
    thread.add_message(Message(role="system", content="System prompt"))  # turn 0
    
    # Save to database
    await store.save(thread)
    
    # Retrieve from database
    retrieved = await store.get(thread.id)
    assert retrieved is not None
    
    # Verify turn data is preserved (system messages not persisted)
    assert len(retrieved.messages) == 6  # 6 non-system messages
    
    # Find messages by content and verify turns
    user_msg = next(m for m in retrieved.messages if m.content == "Question 1")
    assert user_msg.turn == 1
    
    answer_1a = next(m for m in retrieved.messages if m.content == "Answer 1a")
    assert answer_1a.turn == 1
    
    answer_1b = next(m for m in retrieved.messages if m.content == "Answer 1b")
    assert answer_1b.turn == 1
    
    processing_msg = next(m for m in retrieved.messages if m.content == "Processing...")
    assert processing_msg.turn == 2
    
    tool_msg = next(m for m in retrieved.messages if m.content == "Tool result")
    assert tool_msg.turn == 2
    
    complete_msg = next(m for m in retrieved.messages if m.content == "Complete")
    assert complete_msg.turn == 2
    
    # Verify turn helper methods work after retrieval
    assert retrieved.get_current_turn() == 2
    assert len(retrieved.get_messages_by_turn(1)) == 3
    assert len(retrieved.get_messages_by_turn(2)) == 3
    
    # Verify turns summary
    summary = retrieved.get_turns_summary()
    assert 1 in summary
    assert 2 in summary
    assert summary[1]["message_count"] == 3
    assert summary[2]["message_count"] == 3
    
    await store._backend.engine.dispose()

@pytest.mark.asyncio
async def test_turn_data_with_complex_scenarios():
    """Test turn functionality in complex real-world scenarios"""
    store = await ThreadStore.create(":memory:")
    thread = Thread(title="Complex Turn Test")
    
    # System message (not persisted but should handle turn 0)
    thread.add_message(Message(role="system", content="You are helpful"))
    
    # Multi-LLM scenario: same user question, multiple responses
    thread.add_message(Message(role="user", content="What's 2+2?"))
    thread.add_message(Message(role="assistant", content="GPT-4: It's 4", 
                              source={"id": "gpt-4", "type": "agent"}), same_turn=True)
    thread.add_message(Message(role="assistant", content="Claude: 2+2=4", 
                              source={"id": "claude", "type": "agent"}), same_turn=True)
    
    # Tool execution scenario: batch processing
    tool_batch = [
        Message(role="assistant", content="Let me check multiple sources"),
        Message(role="tool", content="Weather: Sunny", tool_call_id="weather_call"),
        Message(role="tool", content="News: All clear", tool_call_id="news_call"),
        Message(role="assistant", content="Weather is sunny, no major news")
    ]
    thread.add_messages_batch(tool_batch)
    
    # Final user response
    thread.add_message(Message(role="user", content="Thanks for the info!"))
    
    # Save and retrieve
    await store.save(thread)
    retrieved = await store.get(thread.id)
    
    # Verify complex turn structure
    assert retrieved.get_current_turn() == 3
    
    # Turn 1: user + 2 assistant responses
    turn1_msgs = retrieved.get_messages_by_turn(1)
    assert len(turn1_msgs) == 3
    assert turn1_msgs[0].role == "user"
    assert turn1_msgs[1].role == "assistant"
    assert turn1_msgs[2].role == "assistant"
    
    # Turn 2: tool execution batch
    turn2_msgs = retrieved.get_messages_by_turn(2)
    assert len(turn2_msgs) == 4
    assert turn2_msgs[0].role == "assistant"
    assert turn2_msgs[1].role == "tool"
    assert turn2_msgs[2].role == "tool"
    assert turn2_msgs[3].role == "assistant"
    
    # Turn 3: final user message
    turn3_msgs = retrieved.get_messages_by_turn(3)
    assert len(turn3_msgs) == 1
    assert turn3_msgs[0].role == "user"
    assert turn3_msgs[0].content == "Thanks for the info!"
    
    # Verify source data preserved with turns
    gpt_msg = next(m for m in turn1_msgs if "GPT-4" in m.content)
    assert gpt_msg.source["id"] == "gpt-4"
    assert gpt_msg.turn == 1
    
    await store._backend.engine.dispose() 