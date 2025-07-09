"""
Tests for the agent base classes
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, Optional

from space_monkey.agents.base import SlackAgent, ClassifierAgent, SimpleAgent
from narrator import Thread, Message, ThreadStore, FileStore

class TestSlackAgent:
    """Tests for the base SlackAgent class"""
    
    def test_agent_initialization(self, mock_thread_store, mock_file_store):
        """Test basic agent initialization"""
        # Create a concrete implementation for testing
        class TestAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "test response"
        
        mock_bot = Mock()
        config = {"version": "1.0.0", "test_param": "value"}
        
        agent = TestAgent("test-agent", config, mock_thread_store, mock_file_store, mock_bot)
        
        assert agent.name == "test-agent"
        assert agent.config == config
        assert agent.thread_store == mock_thread_store
        assert agent.file_store == mock_file_store
        assert agent.bot == mock_bot
        assert agent.version == "1.0.0"
    
    def test_agent_initialization_with_default_version(self, mock_thread_store, mock_file_store):
        """Test agent initialization with default version"""
        class TestAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "test response"
        
        mock_bot = Mock()
        config = {"test_param": "value"}  # No version specified
        
        agent = TestAgent("test-agent", config, mock_thread_store, mock_file_store, mock_bot)
        
        assert agent.version == "1.0.0"  # Default version
    
    async def test_agent_lifecycle_methods(self, mock_thread_store, mock_file_store):
        """Test agent lifecycle methods have default implementations"""
        class TestAgent(SlackAgent):
            def should_handle(self, event, thread):
                return True
            
            async def process_message(self, thread, event):
                return "test response"
        
        mock_bot = Mock()
        agent = TestAgent("test-agent", {}, mock_thread_store, mock_file_store, mock_bot)
        
        # These should not raise exceptions (default implementations)
        await agent.on_startup()
        await agent.on_shutdown()
        await agent.on_reaction_added({}, Mock())
        await agent.on_reaction_removed({}, Mock())
    
    def test_abstract_methods_must_be_implemented(self, mock_thread_store, mock_file_store):
        """Test that abstract methods must be implemented"""
        mock_bot = Mock()
        
        # This should raise TypeError because abstract methods aren't implemented
        with pytest.raises(TypeError):
            SlackAgent("test", {}, mock_thread_store, mock_file_store, mock_bot)

class TestClassifierAgent:
    """Tests for the ClassifierAgent class"""
    
    async def test_classifier_process_message_returns_none(self, mock_thread_store, mock_file_store):
        """Test that classifier process_message always returns None"""
        class TestClassifier(ClassifierAgent):
            def should_handle(self, event, thread):
                return True
            
            async def classify_message(self, thread, event):
                return {"response_type": "full_response", "reasoning": "test"}
        
        mock_bot = Mock()
        classifier = TestClassifier("classifier", {}, mock_thread_store, mock_file_store, mock_bot)
        
        result = await classifier.process_message(Mock(), {})
        assert result is None  # Classifiers don't return text responses
    
    async def test_classifier_abstract_method(self, mock_thread_store, mock_file_store):
        """Test that classify_message is abstract"""
        mock_bot = Mock()
        
        # This should raise TypeError because classify_message isn't implemented
        with pytest.raises(TypeError):
            ClassifierAgent("classifier", {}, mock_thread_store, mock_file_store, mock_bot)

class TestSimpleAgent:
    """Tests for the SimpleAgent class"""
    
    def test_simple_agent_initialization(self, mock_thread_store, mock_file_store):
        """Test SimpleAgent initialization with patterns"""
        mock_bot = Mock()
        config = {
            "patterns": ["hello", "hi", "hey"],
            "response_template": "Hello from {name}!"
        }
        
        agent = SimpleAgent("simple", config, mock_thread_store, mock_file_store, mock_bot)
        
        assert agent.patterns == ["hello", "hi", "hey"]
        assert agent.response_template == "Hello from {name}!"
    
    def test_simple_agent_initialization_with_defaults(self, mock_thread_store, mock_file_store):
        """Test SimpleAgent initialization with default values"""
        mock_bot = Mock()
        config = {}
        
        agent = SimpleAgent("simple", config, mock_thread_store, mock_file_store, mock_bot)
        
        assert agent.patterns == []
        assert agent.response_template == "Hello from {name}!"
    
    def test_simple_agent_should_handle_matching_pattern(self, mock_thread_store, mock_file_store):
        """Test SimpleAgent handles messages matching patterns"""
        mock_bot = Mock()
        config = {"patterns": ["hello", "test"]}
        
        agent = SimpleAgent("simple", config, mock_thread_store, mock_file_store, mock_bot)
        
        # Should handle messages containing patterns
        assert agent.should_handle({"text": "Hello world!"}, Mock()) == True
        assert agent.should_handle({"text": "This is a test"}, Mock()) == True
        assert agent.should_handle({"text": "HELLO THERE"}, Mock()) == True  # Case insensitive
    
    def test_simple_agent_should_not_handle_non_matching(self, mock_thread_store, mock_file_store):
        """Test SimpleAgent doesn't handle non-matching messages"""
        mock_bot = Mock()
        config = {"patterns": ["hello", "test"]}
        
        agent = SimpleAgent("simple", config, mock_thread_store, mock_file_store, mock_bot)
        
        # Should not handle messages without patterns
        assert agent.should_handle({"text": "Goodbye world!"}, Mock()) == False
        assert agent.should_handle({"text": "Random message"}, Mock()) == False
        assert agent.should_handle({}, Mock()) == False  # No text
    
    async def test_simple_agent_process_message(self, mock_thread_store, mock_file_store):
        """Test SimpleAgent message processing"""
        mock_bot = Mock()
        config = {
            "response_template": "Hello from {name}! Version {version}",
            "version": "2.0.0"
        }
        
        agent = SimpleAgent("simple", config, mock_thread_store, mock_file_store, mock_bot)
        
        response = await agent.process_message(Mock(), {})
        
        assert response == "Hello from simple! Version 2.0.0"
    
    def test_simple_agent_empty_patterns(self, mock_thread_store, mock_file_store):
        """Test SimpleAgent with empty patterns"""
        mock_bot = Mock()
        config = {"patterns": []}
        
        agent = SimpleAgent("simple", config, mock_thread_store, mock_file_store, mock_bot)
        
        # Should not handle any messages with empty patterns
        assert agent.should_handle({"text": "Any message"}, Mock()) == False

# Integration test with actual test agent classes from conftest
class TestAgentIntegration:
    """Integration tests using test agent classes from conftest"""
    
    def test_test_agent_should_handle(self, test_agent_class, mock_thread_store, mock_file_store):
        """Test the TestAgent from conftest"""
        mock_bot = Mock()
        agent = test_agent_class("test", {}, mock_thread_store, mock_file_store, mock_bot)
        
        assert agent.should_handle({"text": "This is a test"}, Mock()) == True
        assert agent.should_handle({"text": "TEST MESSAGE"}, Mock()) == True
        assert agent.should_handle({"text": "Hello world"}, Mock()) == False
    
    async def test_test_agent_process_message(self, test_agent_class, mock_thread_store, mock_file_store):
        """Test the TestAgent message processing"""
        mock_bot = Mock()
        agent = test_agent_class("test", {}, mock_thread_store, mock_file_store, mock_bot)
        
        response = await agent.process_message(Mock(), {})
        assert response == "Test response"
    
    async def test_test_classifier_classify_message(self, test_classifier_class, mock_thread_store, mock_file_store):
        """Test the TestClassifier from conftest"""
        mock_bot = Mock()
        classifier = test_classifier_class("classifier", {}, mock_thread_store, mock_file_store, mock_bot)
        
        # Test ignore classification
        result = await classifier.classify_message(Mock(), {"text": "ignore this"})
        assert result["response_type"] == "ignore"
        assert result["reasoning"] == "Test ignore"
        
        # Test emoji classification
        result = await classifier.classify_message(Mock(), {"text": "emoji please"})
        assert result["response_type"] == "emoji_reaction"
        assert result["suggested_emoji"] == "thumbsup"
        assert result["reasoning"] == "Test emoji"
        
        # Test full response classification
        result = await classifier.classify_message(Mock(), {"text": "regular message"})
        assert result["response_type"] == "full_response"
        assert result["reasoning"] == "Test full response" 