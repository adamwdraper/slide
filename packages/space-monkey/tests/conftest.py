"""
Shared fixtures for Space Monkey tests
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Optional

from space_monkey.core.config import Config
from space_monkey.core.bot import SpaceMonkey
from space_monkey.agents.base import SlackAgent, ClassifierAgent
from narrator import Thread, Message, ThreadStore, FileStore

# Test configuration
TEST_CONFIG = {
    "slack_bot_token": "xoxb-test-token",
    "slack_app_token": "xapp-test-token",
    "database_url": None,  # Use in-memory for tests
    "file_storage_path": None,  # Use temp storage for tests
    "environment": "test",
    "host": "127.0.0.1",
    "port": 8001,
}

@pytest.fixture
def test_config():
    """Test configuration"""
    return Config(**TEST_CONFIG)

@pytest.fixture
async def mock_thread_store():
    """Mock thread store for testing"""
    store = Mock(spec=ThreadStore)
    store.save = AsyncMock()
    store.get = AsyncMock()
    store.find_by_platform = AsyncMock(return_value=[])
    store.find_messages_by_attribute = AsyncMock(return_value=[])
    store.get_thread_by_message_id = AsyncMock()
    return store

@pytest.fixture
async def mock_file_store():
    """Mock file store for testing"""
    store = Mock(spec=FileStore)
    store.save = AsyncMock()
    store.get = AsyncMock()
    store.delete = AsyncMock()
    return store

@pytest.fixture
def mock_slack_app():
    """Mock Slack app for testing"""
    app = Mock()
    app.client = Mock()
    app.client.auth_test = AsyncMock(return_value={"user_id": "U123TEST"})
    app.client.reactions_add = AsyncMock()
    app.client.reactions_remove = AsyncMock()
    app.event = Mock()
    app.use = Mock()
    return app

@pytest.fixture
async def space_monkey_bot(test_config, mock_thread_store, mock_file_store):
    """Space Monkey bot instance for testing"""
    with patch('space_monkey.core.bot.AsyncApp') as mock_app_class, \
         patch('space_monkey.core.bot.ThreadStore.create') as mock_thread_create, \
         patch('space_monkey.core.bot.FileStore.create') as mock_file_create:
        
        # Mock the store creation
        mock_thread_create.return_value = mock_thread_store
        mock_file_create.return_value = mock_file_store
        
        # Mock the Slack app
        mock_app = Mock()
        mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123TEST"})
        mock_app_class.return_value = mock_app
        
        bot = SpaceMonkey(test_config)
        bot.slack_app = mock_app
        bot.thread_store = mock_thread_store
        bot.file_store = mock_file_store
        bot.bot_user_id = "U123TEST"
        
        return bot

@pytest.fixture
def sample_slack_event():
    """Sample Slack message event for testing"""
    return {
        "type": "message",
        "channel": "C123TEST",
        "user": "U456USER",
        "text": "Hello, bot!",
        "ts": "1234567890.123456",
        "channel_type": "channel"
    }

@pytest.fixture
def sample_thread_event():
    """Sample Slack thread message event for testing"""
    return {
        "type": "message",
        "channel": "C123TEST",
        "user": "U456USER",
        "text": "Reply in thread",
        "ts": "1234567890.123457",
        "thread_ts": "1234567890.123456",
        "channel_type": "channel"
    }

@pytest.fixture
def sample_dm_event():
    """Sample direct message event for testing"""
    return {
        "type": "message",
        "channel": "D123DM",
        "user": "U456USER",
        "text": "Direct message",
        "ts": "1234567890.123458",
        "channel_type": "im"
    }

@pytest.fixture
def sample_reaction_event():
    """Sample reaction event for testing"""
    return {
        "type": "reaction_added",
        "user": "U456USER",
        "reaction": "thumbsup",
        "item": {
            "type": "message",
            "channel": "C123TEST",
            "ts": "1234567890.123456"
        }
    }

@pytest.fixture
async def sample_thread():
    """Sample thread with messages for testing"""
    thread = Thread(platforms={"slack": {"channel": "C123TEST", "thread_ts": "1234567890.123456"}})
    
    # Add some sample messages
    user_msg = Message(
        role="user",
        content="Hello, bot!",
        source={"id": "U456USER", "type": "user"},
        platforms={"slack": {"channel": "C123TEST", "ts": "1234567890.123456"}}
    )
    
    assistant_msg = Message(
        role="assistant",
        content="Hello! How can I help you?",
        source={"id": "U123TEST", "type": "bot"}
    )
    
    thread.add_message(user_msg)
    thread.add_message(assistant_msg)
    
    return thread

class TestAgent(SlackAgent):
    """Test agent for testing"""
    
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        return "test" in event.get("text", "").lower()
    
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        return "Test response"

class TestClassifier(ClassifierAgent):
    """Test classifier for testing"""
    
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        return True
    
    async def classify_message(self, thread: Thread, event: Dict[str, Any]) -> Dict[str, Any]:
        text = event.get("text", "").lower()
        
        if "ignore" in text:
            return {"response_type": "ignore", "reasoning": "Test ignore"}
        elif "emoji" in text:
            return {"response_type": "emoji_reaction", "suggested_emoji": "thumbsup", "reasoning": "Test emoji"}
        else:
            return {"response_type": "full_response", "reasoning": "Test full response"}

@pytest.fixture
def test_agent_class():
    """Test agent class for testing"""
    return TestAgent

@pytest.fixture
def test_classifier_class():
    """Test classifier class for testing"""
    return TestClassifier

@pytest.fixture
async def mock_say():
    """Mock Slack say function for testing"""
    mock_say = AsyncMock()
    mock_say.return_value = {"ts": "1234567890.999999"}
    return mock_say

# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 