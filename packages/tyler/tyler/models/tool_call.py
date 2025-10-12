"""ToolCall value object for normalizing tool call formats.

This module provides a unified representation for tool calls, handling both
dict and object formats from LLM responses. It eliminates format inconsistency
and provides a clean interface for tool execution.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
import json
from tyler.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolCall:
    """Unified representation of a tool call.
    
    This class normalizes the different formats that tool calls can arrive in
    from LLM responses (dict format vs object format) into a consistent internal
    representation.
    
    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to call
        arguments: Dictionary of arguments to pass to the tool
    """
    id: str
    name: str
    arguments: Dict[str, Any]
    
    @classmethod
    def from_llm_response(cls, tool_call: Union[Dict, Any]) -> 'ToolCall':
        """Create a ToolCall from an LLM response (dict or object format).
        
        Handles both:
        - Dict format: {'id': '...', 'function': {'name': '...', 'arguments': '{...}'}}
        - Object format: object with id, function.name, function.arguments attributes
        
        Args:
            tool_call: Tool call from LLM response (dict or object)
            
        Returns:
            ToolCall instance with normalized data
            
        Raises:
            ValueError: If tool_call format is invalid or missing required fields
        """
        if isinstance(tool_call, dict):
            return cls._from_dict(tool_call)
        else:
            return cls._from_object(tool_call)
    
    @classmethod
    def _from_dict(cls, tool_call: Dict) -> 'ToolCall':
        """Create ToolCall from dict format."""
        tool_id = tool_call.get('id')
        if not tool_id:
            raise ValueError("Tool call dict missing 'id' field")
        
        function = tool_call.get('function', {})
        if not function:
            raise ValueError("Tool call dict missing 'function' field")
        
        name = function.get('name', '')
        if not name:
            raise ValueError("Tool call dict missing 'function.name' field")
        
        # Parse arguments using shared helper
        args_str = function.get('arguments', '{}') or '{}'
        arguments = cls._parse_arguments(args_str)
        
        return cls(id=tool_id, name=name, arguments=arguments)
    
    @classmethod
    def _from_object(cls, tool_call: Any) -> 'ToolCall':
        """Create ToolCall from object format."""
        tool_id = getattr(tool_call, 'id', None)
        if not tool_id:
            raise ValueError("Tool call object missing 'id' attribute")
        
        if not hasattr(tool_call, 'function'):
            raise ValueError("Tool call object missing 'function' attribute")
        
        function = tool_call.function
        name = getattr(function, 'name', '')
        if not name:
            raise ValueError("Tool call object missing 'function.name' attribute")
        
        # Parse arguments using shared helper
        args_str = getattr(function, 'arguments', '{}') or '{}'
        arguments = cls._parse_arguments(args_str)
        
        return cls(id=tool_id, name=name, arguments=arguments)
    
    @classmethod
    def _parse_arguments(cls, args_str: Any) -> Dict[str, Any]:
        """Parse tool call arguments from various formats.
        
        Handles JSON strings, dicts, and edge cases (None, empty string).
        
        Args:
            args_str: Arguments as JSON string, dict, or other type
            
        Returns:
            Parsed arguments as dict, or empty dict if parsing fails
        """
        try:
            if isinstance(args_str, str):
                return json.loads(args_str)
            elif isinstance(args_str, dict):
                return args_str
            else:
                logger.warning(f"Tool call arguments must be a JSON string or dict, got {type(args_str).__name__}")
                return {}
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse tool arguments, using empty dict: {e}")
            return {}
    
    def to_message_format(self) -> Dict[str, Any]:
        """Convert to format suitable for Message.tool_calls field.
        
        Returns dict format for storage and serialization.
        
        Returns:
            Dict in standard tool call format
        """
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments)
            }
        }
    
    def to_execution_format(self) -> 'ToolCall':
        """Convert to format suitable for tool execution.
        
        For tool_runner compatibility, we return self since ToolCall
        provides the interface needed for execution.
        
        Returns:
            Self (ToolCall already has the right interface)
        """
        return self
    
    def get_arguments_json(self) -> str:
        """Get arguments as JSON string.
        
        Useful for tool_runner which expects JSON string format.
        
        Returns:
            JSON string representation of arguments
        """
        return json.dumps(self.arguments)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        args_preview = str(self.arguments)[:50]
        if len(str(self.arguments)) > 50:
            args_preview += "..."
        return f"ToolCall(id={self.id!r}, name={self.name!r}, arguments={args_preview})"


def normalize_tool_calls(tool_calls: Optional[list]) -> Optional[list]:
    """Normalize a list of tool calls to ToolCall instances.
    
    Convenience function for normalizing multiple tool calls at once.
    
    Args:
        tool_calls: List of tool calls in any format, or None
        
    Returns:
        List of ToolCall instances, or None if input is None
        
    Raises:
        ValueError: If any tool call is invalid
    """
    if tool_calls is None:
        return None
    
    normalized = []
    for tool_call in tool_calls:
        try:
            normalized.append(ToolCall.from_llm_response(tool_call))
        except ValueError as e:
            logger.error(f"Failed to normalize tool call: {e}")
            # Skip invalid tool calls rather than failing the whole batch
            continue
    
    return normalized if normalized else None


def serialize_tool_calls(tool_calls: Optional[list]) -> Optional[list]:
    """Serialize a list of ToolCall instances to message format.
    
    Convenience function for serializing multiple ToolCall instances.
    
    Args:
        tool_calls: List of ToolCall instances, or None
        
    Returns:
        List of dicts in message format, or None if input is None
    """
    if tool_calls is None:
        return None
    
    return [tc.to_message_format() for tc in tool_calls if isinstance(tc, ToolCall)]

