"""A2A server implementation for Tyler.

This module provides server functionality to expose Tyler agents 
as A2A (Agent-to-Agent) protocol endpoints, allowing other agents
to delegate tasks to Tyler agents.
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid

try:
    from a2a.server import A2AHttpServer
    from a2a.types import AgentCard, Task, Message, Part, TextPart, TaskStatus
    from fastapi import FastAPI
    HAS_A2A = True
except ImportError:
    HAS_A2A = False
    # Mock types for when a2a-sdk is not installed
    class A2AHttpServer:
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
    class TaskStatus:
        pass
    class FastAPI:
        pass

logger = logging.getLogger(__name__)


@dataclass
class TylerTaskExecution:
    """Information about a Tyler task execution."""
    task_id: str
    tyler_agent: Any  # Tyler Agent instance
    tyler_thread: Any  # Tyler Thread instance
    status: str = "running"
    created_at: datetime = None
    updated_at: datetime = None
    result_messages: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.result_messages is None:
            self.result_messages = []


class A2AServer:
    """Server to expose Tyler agents via A2A protocol."""
    
    def __init__(self, tyler_agent, agent_card: Optional[Dict[str, Any]] = None):
        """Initialize the A2A server.
        
        Args:
            tyler_agent: Tyler Agent instance to expose
            agent_card: Optional custom agent card. If None, generates one from Tyler agent
        """
        if not HAS_A2A:
            raise ImportError(
                "a2a-sdk is required for A2A support. Install with: pip install a2a-sdk"
            )
        
        self.tyler_agent = tyler_agent
        self._agent_card = self._create_agent_card(tyler_agent, agent_card)
        self._server: Optional[A2AHttpServer] = None
        self._app: Optional[FastAPI] = None
        self._active_tasks: Dict[str, TylerTaskExecution] = {}
        
    def _create_agent_card(self, tyler_agent, custom_card: Optional[Dict[str, Any]] = None) -> AgentCard:
        """Create an A2A agent card from Tyler agent information.
        
        Args:
            tyler_agent: Tyler Agent instance
            custom_card: Optional custom agent card data
            
        Returns:
            A2A AgentCard instance
        """
        # Extract information from Tyler agent
        agent_name = getattr(tyler_agent, 'name', 'Tyler Agent')
        agent_purpose = getattr(tyler_agent, 'purpose', 'General purpose AI agent')
        tools = getattr(tyler_agent, 'tools', [])
        
        # Default agent card data
        card_data = {
            "name": agent_name,
            "version": "1.0.0",
            "description": agent_purpose,
            "capabilities": self._extract_capabilities(tyler_agent, tools),
            "contact": {
                "name": "Tyler Agent",
                "email": "noreply@tyler.ai"
            },
            "vendor": "Tyler Framework",
            "protocol_version": "1.0"
        }
        
        # Override with custom data if provided
        if custom_card:
            card_data.update(custom_card)
        
        return AgentCard(**card_data)
    
    def _extract_capabilities(self, tyler_agent, tools: List[Any]) -> List[str]:
        """Extract capabilities from Tyler agent and tools.
        
        Args:
            tyler_agent: Tyler Agent instance
            tools: List of Tyler tools
            
        Returns:
            List of capability strings
        """
        capabilities = ["task_execution", "conversation_management"]
        
        # Add tool-based capabilities
        tool_categories = set()
        for tool in tools:
            # Extract tool category from tool definition
            if hasattr(tool, 'get') and 'definition' in tool:
                tool_def = tool['definition']
                if 'function' in tool_def:
                    func_def = tool_def['function']
                    # Extract category from tool name or description
                    name = func_def.get('name', '').lower()
                    desc = func_def.get('description', '').lower()
                    
                    if any(keyword in name or keyword in desc 
                           for keyword in ['file', 'document', 'read', 'write']):
                        tool_categories.add("file_operations")
                    elif any(keyword in name or keyword in desc 
                             for keyword in ['web', 'http', 'url', 'search']):
                        tool_categories.add("web_operations")
                    elif any(keyword in name or keyword in desc 
                             for keyword in ['data', 'analyze', 'process']):
                        tool_categories.add("data_processing")
                    elif any(keyword in name or keyword in desc 
                             for keyword in ['code', 'python', 'execute']):
                        tool_categories.add("code_execution")
        
        capabilities.extend(sorted(tool_categories))
        
        return capabilities
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the A2A server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        try:
            # Create FastAPI app
            self._app = FastAPI(title=f"{self._agent_card.name} A2A Server")
            
            # Create A2A server
            self._server = A2AHttpServer(
                agent_card=self._agent_card,
                app=self._app
            )
            
            # Register handlers
            self._server.on_create_task = self._handle_create_task
            self._server.on_send_message = self._handle_send_message
            self._server.on_get_task_status = self._handle_get_task_status
            self._server.on_cancel_task = self._handle_cancel_task
            
            # Start the server
            import uvicorn
            await uvicorn.run(
                self._app, 
                host=host, 
                port=port,
                log_level="info"
            )
            
        except Exception as e:
            logger.error(f"Failed to start A2A server: {e}")
            raise
    
    async def _handle_create_task(self, message: Message) -> Task:
        """Handle task creation requests.
        
        Args:
            message: Initial task message
            
        Returns:
            Created task
        """
        task_id = str(uuid.uuid4())
        
        try:
            # Extract content from A2A message
            content = self._extract_message_content(message)
            
            # Import Tyler classes here to avoid circular imports
            from ..models.agent import Thread, Message as TylerMessage
            
            # Create Tyler thread and message
            tyler_thread = Thread()
            tyler_message = TylerMessage(role="user", content=content)
            tyler_thread.add_message(tyler_message)
            
            # Create task execution record
            task_execution = TylerTaskExecution(
                task_id=task_id,
                tyler_agent=self.tyler_agent,
                tyler_thread=tyler_thread,
                status="running"
            )
            
            self._active_tasks[task_id] = task_execution
            
            # Start Tyler agent processing in background
            asyncio.create_task(self._execute_tyler_task(task_execution))
            
            # Create A2A task object
            a2a_task = Task(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                created_at=task_execution.created_at,
                updated_at=task_execution.updated_at
            )
            
            logger.info(f"Created A2A task {task_id} for Tyler agent")
            return a2a_task
            
        except Exception as e:
            logger.error(f"Failed to create task {task_id}: {e}")
            # Create error task
            return Task(
                task_id=task_id,
                status=TaskStatus.ERROR,
                error_message=str(e)
            )
    
    async def _execute_tyler_task(self, task_execution: TylerTaskExecution) -> None:
        """Execute a Tyler task in the background.
        
        Args:
            task_execution: Task execution information
        """
        try:
            # Execute Tyler agent
            processed_thread, new_messages = await task_execution.tyler_agent.go(
                task_execution.tyler_thread
            )
            
            # Extract response content
            response_messages = []
            for message in new_messages:
                if hasattr(message, 'content'):
                    response_messages.append(message.content)
                else:
                    response_messages.append(str(message))
            
            # Update task execution
            task_execution.result_messages = response_messages
            task_execution.status = "completed"
            task_execution.updated_at = datetime.utcnow()
            
            logger.info(f"Completed Tyler task {task_execution.task_id}")
            
        except Exception as e:
            logger.error(f"Error executing Tyler task {task_execution.task_id}: {e}")
            task_execution.status = "error"
            task_execution.result_messages = [f"Task execution failed: {str(e)}"]
            task_execution.updated_at = datetime.utcnow()
    
    async def _handle_send_message(self, task_id: str, message: Message) -> None:
        """Handle sending additional messages to a task.
        
        Args:
            task_id: ID of the task
            message: Message to send
        """
        if task_id not in self._active_tasks:
            logger.warning(f"Task {task_id} not found for message sending")
            return
        
        task_execution = self._active_tasks[task_id]
        
        if task_execution.status != "running":
            logger.warning(f"Cannot send message to task {task_id} with status {task_execution.status}")
            return
        
        try:
            # Extract content from A2A message
            content = self._extract_message_content(message)
            
            # Import Tyler Message class
            from ..models.agent import Message as TylerMessage
            
            # Add message to Tyler thread
            tyler_message = TylerMessage(role="user", content=content)
            task_execution.tyler_thread.add_message(tyler_message)
            
            # Re-execute Tyler agent with updated thread
            asyncio.create_task(self._execute_tyler_task(task_execution))
            
        except Exception as e:
            logger.error(f"Failed to send message to task {task_id}: {e}")
    
    async def _handle_get_task_status(self, task_id: str) -> TaskStatus:
        """Handle task status requests.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task status
        """
        if task_id not in self._active_tasks:
            return TaskStatus(
                task_id=task_id,
                status="not_found",
                error_message="Task not found"
            )
        
        task_execution = self._active_tasks[task_id]
        
        # Map Tyler status to A2A status
        a2a_status = "running"
        if task_execution.status == "completed":
            a2a_status = "completed"
        elif task_execution.status == "error":
            a2a_status = "error"
        
        return TaskStatus(
            task_id=task_id,
            status=a2a_status,
            created_at=task_execution.created_at,
            updated_at=task_execution.updated_at,
            result=task_execution.result_messages if task_execution.status == "completed" else None,
            error_message=task_execution.result_messages[0] if task_execution.status == "error" else None
        )
    
    async def _handle_cancel_task(self, task_id: str) -> bool:
        """Handle task cancellation requests.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            True if task was cancelled successfully
        """
        if task_id not in self._active_tasks:
            logger.warning(f"Task {task_id} not found for cancellation")
            return False
        
        task_execution = self._active_tasks[task_id]
        
        # Mark as cancelled
        task_execution.status = "cancelled"
        task_execution.updated_at = datetime.utcnow()
        
        # Remove from active tasks
        del self._active_tasks[task_id]
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
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
        for part in message.parts:
            if hasattr(part, 'text'):
                content_parts.append(part.text)
            else:
                content_parts.append(str(part))
        
        return "\n".join(content_parts) if content_parts else str(message)
    
    async def stop_server(self) -> None:
        """Stop the A2A server and clean up."""
        # Cancel all active tasks
        for task_id in list(self._active_tasks.keys()):
            await self._handle_cancel_task(task_id)
        
        # Stop server (implementation depends on how server is run)
        if self._server:
            # A2A server may not have explicit stop method
            pass
        
        logger.info("A2A server stopped")
    
    def get_agent_card(self) -> AgentCard:
        """Get the agent card for this server.
        
        Returns:
            A2A AgentCard
        """
        return self._agent_card
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get information about active tasks.
        
        Returns:
            List of active task information
        """
        return [
            {
                "task_id": task.task_id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            }
            for task in self._active_tasks.values()
        ]