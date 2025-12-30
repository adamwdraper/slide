"""Tests for A2A push notification sender.

Tests cover:
- Push notification sending with SDK integration
- Retry logic
- HMAC signing
- Integration with SDK's push infrastructure
"""

import pytest
import json
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch


# Mock SDK types for testing
class MockTask:
    """Mock A2A Task for testing."""
    def __init__(self, task_id="test-123", context_id=None):
        self.id = task_id
        self.context_id = context_id
    
    def model_dump(self, mode=None, exclude_none=True):
        return {
            "id": self.id,
            "contextId": self.context_id,
            "status": {"state": "working"},
        }


class MockPushConfig:
    """Mock SDK PushNotificationConfig for testing."""
    def __init__(self, url="https://example.com/webhook", token=None):
        self.url = url
        self.token = token


class MockConfigStore:
    """Mock SDK PushNotificationConfigStore for testing."""
    def __init__(self, configs=None):
        self._configs = configs or {}
    
    async def get_info(self, task_id):
        return self._configs.get(task_id, [])
    
    async def set_info(self, task_id, config):
        if task_id not in self._configs:
            self._configs[task_id] = []
        self._configs[task_id].append(config)
    
    async def delete_info(self, task_id, config_id=None):
        if task_id in self._configs:
            del self._configs[task_id]


class TestTylerPushNotificationSender:
    """Test cases for TylerPushNotificationSender."""
    
    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        client = AsyncMock()
        client.is_closed = False
        return client
    
    @pytest.fixture
    def mock_config_store(self):
        """Create a mock config store."""
        return MockConfigStore()
    
    @pytest.fixture
    def sender(self, mock_http_client, mock_config_store):
        """Create a sender with mocked dependencies."""
        # Import here to handle optional SDK dependency
        try:
            from tyler.a2a.notifications import TylerPushNotificationSender
            return TylerPushNotificationSender(
                httpx_client=mock_http_client,
                config_store=mock_config_store,
                signing_secret="test-secret",
                max_retries=3,
                timeout=5.0,
            )
        except ImportError:
            pytest.skip("a2a-sdk not installed")
    
    @pytest.mark.asyncio
    async def test_send_notification_no_configs(self, sender, mock_http_client):
        """Test that no HTTP call is made when no push configs exist."""
        task = MockTask(task_id="task-no-config")
        
        await sender.send_notification(task)
        
        # No HTTP calls should be made
        mock_http_client.post.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self, sender, mock_http_client, mock_config_store):
        """Test successful notification sending."""
        # Add config for the task
        config = MockPushConfig(url="https://example.com/webhook", token="auth-token")
        await mock_config_store.set_info("task-123", config)
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        
        task = MockTask(task_id="task-123")
        await sender.send_notification(task)
        
        # Should have made exactly one HTTP call
        mock_http_client.post.assert_called_once()
        
        # Check the call args
        call_kwargs = mock_http_client.post.call_args.kwargs
        assert call_kwargs["headers"]["X-A2A-Notification-Token"] == "auth-token"
    
    @pytest.mark.asyncio
    async def test_send_notification_with_hmac_signature(self, sender, mock_http_client, mock_config_store):
        """Test that HMAC signature is included when signing secret is set."""
        config = MockPushConfig(url="https://example.com/webhook")
        await mock_config_store.set_info("task-456", config)
        
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_http_client.post = AsyncMock(return_value=mock_response)
        
        task = MockTask(task_id="task-456")
        await sender.send_notification(task)
        
        # Check signature header was included
        call_kwargs = mock_http_client.post.call_args.kwargs
        assert "X-A2A-Signature" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-A2A-Signature"].startswith("sha256=")
    
    @pytest.mark.asyncio
    async def test_send_notification_retry_on_failure(self, sender, mock_http_client, mock_config_store):
        """Test retry logic on failure."""
        config = MockPushConfig(url="https://example.com/webhook")
        await mock_config_store.set_info("task-retry", config)
        
        # Mock failed response
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_http_client.post = AsyncMock(return_value=mock_response)
        
        task = MockTask(task_id="task-retry")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await sender.send_notification(task)
        
        # Should have retried max_retries times
        assert mock_http_client.post.call_count == 3
    
    def test_sign_payload(self, sender):
        """Test HMAC payload signing."""
        payload = '{"task_id": "123"}'
        
        signature = sender._sign_payload(payload)
        
        # Verify it's a valid HMAC-SHA256 signature
        expected = hmac.new(
            "test-secret".encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        assert signature == expected
    
    def test_sign_payload_no_secret(self, mock_http_client, mock_config_store):
        """Test that sign_payload returns None when no secret is set."""
        try:
            from tyler.a2a.notifications import TylerPushNotificationSender
            sender_no_secret = TylerPushNotificationSender(
                httpx_client=mock_http_client,
                config_store=mock_config_store,
                signing_secret=None,  # No secret
            )
            
            result = sender_no_secret._sign_payload('{"test": "data"}')
            
            assert result is None
        except ImportError:
            pytest.skip("a2a-sdk not installed")
    
    @pytest.mark.asyncio
    async def test_task_id_header_included(self, sender, mock_http_client, mock_config_store):
        """Test that task ID is included in headers."""
        config = MockPushConfig(url="https://example.com/webhook")
        await mock_config_store.set_info("task-header-test", config)
        
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_http_client.post = AsyncMock(return_value=mock_response)
        
        task = MockTask(task_id="task-header-test", context_id="ctx-123")
        await sender.send_notification(task)
        
        call_kwargs = mock_http_client.post.call_args.kwargs
        assert call_kwargs["headers"]["X-A2A-Task-ID"] == "task-header-test"
        assert call_kwargs["headers"]["X-A2A-Context-ID"] == "ctx-123"


class TestCreatePushNotificationSender:
    """Test cases for the factory function."""
    
    def test_create_push_notification_sender(self):
        """Test creating a sender with dependencies."""
        try:
            from tyler.a2a.notifications import create_push_notification_sender
            
            sender, config_store, http_client = create_push_notification_sender(
                signing_secret="my-secret",
                max_retries=5,
                timeout=15.0,
            )
            
            assert sender is not None
            assert config_store is not None
            assert http_client is not None
            
            # Verify sender has the secret set
            assert sender._signing_secret == "my-secret"
            assert sender._max_retries == 5
            
        except ImportError:
            pytest.skip("a2a-sdk not installed")
