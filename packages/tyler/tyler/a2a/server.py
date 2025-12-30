"""A2A server implementation for Tyler.

This module provides server functionality to expose Tyler agents 
as A2A (Agent-to-Agent) protocol v0.3.0 endpoints, allowing other agents
to delegate tasks to Tyler agents.

Uses the SDK's built-in infrastructure for:
- Task management (InMemoryTaskStore)
- Event queuing (InMemoryQueueManager)
- Push notifications (InMemoryPushNotificationConfigStore + TylerPushNotificationSender)
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

import httpx

try:
    from a2a.server.apps import A2AFastAPIApplication
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue, InMemoryQueueManager
    from a2a.server.tasks import InMemoryTaskStore, InMemoryPushNotificationConfigStore
    from a2a.types import (
        AgentCard,
        AgentCapabilities,
        AgentSkill,
        Task,
        Message,
        Part,
        TextPart,
        FilePart as A2AFilePart,
        DataPart as A2ADataPart,
        TaskStatus,
        TaskState,
        TaskStatusUpdateEvent,
        TaskArtifactUpdateEvent,
        Artifact as A2AArtifact,
        Role,
    )
    from fastapi import FastAPI
    HAS_A2A = True
except ImportError as e:
    HAS_A2A = False
    _import_error = str(e)
    # Mock types for when a2a-sdk is not installed
    class A2AFastAPIApplication:
        pass
    class DefaultRequestHandler:
        pass
    class AgentExecutor:
        pass
    class RequestContext:
        pass
    class EventQueue:
        pass
    class InMemoryQueueManager:
        pass
    class InMemoryTaskStore:
        pass
    class InMemoryPushNotificationConfigStore:
        pass
    class AgentCard:
        pass
    class AgentCapabilities:
        pass
    class AgentSkill:
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
    class TaskStatus:
        pass
    class TaskState:
        pass
    class TaskStatusUpdateEvent:
        pass
    class TaskArtifactUpdateEvent:
        pass
    class A2AArtifact:
        pass
    class Role:
        pass
    class FastAPI:
        pass

from .types import (
    Artifact,
    TextPart as TylerTextPart,
    FilePart as TylerFilePart,
    DataPart as TylerDataPart,
    from_a2a_part,
)
from .notifications import TylerPushNotificationSender
from ..models.execution import EventType

logger = logging.getLogger(__name__)

# Protocol version
A2A_PROTOCOL_VERSION = "0.3.0"


@dataclass
class TylerTaskExecution:
    """Information about a Tyler task execution."""
    task_id: str
    agent: Any  # Tyler Agent instance
    tyler_thread: Any  # Tyler Thread instance
    status: str = "running"
    created_at: datetime = None
    updated_at: datetime = None
    result_messages: List[str] = None
    context_id: Optional[str] = None
    artifacts: List[Artifact] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.result_messages is None:
            self.result_messages = []
        if self.artifacts is None:
            self.artifacts = []


class TylerAgentExecutor(AgentExecutor):
    """A2A AgentExecutor that wraps a Tyler agent.
    
    This executor uses Tyler's streaming internally for all requests.
    The A2A SDK handles delivery based on the client's request type:
    - message/send: SDK aggregates events into a single response
    - message/stream: SDK streams events via SSE in real-time
    
    See: https://a2a-protocol.org/latest/tutorials/python/4-agent-executor/
    """
    
    def __init__(self, agent):
        """Initialize the executor.
        
        Args:
            agent: The Tyler Agent instance to wrap
        """
        self.agent = agent
        self._active_executions: Dict[str, TylerTaskExecution] = {}
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a task using the Tyler agent.
        
        Always uses Tyler's streaming internally. The A2A SDK's
        DefaultRequestHandler handles delivery based on whether the
        client called message/send or message/stream.
        
        Emits TaskArtifactUpdateEvent for each token chunk, allowing
        real-time streaming for message/stream clients while the SDK
        aggregates events for message/send clients.
        
        Args:
            context: The request context with task information
            event_queue: Queue for sending events back
        """
        task_id = context.task_id
        context_id = context.context_id
        message = context.message
        
        try:
            # Extract content from A2A message
            content = self._extract_message_content(message)
            
            # Import Tyler classes
            from ..models.agent import Thread, Message as TylerMessage
            
            # Create Tyler thread and message
            tyler_thread = Thread()
            tyler_message = TylerMessage(role="user", content=content)
            tyler_thread.add_message(tyler_message)
            
            # Track execution
            execution = TylerTaskExecution(
                task_id=task_id,
                agent=self.agent,
                tyler_thread=tyler_thread,
                context_id=context_id,
            )
            self._active_executions[task_id] = execution
            
            # Send working status
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            ))
            
            # Execute with streaming - SDK handles delivery mode
            artifact_id = str(uuid.uuid4())
            content_buffer = []
            chunk_count = 0
            artifact_initialized = False
            
            logger.debug(f"Starting execution for task {task_id}")
            
            async for event in self.agent.stream(tyler_thread):
                if event.type == EventType.LLM_STREAM_CHUNK:
                    # Emit token chunk as artifact update
                    chunk = event.data.get("content_chunk", "")
                    if chunk:
                        content_buffer.append(chunk)
                        chunk_count += 1
                        
                        # First chunk creates the artifact (append=False)
                        # Subsequent chunks append to it (append=True)
                        is_first_chunk = not artifact_initialized
                        if is_first_chunk:
                            artifact_initialized = True
                        
                        await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                            taskId=task_id,
                            contextId=context_id or task_id,
                            artifact=A2AArtifact(
                                artifactId=artifact_id,
                                name=f"Task {task_id[:8]} Result",
                                parts=[Part(root=TextPart(text=chunk))],
                                description="Tyler agent response",
                            ),
                            append=not is_first_chunk,  # False for first, True for rest
                            lastChunk=False,
                        ))
                        
                elif event.type == EventType.EXECUTION_ERROR:
                    # Handle error during execution
                    error_msg = event.data.get("message", "Unknown error")
                    logger.error(f"Execution error for task {task_id}: {error_msg}")
                    
                    await event_queue.enqueue_event(TaskStatusUpdateEvent(
                        taskId=task_id,
                        contextId=context_id or task_id,
                        status=TaskStatus(
                            state=TaskState.failed,
                            message=Message(
                                messageId=str(uuid.uuid4()),
                                role=Role.agent,
                                parts=[Part(root=TextPart(text=f"Task failed: {error_msg}"))],
                                contextId=context_id,
                            ),
                        ),
                        final=True,
                    ))
                    
                    execution.status = "error"
                    # Clean up execution record to prevent memory leak
                    del self._active_executions[task_id]
                    return
                    
                elif event.type == EventType.EXECUTION_COMPLETE:
                    # Execution complete
                    logger.debug(f"Execution complete for task {task_id}: {chunk_count} chunks")
                    break
            
            # Send final artifact event with lastChunk=True
            # Only send if no chunks were streamed (to create an artifact with completion message)
            # or to mark the end of the stream for clients
            if not artifact_initialized:
                # No chunks were sent - create a single artifact with completion message
                await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                    taskId=task_id,
                    contextId=context_id or task_id,
                    artifact=A2AArtifact(
                        artifactId=artifact_id,
                        name=f"Task {task_id[:8]} Result",
                        parts=[Part(root=TextPart(text="Task completed."))],
                        description="Tyler agent response",
                    ),
                    append=False,
                    lastChunk=True,
                ))
            else:
                # Chunks were streamed - send empty final event to signal completion
                # The lastChunk=True flag tells clients the stream has ended
                await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                    taskId=task_id,
                    contextId=context_id or task_id,
                    artifact=A2AArtifact(
                        artifactId=artifact_id,
                        name=f"Task {task_id[:8]} Result",
                        parts=[],  # Empty - content already streamed
                        description="Tyler agent response",
                    ),
                    append=True,
                    lastChunk=True,
                ))
            
            # Send completion status
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            ))
            
            # Update execution record and clean up to prevent memory leak
            execution.status = "completed"
            execution.result_messages = content_buffer
            execution.updated_at = datetime.now(timezone.utc)
            del self._active_executions[task_id]
            
            total_bytes = sum(len(c) for c in content_buffer)
            logger.info(f"Completed task {task_id}: {chunk_count} chunks, {total_bytes} bytes")
            
        except Exception as e:
            import traceback
            logger.error(f"Error executing Tyler task {task_id}: {e}\n{traceback.format_exc()}")
            
            # Send error status
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[Part(root=TextPart(text=f"Task failed: {str(e)}"))],
                        contextId=context_id,
                    ),
                ),
                final=True,
            ))
            
            if task_id in self._active_executions:
                self._active_executions[task_id].status = "error"
                del self._active_executions[task_id]
    
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task.
        
        Args:
            context: The request context
            event_queue: Queue for sending events
        """
        task_id = context.task_id
        
        if task_id in self._active_executions:
            self._active_executions[task_id].status = "cancelled"
            del self._active_executions[task_id]
        
        # Send cancelled status
        await event_queue.enqueue_event(TaskStatusUpdateEvent(
            taskId=task_id,
            contextId=context.context_id or task_id,
            status=TaskStatus(state=TaskState.canceled),
            final=True,
        ))
        
        logger.info(f"Cancelled Tyler task {task_id}")
    
    def _extract_message_content(self, message: Message) -> str:
        """Extract text content from an A2A message.
        
        Args:
            message: A2A message object
            
        Returns:
            Extracted text content
        """
        if not hasattr(message, 'parts') or not message.parts:
            return str(message)
        
        content_parts = []
        file_references = []
        data_references = []
        
        for part in message.parts:
            try:
                internal_part = from_a2a_part(part)
                
                if isinstance(internal_part, TylerTextPart):
                    content_parts.append(internal_part.text)
                elif isinstance(internal_part, TylerFilePart):
                    file_info = f"[File: {internal_part.name} ({internal_part.media_type})]"
                    if internal_part.is_remote:
                        file_info += f" URI: {internal_part.file_with_uri}"
                    file_references.append(file_info)
                elif isinstance(internal_part, TylerDataPart):
                    data_str = json.dumps(internal_part.data, indent=2)
                    data_references.append(f"[Data ({internal_part.media_type}):\n{data_str}\n]")
                    
            except Exception as e:
                logger.warning(f"Error processing message part: {e}")
                content_parts.append(str(part))
        
        all_content = content_parts + file_references + data_references
        return "\n".join(all_content) if all_content else str(message)


class A2AServer:
    """Server to expose Tyler agents via A2A protocol v0.3.0.
    
    Uses the SDK's built-in infrastructure for task and notification management.
    
    Always uses streaming internally. The A2A SDK handles delivery based on
    the client's request type:
    - message/send: SDK aggregates events into a single response
    - message/stream: SDK streams events via SSE in real-time
    
    See: https://a2a-protocol.org/latest/tutorials/python/4-agent-executor/
    """
    
    def __init__(
        self,
        agent,
        agent_card: Optional[Dict[str, Any]] = None,
        authentication: Optional[Dict[str, Any]] = None,
        push_signing_secret: Optional[str] = None,
    ):
        """Initialize the A2A server.
        
        Args:
            agent: Tyler Agent instance to expose
            agent_card: Optional custom agent card data
            authentication: Optional authentication configuration
            push_signing_secret: Optional secret for HMAC signing push notifications
        """
        if not HAS_A2A:
            raise ImportError(
                f"a2a-sdk is required for A2A support. Install with: pip install a2a-sdk\n"
                f"Import error: {_import_error if '_import_error' in dir() else 'unknown'}"
            )
        
        self.agent = agent
        self._authentication = authentication
        self._push_signing_secret = push_signing_secret
        self._agent_card = self._create_agent_card(agent, agent_card)
        
        # Create executor
        self._executor = TylerAgentExecutor(agent)
        
        # SDK infrastructure
        self._task_store = InMemoryTaskStore()
        self._queue_manager = InMemoryQueueManager()
        self._push_config_store = InMemoryPushNotificationConfigStore()
        
        # HTTP client and push sender (will be created on start)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._push_sender: Optional[TylerPushNotificationSender] = None
        self._app: Optional[FastAPI] = None
        
        logger.info(f"A2A server initialized for agent '{getattr(agent, 'name', 'Tyler Agent')}'")
        
    def _create_agent_card(
        self,
        agent,
        custom_card: Optional[Dict[str, Any]] = None
    ) -> AgentCard:
        """Create an A2A agent card from Tyler agent information.
        
        Args:
            agent: Tyler Agent instance
            custom_card: Optional custom agent card data
            
        Returns:
            A2A AgentCard instance
        """
        agent_name = getattr(agent, 'name', 'Tyler Agent')
        agent_purpose = getattr(agent, 'purpose', 'General purpose AI agent')
        tools = getattr(agent, 'tools', [])
        
        # Build capabilities
        skill_tags = self._extract_capabilities(agent, tools)
        
        # Default card data
        card_data = {
            "name": agent_name,
            "url": "http://localhost:8000/",  # Will be updated when server starts
            "version": "1.0.0",
            "description": agent_purpose,
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "capabilities": AgentCapabilities(
                streaming=True,
                pushNotifications=True,
            ),
            "skills": [
                AgentSkill(
                    id="general",
                    name="General Task Execution",
                    description=agent_purpose,
                    tags=skill_tags,
                )
            ],
        }
        
        # Override with custom data
        if custom_card:
            # Handle nested updates carefully
            for key, value in custom_card.items():
                if key == "capabilities" and isinstance(value, dict):
                    card_data["capabilities"] = AgentCapabilities(**value)
                elif key == "skills" and isinstance(value, list):
                    card_data["skills"] = [
                        AgentSkill(**s) if isinstance(s, dict) else s 
                        for s in value
                    ]
                else:
                    card_data[key] = value
        
        return AgentCard(**card_data)
    
    def _extract_capabilities(self, agent, tools: List[Any]) -> List[str]:
        """Extract capability tags from Tyler agent and tools.
        
        Args:
            agent: Tyler Agent instance
            tools: List of Tyler tools
            
        Returns:
            List of capability tag strings
        """
        tags = ["task_execution", "conversation", "artifacts"]
        
        tool_categories = set()
        for tool in tools:
            if hasattr(tool, 'get') and 'definition' in tool:
                tool_def = tool['definition']
                if 'function' in tool_def:
                    func_def = tool_def['function']
                    name = func_def.get('name', '').lower()
                    desc = func_def.get('description', '').lower()
                    
                    if any(kw in name or kw in desc for kw in ['file', 'document', 'read', 'write']):
                        tool_categories.add("file_operations")
                    elif any(kw in name or kw in desc for kw in ['web', 'http', 'url', 'search']):
                        tool_categories.add("web_operations")
                    elif any(kw in name or kw in desc for kw in ['data', 'analyze', 'process']):
                        tool_categories.add("data_processing")
                    elif any(kw in name or kw in desc for kw in ['code', 'python', 'execute']):
                        tool_categories.add("code_execution")
        
        tags.extend(sorted(tool_categories))
        return tags
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the A2A server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        try:
            # Update agent card URL
            self._agent_card = AgentCard(
                **{**self._agent_card.model_dump(), "url": f"http://{host}:{port}/"}
            )
            
            # Create HTTP client for push notifications
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
            )
            
            # Create push notification sender with our enhancements
            self._push_sender = TylerPushNotificationSender(
                httpx_client=self._http_client,
                config_store=self._push_config_store,
                signing_secret=self._push_signing_secret,
            )
            
            # Create request handler with full SDK infrastructure
            handler = DefaultRequestHandler(
                agent_executor=self._executor,
                task_store=self._task_store,
                queue_manager=self._queue_manager,
                push_config_store=self._push_config_store,
                push_sender=self._push_sender,
            )
            
            # Create A2A FastAPI application
            a2a_app = A2AFastAPIApplication(
                agent_card=self._agent_card,
                http_handler=handler,
            )
            
            # Build the FastAPI app
            self._app = a2a_app.build(
                title=f"{self._agent_card.name} A2A Server",
            )
            
            logger.info(f"Starting A2A server for '{self._agent_card.name}' on {host}:{port}")
            logger.info(f"Agent card available at: http://{host}:{port}/.well-known/agent.json")
            logger.info(f"Push notifications: enabled (SDK-managed)")
            
            # Start the server
            import uvicorn
            config = uvicorn.Config(
                self._app,
                host=host,
                port=port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error(f"Failed to start A2A server: {e}")
            raise
    
    async def stop_server(self) -> None:
        """Stop the A2A server and clean up."""
        # Close HTTP client
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        
        logger.info("A2A server stopped")
    
    def get_agent_card(self) -> AgentCard:
        """Get the agent card for this server."""
        return self._agent_card
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get information about active tasks."""
        return [
            {
                "task_id": task.task_id,
                "status": task.status,
                "context_id": task.context_id,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "artifact_count": len(task.artifacts),
            }
            for task in self._executor._active_executions.values()
        ]
    
    def get_tasks_by_context(self, context_id: str) -> List[Dict[str, Any]]:
        """Get all tasks grouped by a context ID."""
        return [
            {
                "task_id": task.task_id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "artifact_count": len(task.artifacts),
            }
            for task in self._executor._active_executions.values()
            if task.context_id == context_id
        ]
