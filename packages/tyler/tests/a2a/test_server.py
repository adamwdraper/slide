"""Tests for A2A server implementation.

Tests cover:
- Protocol version (AC-1)
- Agent Card path (AC-2)
- Artifact production (AC-7)
- Context ID support (AC-8)
- Push notifications (AC-9, AC-10, AC-11)
- SDK integration
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

# Mock the a2a-sdk imports before importing server
import sys
mock_a2a = MagicMock()
mock_a2a.server = MagicMock()
mock_a2a.server.apps = MagicMock()
mock_a2a.server.request_handlers = MagicMock()
mock_a2a.server.agent_execution = MagicMock()
mock_a2a.server.events = MagicMock()
mock_a2a.server.tasks = MagicMock()
mock_a2a.types = MagicMock()
sys.modules['a2a'] = mock_a2a
sys.modules['a2a.server'] = mock_a2a.server
sys.modules['a2a.server.apps'] = mock_a2a.server.apps
sys.modules['a2a.server.request_handlers'] = mock_a2a.server.request_handlers
sys.modules['a2a.server.agent_execution'] = mock_a2a.server.agent_execution
sys.modules['a2a.server.events'] = mock_a2a.server.events
sys.modules['a2a.server.tasks'] = mock_a2a.server.tasks
sys.modules['a2a.types'] = mock_a2a.types

from tyler.a2a.server import A2AServer, A2A_PROTOCOL_VERSION, TylerTaskExecution
from tyler.a2a.types import Artifact, TextPart, FilePart, DataPart


# Helper to create all necessary patches for A2AServer
def create_server_patches():
    """Create context manager with all necessary patches."""
    return [
        patch('tyler.a2a.server.HAS_A2A', True),
        patch('tyler.a2a.server.AgentCard'),
        patch('tyler.a2a.server.AgentCapabilities'),
        patch('tyler.a2a.server.AgentSkill'),
        patch('tyler.a2a.server.InMemoryTaskStore'),
        patch('tyler.a2a.server.InMemoryQueueManager'),
        patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'),
    ]


class TestA2AProtocolVersion:
    """Test cases for protocol version (AC-1)."""
    
    def test_protocol_version_constant(self):
        """Test A2A_PROTOCOL_VERSION is 0.3.0."""
        assert A2A_PROTOCOL_VERSION == "0.3.0"
    
    def test_agent_card_created_with_valid_structure(self):
        """Test agent card is created with valid SDK v0.3.0 structure."""
        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.purpose = "Testing"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard') as mock_card, \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Check AgentCard was called with required v0.3.0 fields
            call_kwargs = mock_card.call_args.kwargs
            assert "name" in call_kwargs
            assert "url" in call_kwargs
            assert "version" in call_kwargs
            assert "description" in call_kwargs
            assert "defaultInputModes" in call_kwargs
            assert "defaultOutputModes" in call_kwargs
            assert "capabilities" in call_kwargs
            assert "skills" in call_kwargs


class TestAgentCardConfiguration:
    """Test cases for Agent Card configuration (AC-2)."""
    
    def test_agent_card_from_tyler_agent(self):
        """Test Agent Card is created from Tyler agent info."""
        mock_agent = MagicMock()
        mock_agent.name = "Research Assistant"
        mock_agent.purpose = "Research and analysis"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard') as mock_card, \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            call_kwargs = mock_card.call_args.kwargs
            assert call_kwargs["name"] == "Research Assistant"
            assert call_kwargs["description"] == "Research and analysis"
    
    def test_agent_card_has_capabilities_with_push_notifications(self):
        """Test Agent Card capabilities include push notifications support."""
        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.purpose = "Testing"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities') as mock_caps, \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Check AgentCapabilities was called with push notifications
            caps_call_kwargs = mock_caps.call_args.kwargs
            assert caps_call_kwargs.get("pushNotifications") is True
            assert caps_call_kwargs.get("streaming") is True
    
    def test_agent_card_custom_override(self):
        """Test custom agent card data overrides defaults."""
        mock_agent = MagicMock()
        mock_agent.name = "Default Name"
        mock_agent.purpose = "Default purpose"
        mock_agent.tools = []
        
        custom_card = {
            "name": "Custom Name",
            "version": "2.0.0",
        }
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard') as mock_card, \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent, agent_card=custom_card)
            
            call_kwargs = mock_card.call_args.kwargs
            assert call_kwargs["name"] == "Custom Name"
            assert call_kwargs["version"] == "2.0.0"


class TestTylerTaskExecution:
    """Test cases for TylerTaskExecution dataclass."""
    
    def test_task_execution_defaults(self):
        """Test TylerTaskExecution has proper defaults."""
        task = TylerTaskExecution(
            task_id="test-123",
            tyler_agent=MagicMock(),
            tyler_thread=MagicMock(),
        )
        
        assert task.status == "running"
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
        assert task.result_messages == []
        assert task.artifacts == []
        assert task.context_id is None
    
    def test_task_execution_with_context(self):
        """Test TylerTaskExecution with context_id (AC-8)."""
        task = TylerTaskExecution(
            task_id="test-123",
            tyler_agent=MagicMock(),
            tyler_thread=MagicMock(),
            context_id="context-abc",
        )
        
        assert task.context_id == "context-abc"


class TestCapabilityExtraction:
    """Test cases for capability extraction from tools."""
    
    def test_extract_file_capability_in_skill_tags(self):
        """Test file operations capability is extracted into skill tags."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = [
            {
                "definition": {
                    "function": {
                        "name": "read_file",
                        "description": "Read a file from disk"
                    }
                }
            }
        ]
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill') as mock_skill, \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Check that AgentSkill was called with file_operations tag
            skill_call_kwargs = mock_skill.call_args.kwargs
            assert "file_operations" in skill_call_kwargs.get("tags", [])
    
    def test_extract_web_capability_in_skill_tags(self):
        """Test web operations capability is extracted into skill tags."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = [
            {
                "definition": {
                    "function": {
                        "name": "web_search",
                        "description": "Search the web"
                    }
                }
            }
        ]
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill') as mock_skill, \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Check that AgentSkill was called with web_operations tag
            skill_call_kwargs = mock_skill.call_args.kwargs
            assert "web_operations" in skill_call_kwargs.get("tags", [])
    
    def test_base_capabilities_always_in_skill_tags(self):
        """Test base capabilities are always included in skill tags."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill') as mock_skill, \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Check that AgentSkill was called with base tags
            skill_call_kwargs = mock_skill.call_args.kwargs
            tags = skill_call_kwargs.get("tags", [])
            assert "task_execution" in tags
            assert "conversation" in tags
            assert "artifacts" in tags


class TestServerMethods:
    """Test cases for A2AServer methods."""
    
    def test_get_agent_card(self):
        """Test get_agent_card returns the agent card."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard') as mock_card, \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            mock_card_instance = MagicMock()
            mock_card.return_value = mock_card_instance
            
            server = A2AServer(tyler_agent=mock_agent)
            
            assert server.get_agent_card() == mock_card_instance
    
    def test_get_active_tasks_empty(self):
        """Test get_active_tasks returns empty list initially."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            assert server.get_active_tasks() == []
    
    def test_get_tasks_by_context(self):
        """Test get_tasks_by_context filters correctly (AC-8)."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Add some tasks to the executor's internal tracking
            server._executor._active_executions["task-1"] = TylerTaskExecution(
                task_id="task-1",
                tyler_agent=mock_agent,
                tyler_thread=MagicMock(),
                context_id="context-a",
            )
            server._executor._active_executions["task-2"] = TylerTaskExecution(
                task_id="task-2",
                tyler_agent=mock_agent,
                tyler_thread=MagicMock(),
                context_id="context-b",
            )
            server._executor._active_executions["task-3"] = TylerTaskExecution(
                task_id="task-3",
                tyler_agent=mock_agent,
                tyler_thread=MagicMock(),
                context_id="context-a",
            )
            
            # Filter by context
            context_a_tasks = server.get_tasks_by_context("context-a")
            
            assert len(context_a_tasks) == 2
            assert all(t["task_id"] in ["task-1", "task-3"] for t in context_a_tasks)


class TestSDKIntegration:
    """Test cases for SDK integration."""
    
    def test_server_uses_sdk_push_infrastructure(self):
        """Test that server initializes SDK push notification infrastructure."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore') as mock_task_store, \
             patch('tyler.a2a.server.InMemoryQueueManager') as mock_queue_manager, \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore') as mock_push_store:
            
            server = A2AServer(tyler_agent=mock_agent)
            
            # Verify SDK stores are initialized
            mock_task_store.assert_called_once()
            mock_queue_manager.assert_called_once()
            mock_push_store.assert_called_once()
    
    def test_server_accepts_push_signing_secret(self):
        """Test that server accepts push signing secret parameter."""
        mock_agent = MagicMock()
        mock_agent.name = "Test"
        mock_agent.purpose = "Test"
        mock_agent.tools = []
        
        with patch('tyler.a2a.server.HAS_A2A', True), \
             patch('tyler.a2a.server.AgentCard'), \
             patch('tyler.a2a.server.AgentCapabilities'), \
             patch('tyler.a2a.server.AgentSkill'), \
             patch('tyler.a2a.server.InMemoryTaskStore'), \
             patch('tyler.a2a.server.InMemoryQueueManager'), \
             patch('tyler.a2a.server.InMemoryPushNotificationConfigStore'):
            
            server = A2AServer(
                tyler_agent=mock_agent,
                push_signing_secret="my-secret-key"
            )
            
            assert server._push_signing_secret == "my-secret-key"


class TestImportError:
    """Test cases for import error handling."""
    
    def test_import_error_without_a2a_sdk(self):
        """Test ImportError is raised when a2a-sdk is not installed."""
        mock_agent = MagicMock()
        
        with patch('tyler.a2a.server.HAS_A2A', False):
            with pytest.raises(ImportError, match="a2a-sdk is required"):
                A2AServer(tyler_agent=mock_agent)
