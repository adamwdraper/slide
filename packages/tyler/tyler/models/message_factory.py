"""MessageFactory for creating standardized Tyler messages.

This module provides a centralized factory for creating Message objects with
consistent source metadata, metrics, and formatting throughout the Tyler framework.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
from narrator import Message, Attachment


class MessageFactory:
    """Factory for creating standardized Message objects.
    
    This class centralizes message creation logic to ensure consistent
    source metadata, metrics formatting, and message structure across
    all Tyler agent operations.
    
    Attributes:
        agent_name: Name of the agent creating messages
        model_name: Name of the LLM model being used
    """
    
    def __init__(self, agent_name: str, model_name: str):
        """Initialize the MessageFactory.
        
        Args:
            agent_name: Name of the agent
            model_name: Name of the LLM model
        """
        self.agent_name = agent_name
        self.model_name = model_name
    
    def create_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Create an assistant message with standard source.
        
        Args:
            content: Message content
            tool_calls: Optional list of tool calls in serialized format
            metrics: Optional metrics dictionary (tokens, timing, etc.)
            
        Returns:
            Message instance with assistant role and standard source
        """
        # Build message kwargs, only including optional fields if provided
        message_kwargs = {
            "role": "assistant",
            "content": content,
            "source": self._create_agent_source()
        }
        
        if tool_calls is not None:
            message_kwargs["tool_calls"] = tool_calls
        
        if metrics is not None:
            message_kwargs["metrics"] = metrics
        
        return Message(**message_kwargs)
    
    def create_tool_message(
        self,
        tool_name: str,
        content: str,
        tool_call_id: str,
        attachments: Optional[List[Attachment]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Create a tool result message with standard source.
        
        Args:
            tool_name: Name of the tool that was called
            content: Tool result content
            tool_call_id: ID of the tool call this responds to
            attachments: Optional list of file attachments
            metrics: Optional metrics dictionary (timing, etc.)
            
        Returns:
            Message instance with tool role and standard source
        """
        # Build message kwargs, only including optional fields if provided
        message_kwargs = {
            "role": "tool",
            "name": tool_name,
            "content": content,
            "tool_call_id": tool_call_id,
            "source": self._create_tool_source(tool_name)
        }
        
        if metrics is not None:
            message_kwargs["metrics"] = metrics
        
        message = Message(**message_kwargs)
        
        # Add attachments if provided
        if attachments:
            message.attachments.extend(attachments)
        
        return message
    
    def create_error_message(
        self,
        error_msg: str,
        source: Optional[Dict] = None,
        include_preamble: bool = True
    ) -> Message:
        """Create a standardized error message.
        
        Args:
            error_msg: The error message to display
            source: Optional custom source dict (defaults to agent source)
            include_preamble: Whether to include "I encountered an error:" preamble
            
        Returns:
            Message instance with error content and timing metrics
        """
        timestamp = self._get_timestamp()
        
        if include_preamble:
            content = f"I encountered an error: {error_msg}. Please try again."
        else:
            content = error_msg
        
        return Message(
            role="assistant",
            content=content,
            source=source or self._create_agent_source(),
            metrics={
                "timing": {
                    "started_at": timestamp,
                    "ended_at": timestamp,
                    "latency": 0
                }
            }
        )
    
    def create_system_message(
        self,
        content: str,
        source: Optional[Dict] = None
    ) -> Message:
        """Create a system message.
        
        Args:
            content: System message content
            source: Optional source dict (defaults to agent source)
            
        Returns:
            Message instance with system role
        """
        return Message(
            role="system",
            content=content,
            source=source or self._create_agent_source()
        )
    
    def create_max_iterations_message(self) -> Message:
        """Create a message for when max iterations is reached.
        
        Returns:
            Message indicating iteration limit was hit
        """
        return Message(
            role="assistant",
            content="Maximum tool iteration count reached. Stopping further tool calls.",
            source=self._create_agent_source()
        )
    
    def _create_agent_source(self) -> Dict:
        """Create standardized source dict for agent messages.
        
        Returns:
            Source dictionary with agent identification and model info
        """
        return {
            "id": self.agent_name,
            "name": self.agent_name,
            "type": "agent",
            "attributes": {
                "model": self.model_name
            }
        }
    
    def _create_tool_source(self, tool_name: str) -> Dict:
        """Create standardized source dict for tool messages.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Source dictionary with tool identification
        """
        return {
            "id": tool_name,
            "name": tool_name,
            "type": "tool",
            "attributes": {
                "agent_id": self.agent_name
            }
        }
    
    def _get_timestamp(self) -> str:
        """Get current ISO timestamp.
        
        Returns:
            ISO-formatted timestamp string
        """
        return datetime.now(UTC).isoformat()
    
    def create_tool_timing_metrics(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create standardized timing metrics for tool execution.
        
        Args:
            start_time: Tool execution start time
            end_time: Tool execution end time (defaults to now)
            
        Returns:
            Metrics dictionary with timing information
        """
        if end_time is None:
            end_time = datetime.now(UTC)
        
        latency_ms = (end_time - start_time).total_seconds() * 1000
        
        return {
            "timing": {
                "started_at": start_time.isoformat(),
                "ended_at": end_time.isoformat(),
                "latency": latency_ms
            }
        }

