"""A2A client implementation for Tyler.

This module provides client functionality for connecting to and 
communicating with A2A (Agent-to-Agent) protocol v0.3.0 servers.
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass

try:
    from a2a.client import A2AHttpClient
    from a2a.types import (
        AgentCard,
        Task,
        Message,
        Part,
        TextPart,
        FilePart as A2AFilePart,
        DataPart as A2ADataPart,
        Artifact as A2AArtifact,
    )
    HAS_A2A = True
except ImportError:
    HAS_A2A = False
    # Mock types for when a2a-sdk is not installed
    class A2AHttpClient:
        pass
    class AgentCard:
        pass
    class Task:
        pass
    class Message:
        pass
    class Part:
        pass
    class TextPart:
        pass
    class A2AFilePart:
        pass
    class A2ADataPart:
        pass
    class A2AArtifact:
        pass

from .types import (
    TextPart as TylerTextPart,
    FilePart as TylerFilePart,
    DataPart as TylerDataPart,
    Artifact,
    to_a2a_part,
    from_a2a_part,
    from_a2a_artifact,
    tyler_content_to_parts,
)

# Import SDK's PushNotificationConfig for type hints
try:
    from a2a.types import PushNotificationConfig
except ImportError:
    PushNotificationConfig = None

logger = logging.getLogger(__name__)


@dataclass
class A2AConnection:
    """Information about an A2A agent connection."""
    name: str
    base_url: str
    agent_card: Optional[AgentCard] = None
    client: Optional[A2AHttpClient] = None
    is_connected: bool = False


class A2AClient:
    """Client for connecting to A2A protocol v0.3.0 agents."""
    
    def __init__(self):
        """Initialize the A2A client."""
        if not HAS_A2A:
            raise ImportError(
                "a2a-sdk is required for A2A support. Install with: pip install a2a-sdk"
            )
        
        self.connections: Dict[str, A2AConnection] = {}
        self._tasks: Dict[str, Task] = {}  # Track active tasks by task_id
        self._task_contexts: Dict[str, str] = {}  # task_id -> context_id mapping
    
    async def connect(self, name: str, base_url: str, **kwargs) -> bool:
        """Connect to an A2A agent.
        
        Args:
            name: Unique name for this connection
            base_url: Base URL of the A2A agent
            **kwargs: Additional connection parameters (headers, auth, etc.)
            
        Returns:
            bool: True if connection successful
        """
        if name in self.connections:
            logger.warning(f"Connection '{name}' already exists")
            return False
        
        try:
            # Create HTTP client
            client = A2AHttpClient(base_url=base_url, **kwargs)
            
            # Fetch agent card to validate connection
            agent_card = await client.get_agent_card()
            
            # Store connection info
            connection = A2AConnection(
                name=name,
                base_url=base_url,
                agent_card=agent_card,
                client=client,
                is_connected=True
            )
            self.connections[name] = connection
            
            logger.info(f"Connected to A2A agent '{name}' at {base_url}")
            logger.debug(f"Agent capabilities: {agent_card.capabilities}")
            logger.debug(f"Protocol version: {getattr(agent_card, 'protocol_version', 'unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to A2A agent '{name}' at {base_url}: {e}")
            return False
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from an A2A agent.
        
        Args:
            name: Name of the connection to disconnect
        """
        if name not in self.connections:
            logger.warning(f"Connection '{name}' not found")
            return
        
        connection = self.connections[name]
        
        # Cancel any active tasks for this connection
        tasks_to_cancel = [
            task_id for task_id, task in self._tasks.items()
            if hasattr(task, '_connection_name') and task._connection_name == name
        ]
        
        for task_id in tasks_to_cancel:
            try:
                await self.cancel_task(name, task_id)
            except Exception as e:
                logger.warning(f"Failed to cancel task {task_id}: {e}")
        
        # Close connection
        if connection.client:
            # A2A clients may not have explicit close methods
            pass
        
        # Remove from connections
        del self.connections[name]
        logger.info(f"Disconnected from A2A agent '{name}'")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all A2A agents."""
        connection_names = list(self.connections.keys())
        for name in connection_names:
            await self.disconnect(name)
    
    def is_connected(self, name: str) -> bool:
        """Check if connected to an agent.
        
        Args:
            name: Name of the connection
            
        Returns:
            bool: True if connected
        """
        return name in self.connections and self.connections[name].is_connected
    
    def list_connections(self) -> List[str]:
        """List all active connection names.
        
        Returns:
            List of connection names
        """
        return [name for name, conn in self.connections.items() if conn.is_connected]
    
    def get_agent_card(self, name: str) -> Optional[AgentCard]:
        """Get the agent card for a connection.
        
        Args:
            name: Name of the connection
            
        Returns:
            AgentCard or None if not connected
        """
        if name not in self.connections:
            return None
        return self.connections[name].agent_card
    
    async def create_task(
        self,
        agent_name: str,
        content: Union[str, List[Union[TylerTextPart, TylerFilePart, TylerDataPart]]],
        context_id: Optional[str] = None,
        push_notification_config: Optional[PushNotificationConfig] = None,
        **kwargs
    ) -> Optional[str]:
        """Create a new task with an A2A agent.
        
        Args:
            agent_name: Name of the connected agent
            content: Task content - can be string or list of Part objects
            context_id: Optional context ID for grouping related tasks
            push_notification_config: Optional push notification configuration
            **kwargs: Additional task parameters
            
        Returns:
            Task ID if successful, None otherwise
        """
        if agent_name not in self.connections:
            logger.error(f"Not connected to agent '{agent_name}'")
            return None
        
        connection = self.connections[agent_name]
        
        try:
            # Convert content to A2A Parts
            if isinstance(content, str):
                parts = [TextPart(text=content)]
            else:
                # Convert internal Parts to A2A Parts
                parts = [to_a2a_part(p) for p in content]
            
            # Create message with parts
            message = Message(
                parts=parts,
                **{k: v for k, v in kwargs.items() if k not in ['context_id', 'push_notification_config']}
            )
            
            # Prepare task creation kwargs
            task_kwargs = {}
            if context_id:
                task_kwargs['context_id'] = context_id
            if push_notification_config:
                task_kwargs['push_notification_config'] = {
                    'webhook_url': push_notification_config.webhook_url,
                    'events': push_notification_config.events,
                    'headers': push_notification_config.headers,
                }
            
            # Create task
            task = await connection.client.create_task(message=message, **task_kwargs)
            
            # Store task with connection reference
            task._connection_name = agent_name  # Track which connection this belongs to
            self._tasks[task.task_id] = task
            
            # Track context association
            if context_id:
                self._task_contexts[task.task_id] = context_id
            
            logger.info(f"Created task {task.task_id} with agent '{agent_name}'" +
                       (f" (context: {context_id})" if context_id else ""))
            return task.task_id
            
        except Exception as e:
            logger.error(f"Failed to create task with agent '{agent_name}': {e}")
            return None
    
    async def send_message(
        self,
        agent_name: str,
        task_id: str,
        content: Union[str, List[Union[TylerTextPart, TylerFilePart, TylerDataPart]]],
        **kwargs
    ) -> bool:
        """Send a message to an existing task.
        
        Args:
            agent_name: Name of the connected agent
            task_id: ID of the task
            content: Message content - can be string or list of Part objects
            **kwargs: Additional message parameters
            
        Returns:
            bool: True if message sent successfully
        """
        if agent_name not in self.connections:
            logger.error(f"Not connected to agent '{agent_name}'")
            return False
        
        if task_id not in self._tasks:
            logger.error(f"Task '{task_id}' not found")
            return False
        
        connection = self.connections[agent_name]
        
        try:
            # Convert content to A2A Parts
            if isinstance(content, str):
                parts = [TextPart(text=content)]
            else:
                parts = [to_a2a_part(p) for p in content]
            
            # Create message
            message = Message(
                parts=parts,
                **kwargs
            )
            
            # Send message
            await connection.client.send_message(task_id=task_id, message=message)
            
            logger.debug(f"Sent message to task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to task {task_id}: {e}")
            return False
    
    async def get_task_status(self, agent_name: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task.
        
        Args:
            agent_name: Name of the connected agent
            task_id: ID of the task
            
        Returns:
            Task status information or None
        """
        if agent_name not in self.connections:
            logger.error(f"Not connected to agent '{agent_name}'")
            return None
        
        connection = self.connections[agent_name]
        
        try:
            task_status = await connection.client.get_task_status(task_id=task_id)
            return {
                "task_id": task_id,
                "status": task_status.status,
                "created_at": task_status.created_at,
                "updated_at": task_status.updated_at,
                "context_id": getattr(task_status, 'context_id', self._task_contexts.get(task_id)),
                "metadata": getattr(task_status, 'metadata', {}),
                "has_artifacts": bool(getattr(task_status, 'artifacts', None)),
            }
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return None
    
    async def get_task_artifacts(
        self,
        agent_name: str,
        task_id: str
    ) -> List[Artifact]:
        """Get artifacts produced by a task.
        
        Args:
            agent_name: Name of the connected agent
            task_id: ID of the task
            
        Returns:
            List of Artifact objects
        """
        if agent_name not in self.connections:
            logger.error(f"Not connected to agent '{agent_name}'")
            return []
        
        connection = self.connections[agent_name]
        
        try:
            # Get task status which includes artifacts
            task_status = await connection.client.get_task_status(task_id=task_id)
            
            a2a_artifacts = getattr(task_status, 'artifacts', None)
            if not a2a_artifacts:
                return []
            
            # Convert A2A artifacts to internal format
            return [from_a2a_artifact(a) for a in a2a_artifacts]
            
        except Exception as e:
            logger.error(f"Failed to get artifacts for task {task_id}: {e}")
            return []
    
    async def cancel_task(self, agent_name: str, task_id: str) -> bool:
        """Cancel a task.
        
        Args:
            agent_name: Name of the connected agent
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if task cancelled successfully
        """
        if agent_name not in self.connections:
            logger.error(f"Not connected to agent '{agent_name}'")
            return False
        
        connection = self.connections[agent_name]
        
        try:
            await connection.client.cancel_task(task_id=task_id)
            
            # Remove from tracking
            if task_id in self._tasks:
                del self._tasks[task_id]
            if task_id in self._task_contexts:
                del self._task_contexts[task_id]
            
            logger.info(f"Cancelled task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    async def stream_task_messages(
        self, 
        agent_name: str, 
        task_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream messages from a task.
        
        Args:
            agent_name: Name of the connected agent
            task_id: ID of the task
            
        Yields:
            Message dictionaries as they arrive
        """
        if agent_name not in self.connections:
            logger.error(f"Not connected to agent '{agent_name}'")
            return
        
        connection = self.connections[agent_name]
        
        try:
            async for message in connection.client.stream_task_messages(task_id=task_id):
                # Convert message parts to internal format
                parts = []
                if hasattr(message, 'parts') and message.parts:
                    for part in message.parts:
                        try:
                            parts.append(from_a2a_part(part))
                        except Exception as e:
                            logger.warning(f"Failed to convert part: {e}")
                
                yield {
                    "task_id": task_id,
                    "message_id": getattr(message, 'message_id', None),
                    "role": getattr(message, 'role', 'assistant'),
                    "content": self._extract_message_content(message),
                    "parts": parts,
                    "timestamp": getattr(message, 'timestamp', None),
                    "context_id": self._task_contexts.get(task_id),
                }
                
        except Exception as e:
            logger.error(f"Error streaming messages for task {task_id}: {e}")
    
    def _extract_message_content(self, message: Message) -> str:
        """Extract text content from a message.
        
        Args:
            message: A2A message object
            
        Returns:
            Extracted text content
        """
        if not hasattr(message, 'parts') or not message.parts:
            return str(message)
        
        content_parts = []
        for part in message.parts:
            try:
                internal_part = from_a2a_part(part)
                if isinstance(internal_part, TylerTextPart):
                    content_parts.append(internal_part.text)
                elif isinstance(internal_part, TylerFilePart):
                    content_parts.append(f"[File: {internal_part.name}]")
                elif isinstance(internal_part, TylerDataPart):
                    content_parts.append(f"[Data: {json.dumps(internal_part.data)}]")
            except Exception:
                content_parts.append(str(part))
        
        return "\n".join(content_parts) if content_parts else str(message)
    
    def get_connection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a connection.
        
        Args:
            name: Name of the connection
            
        Returns:
            Connection information dictionary or None
        """
        if name not in self.connections:
            return None
        
        connection = self.connections[name]
        agent_card = connection.agent_card
        
        return {
            "name": connection.name,
            "base_url": connection.base_url,
            "is_connected": connection.is_connected,
            "agent_name": getattr(agent_card, 'name', 'unknown') if agent_card else None,
            "agent_version": getattr(agent_card, 'version', 'unknown') if agent_card else None,
            "protocol_version": getattr(agent_card, 'protocol_version', 'unknown') if agent_card else None,
            "capabilities": getattr(agent_card, 'capabilities', []) if agent_card else [],
            "description": getattr(agent_card, 'description', None) if agent_card else None,
            "push_notifications_supported": self._supports_push_notifications(agent_card),
        }
    
    def _supports_push_notifications(self, agent_card: Optional[AgentCard]) -> bool:
        """Check if an agent supports push notifications.
        
        Args:
            agent_card: The agent's card
            
        Returns:
            True if push notifications are supported
        """
        if not agent_card:
            return False
        
        push_config = getattr(agent_card, 'push_notifications', None)
        if not push_config:
            return False
        
        return getattr(push_config, 'supported', False)
    
    def get_tasks_by_context(self, context_id: str) -> List[str]:
        """Get all task IDs associated with a context.
        
        Args:
            context_id: The context ID to filter by
            
        Returns:
            List of task IDs in the context
        """
        return [
            task_id for task_id, ctx_id in self._task_contexts.items()
            if ctx_id == context_id
        ]
