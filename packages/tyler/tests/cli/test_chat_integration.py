"""
Integration tests for Tyler Chat CLI functionality.

Tests verify that CLI works correctly with and without Weave.
"""
import os
from unittest.mock import patch
import pytest
from narrator import Message


@pytest.mark.asyncio
@patch.dict(os.environ, {}, clear=True)
async def test_cli_works_without_weave():
    """Test that CLI functions normally without Weave initialization"""
    from tyler.cli.chat import ChatManager
    
    # Create manager without WANDB_PROJECT
    manager = ChatManager()
    
    # Initialize agent
    manager.initialize_agent({
        'model_name': 'gpt-4o',
        'purpose': 'Test assistant'
    })
    
    assert manager.agent is not None
    assert manager.agent.name == "Tyler"
    
    # Create a thread
    thread = await manager.create_thread(title="Test Thread")
    assert thread is not None
    assert thread.title == "Test Thread"
    assert len(thread.messages) > 0  # Should have system message
    
    # Add a message
    thread.add_message(Message(role="user", content="Hello"))
    assert len(thread.messages) >= 2


@pytest.mark.asyncio
@patch('tyler.cli.chat.weave')
@patch.dict(os.environ, {'WANDB_PROJECT': 'test-integration'})
async def test_cli_works_with_weave(mock_weave):
    """Test that CLI functions normally with Weave enabled"""
    from tyler.cli.chat import ChatManager
    
    # Create manager with WANDB_PROJECT (weave.init will be mocked)
    manager = ChatManager()
    
    # Verify weave.init was called
    mock_weave.init.assert_called_once_with('test-integration')
    
    # Initialize agent
    manager.initialize_agent({
        'model_name': 'gpt-4o',
        'purpose': 'Test assistant'
    })
    
    assert manager.agent is not None
    
    # Create a thread
    thread = await manager.create_thread(title="Test With Weave")
    assert thread is not None
    assert thread.title == "Test With Weave"


@pytest.mark.asyncio  
@patch.dict(os.environ, {}, clear=True)
async def test_multiple_threads_without_weave():
    """Test creating multiple threads works without Weave"""
    from tyler.cli.chat import ChatManager
    
    manager = ChatManager()
    manager.initialize_agent({'model_name': 'gpt-4o'})
    
    # Create multiple threads - verifies no issues with @weave.op() decorators
    thread1 = await manager.create_thread(title="Thread 1")
    thread2 = await manager.create_thread(title="Thread 2")
    thread3 = await manager.create_thread(title="Thread 3")
    
    # Verify all threads were created successfully
    assert thread1.id != thread2.id != thread3.id
    assert thread1.title == "Thread 1"
    assert thread2.title == "Thread 2"
    assert thread3.title == "Thread 3"
    
    # List threads
    threads = await manager.list_threads()
    assert len(threads) >= 3
    
    # Current thread should be the most recent (thread3)
    assert manager.current_thread.id == thread3.id

