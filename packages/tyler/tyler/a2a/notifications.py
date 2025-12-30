"""Push notification handler for A2A Protocol.

This module provides webhook-based push notifications for task updates,
implementing the A2A Protocol v0.3.0 specification for asynchronous
task update delivery.

Extends the SDK's BasePushNotificationSender with:
- Retry logic with exponential backoff
- HMAC signing for payload verification
- Custom event type support
"""

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

try:
    from a2a.server.tasks import (
        BasePushNotificationSender,
        PushNotificationConfigStore,
        InMemoryPushNotificationConfigStore,
    )
    from a2a.types import Task as A2ATask, PushNotificationConfig as SDKPushConfig
    HAS_A2A = True
except ImportError:
    HAS_A2A = False
    BasePushNotificationSender = object
    PushNotificationConfigStore = None
    InMemoryPushNotificationConfigStore = None
    A2ATask = None
    SDKPushConfig = None

logger = logging.getLogger(__name__)


# Constants
DEFAULT_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [1, 2, 4]  # Exponential backoff


class TylerPushNotificationSender(BasePushNotificationSender):
    """Enhanced push notification sender for Tyler.
    
    Extends the SDK's BasePushNotificationSender with:
    - Retry logic with exponential backoff
    - HMAC signing for payload verification (if secret configured)
    - Better error handling and logging
    
    Usage:
        config_store = InMemoryPushNotificationConfigStore()
        sender = TylerPushNotificationSender(
            httpx_client=httpx.AsyncClient(),
            config_store=config_store,
            signing_secret="optional-secret-for-hmac"
        )
    """
    
    def __init__(
        self,
        httpx_client: httpx.AsyncClient,
        config_store: "PushNotificationConfigStore",
        signing_secret: Optional[str] = None,
        max_retries: int = MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the Tyler push notification sender.
        
        Args:
            httpx_client: Async HTTP client for sending notifications
            config_store: Store for push notification configurations
            signing_secret: Optional secret for HMAC signing payloads
            max_retries: Maximum number of retry attempts
            timeout: HTTP request timeout in seconds
        """
        if not HAS_A2A:
            raise ImportError("a2a-sdk is required for push notifications")
        
        super().__init__(httpx_client, config_store)
        self._signing_secret = signing_secret
        self._max_retries = max_retries
        self._timeout = timeout
    
    def _sign_payload(self, payload: str) -> Optional[str]:
        """Generate HMAC signature for payload.
        
        Args:
            payload: JSON payload string
            
        Returns:
            HMAC-SHA256 signature as hex string, or None if no secret
        """
        if not self._signing_secret:
            return None
        
        return hmac.new(
            self._signing_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    
    async def _dispatch_notification(
        self, task: "A2ATask", push_info: "SDKPushConfig"
    ) -> bool:
        """Send a notification with retry logic.
        
        Overrides the base implementation to add:
        - Retry with exponential backoff
        - HMAC signing
        - Better error handling
        
        Args:
            task: The task to send
            push_info: Push notification configuration
            
        Returns:
            True if notification was sent successfully
        """
        url = push_info.url
        payload = task.model_dump(mode='json', exclude_none=True)
        payload_json = json.dumps(payload)
        
        headers = {"Content-Type": "application/json"}
        
        # Add token if configured
        if push_info.token:
            headers["X-A2A-Notification-Token"] = push_info.token
        
        # Add HMAC signature if we have a signing secret
        signature = self._sign_payload(payload_json)
        if signature:
            headers["X-A2A-Signature"] = f"sha256={signature}"
        
        # Add task metadata headers
        headers["X-A2A-Task-ID"] = task.id
        if task.context_id:
            headers["X-A2A-Context-ID"] = task.context_id
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self._max_retries):
            try:
                response = await self._client.post(
                    url,
                    content=payload_json,
                    headers=headers,
                    timeout=self._timeout,
                )
                
                if response.is_success:
                    logger.info(
                        f"Push notification sent: task_id={task.id} url={url}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Push notification failed with status {response.status_code}: "
                        f"task_id={task.id} (attempt {attempt + 1}/{self._max_retries})"
                    )
                    last_error = Exception(f"HTTP {response.status_code}")
                    
            except httpx.TimeoutException as e:
                logger.warning(
                    f"Push notification timeout: task_id={task.id} "
                    f"(attempt {attempt + 1}/{self._max_retries})"
                )
                last_error = e
                
            except httpx.RequestError as e:
                logger.warning(
                    f"Push notification request error: {e} "
                    f"(attempt {attempt + 1}/{self._max_retries})"
                )
                last_error = e
            
            # Wait before retry (if not last attempt)
            if attempt < self._max_retries - 1:
                backoff = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                await asyncio.sleep(backoff)
        
        # All retries exhausted
        logger.error(
            f"Push notification failed after {self._max_retries} attempts: "
            f"task_id={task.id} url={url} error={last_error}"
        )
        return False


def create_push_notification_sender(
    signing_secret: Optional[str] = None,
    max_retries: int = MAX_RETRIES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple["TylerPushNotificationSender", "InMemoryPushNotificationConfigStore", httpx.AsyncClient]:
    """Create a push notification sender with its dependencies.
    
    This is a convenience factory function that creates:
    - An HTTP client
    - A config store
    - The push sender
    
    Args:
        signing_secret: Optional secret for HMAC signing
        max_retries: Maximum retry attempts
        timeout: HTTP timeout in seconds
        
    Returns:
        Tuple of (sender, config_store, http_client)
        
    Note:
        The caller is responsible for closing the HTTP client when done.
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for push notifications")
    
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
    )
    
    config_store = InMemoryPushNotificationConfigStore()
    
    sender = TylerPushNotificationSender(
        httpx_client=http_client,
        config_store=config_store,
        signing_secret=signing_secret,
        max_retries=max_retries,
        timeout=timeout,
    )
    
    return sender, config_store, http_client
