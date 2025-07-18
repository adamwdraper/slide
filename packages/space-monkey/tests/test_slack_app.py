"""
Comprehensive unit tests for SlackApp class.

These tests cover all major functionality including initialization,
message processing, classification, thread management, and event handling.

Test Coverage:
- SlackApp initialization with and without custom response topics
- Startup process including Slack auth, classifier setup, and health monitoring
- Message processing flow including duplicate detection and thread management
- Message classification (ignore, emoji reaction, full response)
- File upload handling to Slack
- Reaction event handling (add/remove)
- Error handling for agent errors and database issues  
- Utility methods (dev footer generation)
- Health monitoring configuration

All tests use proper async patterns and mock external dependencies.
"""
import os
import pytest
import pytest_asyncio
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock, call
from datetime import datetime, timezone

# Mock environment variables before imports
@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables for testing"""
    with patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token',
        'SLACK_APP_TOKEN': 'xapp-test-token',
        'OPENAI_API_KEY': 'sk-test-key',
        'HEALTH_CHECK_URL': 'http://test-health-check',
        'WANDB_PROJECT': 'test-project',
        'WANDB_API_KEY': 'test-wandb-key',
        'ENV': 'test'
    }):
        yield

# Import after environment setup
from space_monkey import SlackApp, Agent, ThreadStore, FileStore
from narrator import Thread, Message, Attachment

class TestSlackAppInitialization:
    """Test SlackApp initialization and setup."""
    
    @pytest_asyncio.fixture
    async def mock_stores(self):
        """Create mock stores for testing."""
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        return thread_store, file_store
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent for testing."""
        agent = MagicMock(spec=Agent)
        agent.name = "TestAgent"
        agent.version = "1.0.0"
        agent.go = AsyncMock()
        agent.thread_store = MagicMock()  # Add thread_store attribute
        return agent
    
    @pytest.mark.asyncio
    async def test_slack_app_initialization(self, mock_agent, mock_stores):
        """Test basic SlackApp initialization."""
        thread_store, file_store = mock_stores
        
        app = SlackApp(
            agent=mock_agent,
            thread_store=thread_store,
            file_store=file_store,
            response_topics="test topics"
        )
        
        assert app.agent == mock_agent
        assert app.thread_store == thread_store
        assert app.file_store == file_store
        assert app.response_topics == "test topics"
        assert app.slack_app is None  # Not initialized until startup
        assert app.bot_user_id is None
    
    @pytest.mark.asyncio
    async def test_slack_app_with_default_topics(self, mock_agent, mock_stores):
        """Test SlackApp initialization without response_topics."""
        thread_store, file_store = mock_stores
        
        app = SlackApp(
            agent=mock_agent,
            thread_store=thread_store,
            file_store=file_store
        )
        
        assert app.response_topics is None

class TestSlackAppStartup:
    """Test SlackApp startup and initialization process."""
    
    @pytest_asyncio.fixture
    async def mock_stores(self):
        """Create mock stores for testing."""
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        return thread_store, file_store
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent for testing."""
        agent = MagicMock(spec=Agent)
        agent.name = "TestAgent"
        agent.version = "1.0.0"
        agent.go = AsyncMock()
        agent.thread_store = MagicMock()  # Add thread_store attribute
        return agent
    
    @pytest.mark.asyncio
    @patch('weave.init')
    @patch('space_monkey.slack_app.AsyncApp')
    @patch('space_monkey.slack_app.Agent')
    async def test_startup_initialization(self, mock_agent_class, mock_async_app, mock_weave_init, mock_agent, mock_stores):
        """Test complete startup initialization process."""
        thread_store, file_store = mock_stores
        
        # Mock Slack app
        mock_slack_app = AsyncMock()
        mock_async_app.return_value = mock_slack_app
        mock_slack_app.client.auth_test.return_value = {"user_id": "U12345"}
        
        # Mock event handler registration
        mock_slack_app.event = MagicMock(return_value=lambda handler: handler)
        mock_slack_app.use = MagicMock(return_value=lambda handler: handler)
        
        # Mock classifier agent
        mock_classifier = AsyncMock()
        mock_agent_class.return_value = mock_classifier
        
        app = SlackApp(
            agent=mock_agent,
            thread_store=thread_store,
            file_store=file_store,
            response_topics="test topics"
        )
        
        # Mock socket handler
        with patch('space_monkey.slack_app.AsyncSocketModeHandler') as mock_handler:
            mock_socket_handler = AsyncMock()
            mock_handler.return_value = mock_socket_handler
            
            # Test startup
            await app._startup()
            
            # Verify initialization
            assert app.bot_user_id == "U12345"
            assert app.message_classifier_agent == mock_classifier
            mock_weave_init.assert_called_once_with('test-project')

class TestMessageProcessing:
    """Test message processing and classification."""
    
    @pytest_asyncio.fixture
    async def app_with_mocks(self):
        """Create SlackApp with all necessary mocks."""
        # Mock stores
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        
        # Mock agent
        agent = AsyncMock(spec=Agent)
        agent.name = "TestAgent"
        agent.version = "1.0.0"
        agent.go = AsyncMock()
        agent.thread_store = MagicMock()  # Add thread_store attribute
        
        # Create app
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store,
            response_topics="test topics"
        )
        
        # Mock classifier
        app.message_classifier_agent = AsyncMock()
        app.bot_user_id = "U12345"
        
        # Mock Slack app
        app.slack_app = AsyncMock()
        app.slack_app.client.reactions_add = AsyncMock()
        
        return app
    
    @pytest.mark.asyncio
    async def test_should_process_message_new_message(self, app_with_mocks):
        """Test that new messages are processed."""
        app = app_with_mocks
        app.thread_store.find_messages_by_attribute.return_value = []
        
        event = {
            "ts": "1234567890.123",
            "channel_type": "im",
            "text": "Hello"
        }
        
        result = await app._should_process_message(event)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_should_process_message_duplicate(self, app_with_mocks):
        """Test that duplicate messages are not processed."""
        app = app_with_mocks
        app.thread_store.find_messages_by_attribute.return_value = [MagicMock()]
        
        event = {
            "ts": "1234567890.123",
            "channel_type": "im",
            "text": "Hello"
        }
        
        result = await app._should_process_message(event)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_or_create_thread_new(self, app_with_mocks):
        """Test creating new thread."""
        app = app_with_mocks
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        thread = await app._get_or_create_thread(event)
        
        assert thread.platforms["slack"]["channel"] == "C12345"
        assert thread.platforms["slack"]["thread_ts"] == "1234567890.123"
        app.thread_store.save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_or_create_thread_existing(self, app_with_mocks):
        """Test finding existing thread."""
        app = app_with_mocks
        existing_thread = Thread(id="existing-thread")
        app.thread_store.find_by_platform.return_value = [existing_thread]
        
        event = {
            "channel": "C12345",
            "thread_ts": "1234567890.123"
        }
        
        thread = await app._get_or_create_thread(event)
        
        assert thread == existing_thread
        app.thread_store.save.assert_not_called()

class TestMessageClassification:
    """Test message classification logic."""
    
    @pytest_asyncio.fixture
    async def app_with_classifier(self):
        """Create SlackApp with classifier setup."""
        # Mock stores
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        
        # Mock agent
        agent = AsyncMock(spec=Agent)
        agent.name = "TestAgent"
        agent.version = "1.0.0"
        agent.thread_store = MagicMock()  # Add thread_store attribute
        
        # Create app
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store,
            response_topics="test topics"
        )
        
        # Mock classifier
        app.message_classifier_agent = AsyncMock()
        app.bot_user_id = "U12345"
        app.slack_app = AsyncMock()
        
        return app
    
    @pytest.mark.asyncio
    async def test_classification_ignore(self, app_with_classifier):
        """Test classification resulting in ignore."""
        app = app_with_classifier
        
        # Mock classifier response
        classify_message = Message(
            role="assistant",
            content=json.dumps({
                "response_type": "ignore",
                "reasoning": "Not relevant to agent"
            })
        )
        app.message_classifier_agent.go.return_value = (None, [classify_message])
        
        # Mock thread creation
        thread = Thread()
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "text": "Random message",
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        with patch.object(app, '_get_or_create_thread', return_value=thread):
            response_type, content = await app._process_message("Random message", event)
        
        assert response_type == "none"
        assert content == ""
    
    @pytest.mark.asyncio
    async def test_classification_emoji(self, app_with_classifier):
        """Test classification resulting in emoji reaction."""
        app = app_with_classifier
        
        # Mock classifier response
        classify_message = Message(
            role="assistant",
            content=json.dumps({
                "response_type": "emoji_reaction",
                "suggested_emoji": "thumbsup",
                "reasoning": "Simple acknowledgment"
            })
        )
        app.message_classifier_agent.go.return_value = (None, [classify_message])
        
        # Mock thread creation
        thread = Thread()
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "text": "Thanks!",
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        with patch.object(app, '_get_or_create_thread', return_value=thread):
            response_type, content = await app._process_message("Thanks!", event)
        
        assert response_type == "emoji"
        assert content["emoji"] == "thumbsup"
        assert content["ts"] == "1234567890.123"
        assert content["channel"] == "C12345"
    
    @pytest.mark.asyncio
    async def test_classification_full_response(self, app_with_classifier):
        """Test classification resulting in full response."""
        app = app_with_classifier
        
        # Mock classifier response
        classify_message = Message(
            role="assistant",
            content=json.dumps({
                "response_type": "full_response",
                "reasoning": "Requires detailed response"
            })
        )
        app.message_classifier_agent.go.return_value = (None, [classify_message])
        
        # Mock agent response
        assistant_message = Message(
            role="assistant",
            content="Here's my detailed response.",
            metrics={"model": "gpt-4.1", "completion_tokens": 10}
        )
        app.agent.go.return_value = (None, [assistant_message])
        
        # Mock thread creation
        thread = Thread()
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "text": "How do I use this?",
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        with patch.object(app, '_get_or_create_thread', return_value=thread):
            response_type, content = await app._process_message("How do I use this?", event)
        
        assert response_type == "message"
        assert "Here's my detailed response." in content["text"]

class TestFileHandling:
    """Test file upload and attachment handling."""
    
    @pytest_asyncio.fixture
    async def app_with_files(self):
        """Create SlackApp with file handling mocks."""
        # Mock stores
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        
        # Mock agent
        agent = AsyncMock(spec=Agent)
        agent.name = "TestAgent"
        agent.version = "1.0.0"
        agent.thread_store = MagicMock()  # Add thread_store attribute
        
        # Create app
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store
        )
        
        # Mock Slack app
        app.slack_app = AsyncMock()
        app.message_classifier_agent = AsyncMock()
        app.bot_user_id = "U12345"
        
        return app
    
    @pytest.mark.asyncio
    async def test_file_upload_process(self, app_with_files):
        """Test file upload to Slack."""
        app = app_with_files
        
        # Mock attachment
        attachment = MagicMock(spec=Attachment)
        attachment.filename = "test.mp3"
        attachment.mime_type = "audio/mpeg"
        attachment.get_content_bytes = AsyncMock(return_value=b"fake audio data")
        
        # Mock tool message with attachment (include required tool_call_id)
        tool_message = Message(
            role="tool",
            content='{"success": true}',
            tool_call_id="test_tool_call_123",
            attachments=[attachment]
        )
        
        # Mock assistant message
        assistant_message = Message(
            role="assistant",
            content="Here's your audio file!"
        )
        
        # Mock agent response
        app.agent.go.return_value = (None, [tool_message, assistant_message])
        
        # Mock classifier
        classify_message = Message(
            role="assistant",
            content=json.dumps({"response_type": "full_response"})
        )
        app.message_classifier_agent.go.return_value = (None, [classify_message])
        
        # Mock Slack file upload
        app.slack_app.client.files_getUploadURLExternal.return_value = {
            "upload_url": "https://files.slack.com/upload",
            "file_id": "F12345"
        }
        app.slack_app.client.files_completeUploadExternal.return_value = {"ok": True}
        
        # Mock thread
        thread = Thread()
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "text": "Generate audio",
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        with patch.object(app, '_get_or_create_thread', return_value=thread), \
             patch('aiohttp.ClientSession') as mock_session:
            
            # Mock aiohttp response
            mock_response = AsyncMock()
            mock_response.status = 200
            
            # Create proper async context manager mocks
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_post)
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            response_type, content = await app._process_message("Generate audio", event)
        
        # Should return none since file upload handles the response
        assert response_type == "none"
        
        # Verify file upload calls
        app.slack_app.client.files_getUploadURLExternal.assert_called_once()
        app.slack_app.client.files_completeUploadExternal.assert_called_once()

class TestReactionHandling:
    """Test reaction added/removed event handling."""
    
    @pytest_asyncio.fixture
    async def app_with_reactions(self):
        """Create SlackApp with reaction handling setup."""
        # Mock stores
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        
        # Mock agent
        agent = AsyncMock(spec=Agent)
        agent.name = "TestAgent"
        agent.thread_store = MagicMock()  # Add thread_store attribute
        
        # Create app
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store
        )
        
        return app
    
    @pytest.mark.asyncio
    async def test_reaction_added(self, app_with_reactions):
        """Test handling reaction added events."""
        app = app_with_reactions
        
        # Mock message and thread
        message = Message(id="msg123", role="user", content="Test")
        thread = MagicMock(spec=Thread)
        thread.id = "thread123"
        thread.add_reaction = MagicMock(return_value=True)
        
        app.thread_store.find_messages_by_attribute.return_value = [message]
        app.thread_store.get_thread_by_message_id.return_value = thread
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "reaction": "thumbsup",
            "item": {"ts": "1234567890.123"}
        }
        
        await app._handle_reaction_added(event, None)
        
        thread.add_reaction.assert_called_once_with("msg123", "thumbsup", "U67890")
        app.thread_store.save.assert_called_once_with(thread)
    
    @pytest.mark.asyncio
    async def test_reaction_removed(self, app_with_reactions):
        """Test handling reaction removed events."""
        app = app_with_reactions
        
        # Mock message and thread
        message = Message(id="msg123", role="user", content="Test")
        thread = MagicMock(spec=Thread)
        thread.id = "thread123"
        thread.remove_reaction = MagicMock(return_value=True)
        
        app.thread_store.find_messages_by_attribute.return_value = [message]
        app.thread_store.get_thread_by_message_id.return_value = thread
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "reaction": "thumbsup",
            "item": {"ts": "1234567890.123"}
        }
        
        await app._handle_reaction_removed(event, None)
        
        thread.remove_reaction.assert_called_once_with("msg123", "thumbsup", "U67890")
        app.thread_store.save.assert_called_once_with(thread)

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest_asyncio.fixture
    async def app_with_errors(self):
        """Create SlackApp for error testing."""
        # Mock stores
        thread_store = AsyncMock(spec=ThreadStore)
        file_store = AsyncMock(spec=FileStore)
        
        # Mock agent
        agent = AsyncMock(spec=Agent)
        agent.name = "TestAgent"
        agent.thread_store = MagicMock()  # Add thread_store attribute
        
        # Create app
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store
        )
        
        app.message_classifier_agent = AsyncMock()
        app.bot_user_id = "U12345"
        app.slack_app = AsyncMock()
        
        return app
    
    @pytest.mark.asyncio
    async def test_agent_error_handling(self, app_with_errors):
        """Test handling agent errors gracefully."""
        app = app_with_errors
        
        # Mock classifier
        classify_message = Message(
            role="assistant",
            content=json.dumps({"response_type": "full_response"})
        )
        app.message_classifier_agent.go.return_value = (None, [classify_message])
        
        # Mock agent to raise error
        app.agent.go.side_effect = Exception("Agent processing error")
        
        # Mock thread
        thread = Thread()
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "text": "Test message",
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        with patch.object(app, '_get_or_create_thread', return_value=thread):
            response_type, content = await app._process_message("Test message", event)
        
        assert response_type == "message"
        assert "error" in content["text"].lower()
    
    @pytest.mark.asyncio
    async def test_thread_not_found_error(self, app_with_errors):
        """Test handling thread not found errors."""
        app = app_with_errors
        
        # Mock classifier
        classify_message = Message(
            role="assistant",
            content=json.dumps({"response_type": "full_response"})
        )
        app.message_classifier_agent.go.return_value = (None, [classify_message])
        
        # Mock agent to raise thread not found error
        app.agent.go.side_effect = ValueError("Thread with ID abc123 not found")
        
        # Mock thread
        thread = Thread(id="abc123")
        app.thread_store.find_by_platform.return_value = []
        app.thread_store.save = AsyncMock()
        
        event = {
            "user": "U67890",
            "text": "Test message",
            "channel": "C12345",
            "ts": "1234567890.123"
        }
        
        with patch.object(app, '_get_or_create_thread', return_value=thread):
            response_type, content = await app._process_message("Test message", event)
        
        assert response_type == "message"
        assert "error" in content["text"].lower() or "apologize" in content["text"].lower()
    
    @pytest.mark.asyncio
    async def test_database_error_in_should_process(self, app_with_errors):
        """Test handling database errors in should_process_message."""
        app = app_with_errors
        
        # Mock database error
        app.thread_store.find_messages_by_attribute.side_effect = Exception("Database error")
        
        event = {
            "ts": "1234567890.123",
            "channel_type": "im",
            "text": "Hello"
        }
        
        # Should return False to be conservative
        result = await app._should_process_message(event)
        assert result is False

class TestUtilityMethods:
    """Test utility and helper methods."""
    
    @pytest.fixture
    def simple_app(self):
        """Create simple SlackApp for utility testing."""
        agent = MagicMock()
        agent.name = "TestAgent"
        agent.version = "1.0.0"
        
        app = SlackApp(
            agent=agent,
            thread_store=AsyncMock(),
            file_store=AsyncMock()
        )
        
        return app
    
    def test_get_dev_footer_with_metrics(self, simple_app):
        """Test dev footer generation with metrics."""
        metrics = {
            "model": "gpt-4.1",
            "weave_call": {"ui_url": "https://weave.wandb.ai/trace/123"}
        }
        
        footer = simple_app._get_dev_footer(metrics)
        
        assert "TestAgent: v1.0.0" in footer
        assert "gpt-4.1" in footer
        assert "Weave trace" in footer
        assert "https://weave.wandb.ai/trace/123" in footer
    
    def test_get_dev_footer_minimal(self, simple_app):
        """Test dev footer with minimal metrics."""
        metrics = {"model": "gpt-4.1"}
        
        footer = simple_app._get_dev_footer(metrics)
        
        assert "TestAgent: v1.0.0" in footer
        assert "gpt-4.1" in footer
        assert "Weave trace" not in footer
    
    def test_get_dev_footer_empty(self, simple_app):
        """Test dev footer with no useful metrics."""
        metrics = {}
        
        footer = simple_app._get_dev_footer(metrics)
        
        # When no model or weave_url, it defaults to "N/A" for model but returns empty string
        # because model defaults to "N/A" which is truthy
        assert "TestAgent: v1.0.0" in footer
        assert "N/A" in footer

class TestHealthMonitoring:
    """Test health monitoring functionality."""
    
    @pytest.fixture
    def app_with_health(self):
        """Create SlackApp with health monitoring."""
        agent = MagicMock()
        thread_store = AsyncMock()
        file_store = AsyncMock()
        
        # Don't set health_check_url in the app itself
        with patch.dict(os.environ, {'HEALTH_CHECK_URL': 'http://test-health-check'}):
            app = SlackApp(
                agent=agent,
                thread_store=thread_store,
                file_store=file_store
            )
        
        return app
    
    @patch('requests.get')
    @patch('threading.Thread')
    def test_health_monitoring_start(self, mock_thread, mock_get, app_with_health):
        """Test health monitoring thread startup."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "OK"
        
        app_with_health._start_health_monitoring()
        
        # Verify thread was created and started
        mock_thread.assert_called_once()
        assert mock_thread.return_value.start.called
    
    def test_no_health_monitoring_without_url(self):
        """Test that health monitoring doesn't start without URL."""
        # Clear the health check URL from environment
        with patch.dict(os.environ, {'HEALTH_CHECK_URL': ''}, clear=True):
            agent = MagicMock()
            app = SlackApp(
                agent=agent,
                thread_store=AsyncMock(),
                file_store=AsyncMock()
            )
            
            # Should not raise error when no health_check_url
            app._start_health_monitoring()
            assert app.health_thread is None

if __name__ == "__main__":
    pytest.main([__file__]) 