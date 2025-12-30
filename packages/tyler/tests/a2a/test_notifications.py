"""Tests for A2A push notification handler.

Tests cover:
- Push notification sending (AC-9, AC-10, AC-11)
- Retry logic
- HMAC signing
- Event creation helpers
"""

import pytest
import asyncio
import json
import hashlib
import hmac
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from tyler.a2a.types import (
    PushNotificationConfig,
    PushNotificationEvent,
    PushEventType,
    Artifact,
    TextPart,
)
from tyler.a2a.notifications import (
    PushNotificationHandler,
    PushNotificationError,
    create_task_created_event,
    create_task_updated_event,
    create_task_completed_event,
    create_task_failed_event,
    create_artifact_event,
)


class TestPushNotificationHandler:
    """Test cases for PushNotificationHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return PushNotificationHandler(timeout=5, max_retries=3)
    
    @pytest.fixture
    def valid_config(self):
        """Create a valid push notification config."""
        with patch('tyler.a2a.types.validate_webhook_url', return_value=True):
            return PushNotificationConfig(
                webhook_url="https://example.com/webhook",
                events=["task.created", "task.completed"],
            )
    
    @pytest.fixture
    def event(self):
        """Create a test event."""
        return PushNotificationEvent.create(
            event_type=PushEventType.TASK_CREATED,
            task_id="test-task-123",
            data={"status": "created"},
        )
    
    @pytest.mark.asyncio
    async def test_send_success(self, handler, valid_config, event):
        """Test successful notification send (AC-9)."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        
        with patch.object(handler, '_get_client') as mock_client:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http
            
            result = await handler.send(valid_config, event)
        
        assert result is True
        mock_http.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_skips_unsubscribed_event(self, handler, valid_config, event):
        """Test that unsubscribed events are skipped."""
        # Event type not in config.events
        event.event_type = "task.updated"
        
        result = await handler.send(valid_config, event)
        
        # Should return True (success) without making HTTP call
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_retries_on_failure(self, handler, valid_config, event):
        """Test retry logic on failure."""
        mock_response_fail = MagicMock()
        mock_response_fail.is_success = False
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Server Error"
        
        with patch.object(handler, '_get_client') as mock_client:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response_fail)
            mock_client.return_value = mock_http
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await handler.send(valid_config, event)
        
        assert result is False
        assert mock_http.post.call_count == 3  # max_retries
    
    @pytest.mark.asyncio
    async def test_send_async_returns_task(self, handler, valid_config, event):
        """Test async send returns a task."""
        mock_response = MagicMock()
        mock_response.is_success = True
        
        with patch.object(handler, '_get_client') as mock_client:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http
            
            task = handler.send_async(valid_config, event)
            
            assert isinstance(task, asyncio.Task)
            await task
    
    def test_sign_payload(self, handler):
        """Test HMAC payload signing."""
        payload = '{"task_id": "123"}'
        secret = "my-secret-key"
        
        signature = handler._sign_payload(payload, secret)
        
        # Verify it's a valid HMAC-SHA256 signature
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        assert signature == expected
    
    @pytest.mark.asyncio
    async def test_send_includes_signature_when_secret_set(self, handler, event):
        """Test that signature is included when secret is configured."""
        with patch('tyler.a2a.types.validate_webhook_url', return_value=True):
            config = PushNotificationConfig(
                webhook_url="https://example.com/webhook",
                events=["task.created"],
                secret="my-secret",
            )
        
        mock_response = MagicMock()
        mock_response.is_success = True
        
        with patch.object(handler, '_get_client') as mock_client:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http
            
            await handler.send(config, event)
            
            # Verify signature header was included
            call_kwargs = mock_http.post.call_args.kwargs
            assert "X-A2A-Signature" in call_kwargs["headers"]
            assert call_kwargs["headers"]["X-A2A-Signature"].startswith("sha256=")
    
    @pytest.mark.asyncio
    async def test_close_handler(self, handler):
        """Test handler cleanup."""
        # Create a mock client
        handler._client = AsyncMock()
        handler._client.is_closed = False
        
        await handler.close()
        
        handler._client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wait_all(self, handler, valid_config, event):
        """Test waiting for all pending notifications."""
        mock_response = MagicMock()
        mock_response.is_success = True
        
        with patch.object(handler, '_get_client') as mock_client:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http
            
            # Send multiple async notifications
            handler.send_async(valid_config, event)
            handler.send_async(valid_config, event)
            
            await handler.wait_all()
            
            assert len(handler._pending_notifications) == 0


class TestEventCreationHelpers:
    """Test cases for event creation helper functions."""
    
    def test_create_task_created_event(self):
        """Test task.created event creation (AC-9)."""
        event = create_task_created_event(
            task_id="task-123",
            context_id="ctx-456",
            metadata={"source": "test"},
        )
        
        assert event.event_type == "task.created"
        assert event.task_id == "task-123"
        assert event.context_id == "ctx-456"
        assert event.data["status"] == "created"
        assert event.data["metadata"]["source"] == "test"
    
    def test_create_task_updated_event(self):
        """Test task.updated event creation (AC-10)."""
        event = create_task_updated_event(
            task_id="task-123",
            status="processing",
            message="Working on it...",
            context_id="ctx-456",
        )
        
        assert event.event_type == "task.updated"
        assert event.task_id == "task-123"
        assert event.data["status"] == "processing"
        assert event.data["message"] == "Working on it..."
    
    def test_create_task_completed_event(self):
        """Test task.completed event creation (AC-11)."""
        artifacts = [
            Artifact.create(name="Result", parts=[TextPart(text="Done")])
        ]
        
        event = create_task_completed_event(
            task_id="task-123",
            result="Task completed successfully",
            artifacts=artifacts,
        )
        
        assert event.event_type == "task.completed"
        assert event.data["status"] == "completed"
        assert event.data["result"] == "Task completed successfully"
        assert len(event.data["artifacts"]) == 1
        assert event.data["artifacts"][0]["name"] == "Result"
    
    def test_create_task_failed_event(self):
        """Test task.failed event creation."""
        event = create_task_failed_event(
            task_id="task-123",
            error="Something went wrong",
        )
        
        assert event.event_type == "task.failed"
        assert event.data["status"] == "failed"
        assert event.data["error"] == "Something went wrong"
    
    def test_create_artifact_event(self):
        """Test artifact event creation."""
        artifact = Artifact.create(
            name="Analysis Result",
            parts=[TextPart(text="Analysis complete")],
        )
        
        event = create_artifact_event(
            task_id="task-123",
            artifact=artifact,
            context_id="ctx-456",
        )
        
        assert event.event_type == "task.artifact"
        assert event.task_id == "task-123"
        assert event.context_id == "ctx-456"
        assert event.data["artifact"]["name"] == "Analysis Result"
        assert event.data["artifact"]["part_count"] == 1


class TestEventSerialization:
    """Test cases for event serialization."""
    
    def test_event_to_dict_minimal(self):
        """Test minimal event serialization."""
        event = PushNotificationEvent.create(
            event_type=PushEventType.TASK_CREATED,
            task_id="task-123",
            data={"status": "created"},
        )
        
        d = event.to_dict()
        
        assert "event_id" in d
        assert "event_type" in d
        assert "task_id" in d
        assert "timestamp" in d
        assert "data" in d
        assert "context_id" not in d  # Not included when None
    
    def test_event_to_dict_with_context(self):
        """Test event serialization with context_id."""
        event = PushNotificationEvent.create(
            event_type=PushEventType.TASK_UPDATED,
            task_id="task-123",
            data={"status": "running"},
            context_id="ctx-789",
        )
        
        d = event.to_dict()
        
        assert d["context_id"] == "ctx-789"
    
    def test_event_json_serializable(self):
        """Test that event dict is JSON serializable."""
        event = create_task_completed_event(
            task_id="task-123",
            result="Done",
        )
        
        d = event.to_dict()
        
        # Should not raise
        json_str = json.dumps(d)
        assert json_str
        
        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["task_id"] == "task-123"

