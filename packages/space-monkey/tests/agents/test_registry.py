"""
Tests for the agent registry system
"""

import pytest
from unittest.mock import Mock, AsyncMock

from space_monkey.agents.registry import AgentRegistry
from space_monkey.agents.base import SlackAgent, ClassifierAgent
from narrator import Thread

class TestAgentRegistry:
    """Tests for the AgentRegistry class"""
    
    def test_registry_initialization(self):
        """Test registry initialization"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        assert registry.bot == mock_bot
        assert registry.agent_count == 0
        assert registry.classifier_count == 0
        assert registry.regular_agent_count == 0
        assert len(registry.list_agents()) == 0
    
    def test_register_agent(self, test_agent_class):
        """Test registering an agent"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        config = {"version": "1.0.0"}
        
        registry.register("test-agent", test_agent_class, config)
        
        assert "test-agent" in registry._agent_classes
        assert registry._agent_classes["test-agent"] == test_agent_class
        assert registry._agent_configs["test-agent"] == config
    
    def test_register_agent_with_default_config(self, test_agent_class):
        """Test registering an agent with default config"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        registry.register("test-agent", test_agent_class)
        
        assert registry._agent_configs["test-agent"] == {}
    
    def test_register_duplicate_agent_overwrites(self, test_agent_class):
        """Test registering duplicate agent overwrites previous registration"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Register first time
        registry.register("test-agent", test_agent_class, {"version": "1.0.0"})
        
        # Register again with different config
        registry.register("test-agent", test_agent_class, {"version": "2.0.0"})
        
        assert registry._agent_configs["test-agent"] == {"version": "2.0.0"}
    
    async def test_initialize_all_agents(self, test_agent_class, test_classifier_class, mock_thread_store, mock_file_store):
        """Test initializing all registered agents"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Register agents
        registry.register("test-agent", test_agent_class, {"version": "1.0.0"})
        registry.register("classifier", test_classifier_class, {"version": "2.0.0"})
        
        # Initialize all agents
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        assert registry.agent_count == 2
        assert registry.classifier_count == 1
        assert registry.regular_agent_count == 1
        
        # Check agents were created correctly
        test_agent = registry.get_agent("test-agent")
        assert test_agent is not None
        assert test_agent.name == "test-agent"
        assert test_agent.version == "1.0.0"
        
        classifier = registry.get_agent("classifier")
        assert classifier is not None
        assert classifier.name == "classifier"
        assert classifier.version == "2.0.0"
        assert isinstance(classifier, ClassifierAgent)
    
    async def test_initialize_agent_calls_startup(self, mock_thread_store, mock_file_store):
        """Test that agent initialization calls on_startup"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Create a mock agent class that tracks startup calls
        class MockAgent(SlackAgent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.startup_called = False
            
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "response"
            
            async def on_startup(self):
                self.startup_called = True
        
        registry.register("mock-agent", MockAgent)
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        agent = registry.get_agent("mock-agent")
        assert agent.startup_called == True
    
    async def test_initialize_agent_failure_raises_exception(self, mock_thread_store, mock_file_store):
        """Test that agent initialization failure raises exception"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Create an agent that fails during initialization
        class FailingAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "response"
            
            async def on_startup(self):
                raise RuntimeError("Startup failed")
        
        registry.register("failing-agent", FailingAgent)
        
        with pytest.raises(RuntimeError, match="Startup failed"):
            await registry.initialize_all(mock_thread_store, mock_file_store)
    
    async def test_shutdown_all_agents(self, test_agent_class, mock_thread_store, mock_file_store):
        """Test shutting down all agents"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Create agent that tracks shutdown calls
        class MockAgent(SlackAgent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.shutdown_called = False
            
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "response"
            
            async def on_shutdown(self):
                self.shutdown_called = True
        
        registry.register("mock-agent", MockAgent)
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        await registry.shutdown_all()
        
        agent = registry.get_agent("mock-agent")
        assert agent.shutdown_called == True
    
    async def test_shutdown_agent_failure_continues(self, mock_thread_store, mock_file_store):
        """Test that shutdown continues even if one agent fails"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Create agents, one that fails during shutdown
        class GoodAgent(SlackAgent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.shutdown_called = False
            
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "response"
            
            async def on_shutdown(self):
                self.shutdown_called = True
        
        class FailingAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "response"
            
            async def on_shutdown(self):
                raise RuntimeError("Shutdown failed")
        
        registry.register("good-agent", GoodAgent)
        registry.register("failing-agent", FailingAgent)
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        # Should not raise exception, but should continue
        await registry.shutdown_all()
        
        # Good agent should still be shut down
        good_agent = registry.get_agent("good-agent")
        assert good_agent.shutdown_called == True
    
    def test_get_agent(self, test_agent_class, mock_thread_store, mock_file_store):
        """Test getting an agent by name"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Should return None for non-existent agent
        assert registry.get_agent("non-existent") is None
        
        # Register and initialize agent
        registry.register("test-agent", test_agent_class)
        
        # Should still return None before initialization
        assert registry.get_agent("test-agent") is None
    
    async def test_get_classifiers(self, test_agent_class, test_classifier_class, mock_thread_store, mock_file_store):
        """Test getting classifier agents"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        registry.register("test-agent", test_agent_class)
        registry.register("classifier1", test_classifier_class)
        registry.register("classifier2", test_classifier_class)
        
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        classifiers = registry.get_classifiers()
        assert len(classifiers) == 2
        assert all(isinstance(c, ClassifierAgent) for c in classifiers)
    
    async def test_get_agents_for_event(self, test_agent_class, mock_thread_store, mock_file_store):
        """Test getting agents that should handle an event"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Create agents with different handling logic
        class AlwaysHandleAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "always"
        
        class NeverHandleAgent(SlackAgent):
            def should_handle(self, event, thread):
                return False
            
            async def process_message(self, thread, event):
                return "never"
        
        registry.register("always", AlwaysHandleAgent)
        registry.register("never", NeverHandleAgent)
        registry.register("test", test_agent_class)  # Handles "test" messages
        
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        # Test with event that contains "test"
        event = {"text": "this is a test message"}
        thread = Mock()
        
        handling_agents = registry.get_agents_for_event(event, thread)
        
        # Should get the always handler and test handler, but not never handler
        assert len(handling_agents) == 2
        agent_names = [agent.name for agent in handling_agents]
        assert "always" in agent_names
        assert "test" in agent_names
        assert "never" not in agent_names
    
    async def test_get_agents_for_event_handles_exceptions(self, mock_thread_store, mock_file_store):
        """Test that get_agents_for_event handles exceptions in should_handle"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        class ExceptionAgent(SlackAgent):
            def should_handle(self, event, thread):
                raise RuntimeError("Error in should_handle")
            
            async def process_message(self, thread, event):
                return "exception"
        
        class GoodAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "good"
        
        registry.register("exception", ExceptionAgent)
        registry.register("good", GoodAgent)
        
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        # Should handle exception and continue
        handling_agents = registry.get_agents_for_event({}, Mock())
        
        # Should only get the good agent
        assert len(handling_agents) == 1
        assert handling_agents[0].name == "good"
    
    async def test_list_agents(self, test_agent_class, test_classifier_class, mock_thread_store, mock_file_store):
        """Test listing all agents with their info"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        registry.register("test-agent", test_agent_class, {"version": "1.0.0"})
        registry.register("classifier", test_classifier_class, {"version": "2.0.0"})
        
        await registry.initialize_all(mock_thread_store, mock_file_store)
        
        agents_info = registry.list_agents()
        
        assert len(agents_info) == 2
        
        # Check test agent info
        test_info = agents_info["test-agent"]
        assert test_info["name"] == "test-agent"
        assert test_info["class"] == "TestAgent"
        assert test_info["version"] == "1.0.0"
        assert test_info["type"] == "regular"
        
        # Check classifier info
        classifier_info = agents_info["classifier"]
        assert classifier_info["name"] == "classifier"
        assert classifier_info["class"] == "TestClassifier"
        assert classifier_info["version"] == "2.0.0"
        assert classifier_info["type"] == "classifier"
    
    def test_agent_counts(self, test_agent_class, test_classifier_class):
        """Test agent count properties"""
        mock_bot = Mock()
        registry = AgentRegistry(mock_bot)
        
        # Initially empty
        assert registry.agent_count == 0
        assert registry.classifier_count == 0
        assert registry.regular_agent_count == 0
        
        # After registration but before initialization
        registry.register("test-agent", test_agent_class)
        registry.register("classifier", test_classifier_class)
        
        # Counts should still be 0 before initialization
        assert registry.agent_count == 0
        assert registry.classifier_count == 0
        assert registry.regular_agent_count == 0 