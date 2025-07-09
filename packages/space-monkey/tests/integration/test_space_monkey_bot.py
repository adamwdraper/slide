"""
Integration tests for the main SpaceMonkey bot functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from space_monkey import SpaceMonkey, SlackAgent, ClassifierAgent, Config
from narrator import Thread, Message

class TestSpaceMonkeyBotIntegration:
    """Integration tests for SpaceMonkey bot"""
    
    def test_space_monkey_from_env(self):
        """Test creating SpaceMonkey from environment"""
        with patch.dict('os.environ', {
            'SLACK_BOT_TOKEN': 'xoxb-test',
            'SLACK_APP_TOKEN': 'xapp-test'
        }):
            bot = SpaceMonkey.from_env()
            
            assert bot.config.slack_bot_token == 'xoxb-test'
            assert bot.config.slack_app_token == 'xapp-test'
    
    def test_space_monkey_initialization(self, test_config):
        """Test SpaceMonkey initialization"""
        bot = SpaceMonkey(test_config)
        
        assert bot.config == test_config
        assert bot.agent_registry is not None
        assert bot.middleware is not None
        assert bot.event_router is not None
        assert bot._running == False
        assert bot._startup_complete == False
    
    def test_add_agent_before_startup(self, test_config, test_agent_class):
        """Test adding agents before startup"""
        bot = SpaceMonkey(test_config)
        config = {"version": "1.0.0"}
        
        bot.add_agent("test-agent", test_agent_class, config)
        
        # Should be registered in registry
        assert "test-agent" in bot.agent_registry._agent_classes
        assert bot.agent_registry._agent_configs["test-agent"] == config
    
    def test_add_agent_after_startup_fails(self, test_config, test_agent_class):
        """Test that adding agents after startup fails"""
        bot = SpaceMonkey(test_config)
        bot._startup_complete = True
        
        with pytest.raises(RuntimeError, match="Cannot add agents after bot startup"):
            bot.add_agent("test-agent", test_agent_class)
    
    def test_add_middleware(self, test_config):
        """Test adding middleware"""
        bot = SpaceMonkey(test_config)
        
        async def test_middleware(event):
            return event
        
        bot.add_middleware(test_middleware)
        
        assert test_middleware in bot.middleware._middleware
    
    @patch('space_monkey.core.bot.weave')
    async def test_initialize_weave_success(self, mock_weave, test_config):
        """Test successful Weave initialization"""
        test_config.wandb_api_key = "test-key"
        test_config.wandb_project = "test-project"
        bot = SpaceMonkey(test_config)
        
        await bot._initialize_weave()
        
        mock_weave.init.assert_called_once_with("test-project")
    
    @patch('space_monkey.core.bot.weave')
    async def test_initialize_weave_skip_without_config(self, mock_weave, test_config):
        """Test Weave initialization skipped without config"""
        # No wandb config
        bot = SpaceMonkey(test_config)
        
        await bot._initialize_weave()
        
        mock_weave.init.assert_not_called()
    
    @patch('space_monkey.core.bot.ThreadStore.create')
    @patch('space_monkey.core.bot.FileStore.create')
    async def test_initialize_stores(self, mock_file_create, mock_thread_create, test_config):
        """Test store initialization"""
        mock_thread_store = AsyncMock()
        mock_file_store = AsyncMock()
        mock_thread_create.return_value = mock_thread_store
        mock_file_create.return_value = mock_file_store
        
        bot = SpaceMonkey(test_config)
        await bot._initialize_stores()
        
        assert bot.thread_store == mock_thread_store
        assert bot.file_store == mock_file_store
        mock_thread_create.assert_called_once()
        mock_file_create.assert_called_once()
    
    @patch('space_monkey.core.bot.ThreadStore.create')
    async def test_initialize_stores_with_database_url(self, mock_thread_create, test_config):
        """Test store initialization with database URL"""
        test_config.database_url = "postgresql://test"
        mock_thread_store = AsyncMock()
        mock_thread_create.return_value = mock_thread_store
        
        bot = SpaceMonkey(test_config)
        await bot._initialize_stores()
        
        mock_thread_create.assert_called_once_with("postgresql://test")
    
    @patch('space_monkey.core.bot.AsyncApp')
    async def test_initialize_slack_app(self, mock_app_class, test_config):
        """Test Slack app initialization"""
        mock_app = Mock()
        mock_app.client.auth_test = AsyncMock(return_value={"user_id": "U123TEST"})
        mock_app_class.return_value = mock_app
        
        bot = SpaceMonkey(test_config)
        await bot._initialize_slack_app()
        
        assert bot.slack_app == mock_app
        assert bot.bot_user_id == "U123TEST"
        mock_app_class.assert_called_once_with(token=test_config.slack_bot_token)
    
    def test_property_is_running(self, test_config):
        """Test is_running property"""
        bot = SpaceMonkey(test_config)
        
        assert bot.is_running == False
        
        bot._running = True
        assert bot.is_running == True
    
    def test_property_startup_complete(self, test_config):
        """Test startup_complete property"""
        bot = SpaceMonkey(test_config)
        
        assert bot.startup_complete == False
        
        bot._startup_complete = True
        assert bot.startup_complete == True

class TestSpaceMonkeyEventProcessing:
    """Integration tests for event processing"""
    
    async def test_agent_registration_and_processing(self, space_monkey_bot, test_agent_class, sample_slack_event):
        """Test full agent registration and message processing"""
        # Add agent
        space_monkey_bot.add_agent("test-agent", test_agent_class, {"version": "1.0.0"})
        
        # Initialize agents
        await space_monkey_bot.agent_registry.initialize_all(
            space_monkey_bot.thread_store,
            space_monkey_bot.file_store
        )
        
        # Create a thread for testing
        thread = Thread()
        
        # Get agents that should handle the event
        handling_agents = space_monkey_bot.agent_registry.get_agents_for_event(sample_slack_event, thread)
        
        # Test agent should handle messages with "test" in them
        sample_slack_event["text"] = "This is a test message"
        handling_agents = space_monkey_bot.agent_registry.get_agents_for_event(sample_slack_event, thread)
        
        assert len(handling_agents) == 1
        assert handling_agents[0].name == "test-agent"
        
        # Process message
        response = await handling_agents[0].process_message(thread, sample_slack_event)
        assert response == "Test response"
    
    async def test_classifier_and_regular_agent_workflow(self, space_monkey_bot, test_classifier_class, test_agent_class):
        """Test workflow with both classifier and regular agents"""
        # Add both types of agents
        space_monkey_bot.add_agent("classifier", test_classifier_class)
        space_monkey_bot.add_agent("test-agent", test_agent_class)
        
        # Initialize agents
        await space_monkey_bot.agent_registry.initialize_all(
            space_monkey_bot.thread_store,
            space_monkey_bot.file_store
        )
        
        # Get classifiers
        classifiers = space_monkey_bot.agent_registry.get_classifiers()
        assert len(classifiers) == 1
        assert isinstance(classifiers[0], ClassifierAgent)
        
        # Test classification
        event = {"text": "ignore this message"}
        thread = Thread()
        
        classification = await classifiers[0].classify_message(thread, event)
        assert classification["response_type"] == "ignore"
    
    async def test_middleware_processing(self, space_monkey_bot):
        """Test middleware processing"""
        # Add middleware that modifies events
        async def add_timestamp_middleware(event):
            event["processed_timestamp"] = "12345"
            return event
        
        space_monkey_bot.add_middleware(add_timestamp_middleware)
        
        # Process event through middleware
        test_event = {"text": "test message"}
        processed_event = await space_monkey_bot.middleware.process(test_event)
        
        assert processed_event["processed_timestamp"] == "12345"

class TestSpaceMonkeyConfiguration:
    """Tests for SpaceMonkey configuration handling"""
    
    def test_config_validation_success(self):
        """Test successful config validation"""
        config = Config(
            slack_bot_token="xoxb-test",
            slack_app_token="xapp-test"
        )
        
        # Should not raise
        config.validate_required_fields()
    
    def test_config_validation_failure(self):
        """Test config validation failure"""
        config = Config(
            slack_bot_token="",  # Empty token
            slack_app_token="xapp-test"
        )
        
        with pytest.raises(ValueError):
            config.validate_required_fields()
    
    @patch.dict('os.environ', {
        'SLACK_BOT_TOKEN': 'xoxb-from-env',
        'SLACK_APP_TOKEN': 'xapp-from-env',
        'ENV': 'production'
    })
    def test_from_env_integration(self):
        """Test creating bot from environment variables"""
        bot = SpaceMonkey.from_env()
        
        assert bot.config.slack_bot_token == 'xoxb-from-env'
        assert bot.config.slack_app_token == 'xapp-from-env'
        assert bot.config.environment == 'production'

class TestSpaceMonkeyExamples:
    """Tests using the example bot patterns"""
    
    async def test_basic_echo_agent_pattern(self, space_monkey_bot):
        """Test basic echo agent pattern from examples"""
        class EchoAgent(SlackAgent):
            def should_handle(self, event, thread):
                return event.get("text", "").lower().startswith("echo:")
            
            async def process_message(self, thread, event):
                text = event.get("text", "")
                if text.lower().startswith("echo:"):
                    echo_text = text[5:].strip()
                    return f"🔊 Echo: {echo_text}"
                return None
        
        # Add and initialize agent
        space_monkey_bot.add_agent("echo", EchoAgent)
        await space_monkey_bot.agent_registry.initialize_all(
            space_monkey_bot.thread_store,
            space_monkey_bot.file_store
        )
        
        # Test handling
        event = {"text": "echo: Hello world!"}
        thread = Thread()
        
        agents = space_monkey_bot.agent_registry.get_agents_for_event(event, thread)
        assert len(agents) == 1
        
        response = await agents[0].process_message(thread, event)
        assert response == "🔊 Echo: Hello world!"
        
        # Test non-handling
        event = {"text": "regular message"}
        agents = space_monkey_bot.agent_registry.get_agents_for_event(event, thread)
        assert len(agents) == 0
    
    async def test_help_agent_pattern(self, space_monkey_bot):
        """Test help agent pattern from examples"""
        class HelpAgent(SlackAgent):
            def should_handle(self, event, thread):
                text = event.get("text", "").lower()
                return "help" in text
            
            async def process_message(self, thread, event):
                return "🤖 **Help**\n\nI can help you with various tasks!"
        
        # Add and initialize agent
        space_monkey_bot.add_agent("help", HelpAgent)
        await space_monkey_bot.agent_registry.initialize_all(
            space_monkey_bot.thread_store,
            space_monkey_bot.file_store
        )
        
        # Test handling
        event = {"text": "I need help"}
        thread = Thread()
        
        agents = space_monkey_bot.agent_registry.get_agents_for_event(event, thread)
        assert len(agents) == 1
        
        response = await agents[0].process_message(thread, event)
        assert "Help" in response
        assert "🤖" in response 