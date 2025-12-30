"""Push notification handler for A2A Protocol.

This module provides webhook-based push notifications for task updates,
implementing the A2A Protocol v0.3.0 specification for asynchronous
task update delivery.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .types import (
    PushNotificationConfig,
    PushNotificationEvent,
    PushEventType,
    Artifact,
)

logger = logging.getLogger(__name__)


# Constants
DEFAULT_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [1, 2, 4]  # Exponential backoff


class PushNotificationError(Exception):
    """Error during push notification delivery."""
    pass


class PushNotificationHandler:
    """Handles sending push notifications to webhook endpoints.
    
    This handler implements:
    - Async notification delivery
    - Retry logic with exponential backoff
    - HMAC signing for payload verification
    - Fire-and-forget pattern (doesn't block task processing)
    """
    
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ):
        """Initialize the push notification handler.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._pending_notifications: List[asyncio.Task] = []
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client and cancel pending notifications."""
        # Cancel pending notifications
        for task in self._pending_notifications:
            if not task.done():
                task.cancel()
        self._pending_notifications.clear()
        
        # Close client
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for payload.
        
        Args:
            payload: JSON payload string
            secret: Secret key for signing
            
        Returns:
            HMAC-SHA256 signature as hex string
        """
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    
    async def _send_notification(
        self,
        config: PushNotificationConfig,
        event: PushNotificationEvent,
    ) -> bool:
        """Send a single notification with retry logic.
        
        Args:
            config: Push notification configuration
            event: Event to send
            
        Returns:
            True if notification was delivered successfully
        """
        payload = json.dumps(event.to_dict())
        headers = dict(config.headers or {})
        headers["Content-Type"] = "application/json"
        
        # Add HMAC signature if secret is configured
        if config.secret:
            signature = self._sign_payload(payload, config.secret)
            headers["X-A2A-Signature"] = f"sha256={signature}"
        
        # Add event metadata headers
        headers["X-A2A-Event-Type"] = event.event_type
        headers["X-A2A-Event-ID"] = event.event_id
        
        client = await self._get_client()
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    config.webhook_url,
                    content=payload,
                    headers=headers,
                )
                
                if response.is_success:
                    logger.info(
                        f"Push notification sent successfully: "
                        f"event={event.event_type} task={event.task_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Push notification failed with status {response.status_code}: "
                        f"event={event.event_type} task={event.task_id} "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    last_error = PushNotificationError(
                        f"HTTP {response.status_code}: {response.text}"
                    )
                    
            except httpx.TimeoutException as e:
                logger.warning(
                    f"Push notification timeout: event={event.event_type} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                last_error = e
                
            except httpx.RequestError as e:
                logger.warning(
                    f"Push notification request error: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                last_error = e
            
            # Wait before retry (if not last attempt)
            if attempt < self.max_retries - 1:
                backoff = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                await asyncio.sleep(backoff)
        
        # All retries exhausted
        logger.error(
            f"Push notification failed after {self.max_retries} attempts: "
            f"event={event.event_type} task={event.task_id} error={last_error}"
        )
        return False
    
    async def send(
        self,
        config: PushNotificationConfig,
        event: PushNotificationEvent,
    ) -> bool:
        """Send a push notification.
        
        Args:
            config: Push notification configuration
            event: Event to send
            
        Returns:
            True if notification was delivered successfully
        """
        # Check if this event type is subscribed
        if event.event_type not in config.events:
            logger.debug(
                f"Skipping notification for unsubscribed event type: {event.event_type}"
            )
            return True
        
        return await self._send_notification(config, event)
    
    def send_async(
        self,
        config: PushNotificationConfig,
        event: PushNotificationEvent,
    ) -> asyncio.Task:
        """Send a push notification asynchronously (fire-and-forget).
        
        This method returns immediately and the notification is sent in the background.
        Use this for non-blocking notification delivery.
        
        Args:
            config: Push notification configuration
            event: Event to send
            
        Returns:
            asyncio.Task that can be awaited or ignored
        """
        task = asyncio.create_task(self.send(config, event))
        self._pending_notifications.append(task)
        
        # Clean up completed tasks
        self._pending_notifications = [
            t for t in self._pending_notifications if not t.done()
        ]
        
        return task
    
    async def wait_all(self) -> None:
        """Wait for all pending notifications to complete."""
        if self._pending_notifications:
            await asyncio.gather(*self._pending_notifications, return_exceptions=True)
            self._pending_notifications.clear()


# Convenience functions for creating events

def create_task_created_event(
    task_id: str,
    context_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> PushNotificationEvent:
    """Create a task.created event.
    
    Args:
        task_id: ID of the created task
        context_id: Optional context ID
        metadata: Optional additional metadata
        
    Returns:
        PushNotificationEvent for task creation
    """
    return PushNotificationEvent.create(
        event_type=PushEventType.TASK_CREATED,
        task_id=task_id,
        data={
            "status": "created",
            "metadata": metadata or {},
        },
        context_id=context_id,
    )


def create_task_updated_event(
    task_id: str,
    status: str,
    message: Optional[str] = None,
    context_id: Optional[str] = None,
) -> PushNotificationEvent:
    """Create a task.updated event.
    
    Args:
        task_id: ID of the task
        status: Current task status
        message: Optional status message
        context_id: Optional context ID
        
    Returns:
        PushNotificationEvent for task update
    """
    data: Dict[str, Any] = {"status": status}
    if message:
        data["message"] = message
    
    return PushNotificationEvent.create(
        event_type=PushEventType.TASK_UPDATED,
        task_id=task_id,
        data=data,
        context_id=context_id,
    )


def create_task_completed_event(
    task_id: str,
    result: Optional[str] = None,
    artifacts: Optional[List[Artifact]] = None,
    context_id: Optional[str] = None,
) -> PushNotificationEvent:
    """Create a task.completed event.
    
    Args:
        task_id: ID of the completed task
        result: Optional result summary
        artifacts: Optional list of produced artifacts
        context_id: Optional context ID
        
    Returns:
        PushNotificationEvent for task completion
    """
    data: Dict[str, Any] = {"status": "completed"}
    if result:
        data["result"] = result
    if artifacts:
        data["artifacts"] = [
            {
                "artifact_id": a.artifact_id,
                "name": a.name,
                "created_at": a.created_at.isoformat(),
            }
            for a in artifacts
        ]
    
    return PushNotificationEvent.create(
        event_type=PushEventType.TASK_COMPLETED,
        task_id=task_id,
        data=data,
        context_id=context_id,
    )


def create_task_failed_event(
    task_id: str,
    error: str,
    context_id: Optional[str] = None,
) -> PushNotificationEvent:
    """Create a task.failed event.
    
    Args:
        task_id: ID of the failed task
        error: Error message
        context_id: Optional context ID
        
    Returns:
        PushNotificationEvent for task failure
    """
    return PushNotificationEvent.create(
        event_type=PushEventType.TASK_FAILED,
        task_id=task_id,
        data={
            "status": "failed",
            "error": error,
        },
        context_id=context_id,
    )


def create_artifact_event(
    task_id: str,
    artifact: Artifact,
    context_id: Optional[str] = None,
) -> PushNotificationEvent:
    """Create a task.artifact event.
    
    Args:
        task_id: ID of the task
        artifact: The produced artifact
        context_id: Optional context ID
        
    Returns:
        PushNotificationEvent for artifact production
    """
    return PushNotificationEvent.create(
        event_type=PushEventType.ARTIFACT_PRODUCED,
        task_id=task_id,
        data={
            "artifact": {
                "artifact_id": artifact.artifact_id,
                "name": artifact.name,
                "created_at": artifact.created_at.isoformat(),
                "part_count": len(artifact.parts),
            }
        },
        context_id=context_id,
    )

