"""Agent helper methods mixin for message and source creation."""
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from narrator import Message, Attachment


class AgentHelpersMixin:
    """Mixin providing helper methods for Agent message and source creation.
    
    This mixin expects the following attributes on the class:
    - name: str
    - model_name: str  
    - message_factory: MessageFactory
    """
    
    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _serialize_tool_calls(self, tool_calls: Optional[List[Any]]) -> Optional[List[Dict]]:
        """Serialize tool calls to a list of dictionaries.

        Args:
            tool_calls: List of tool calls to serialize, or None

        Returns:
            Optional[List[Dict]]: Serialized tool calls, or None if input is None
        """
        if tool_calls is None:
            return None
            
        serialized = []
        for tool_call in tool_calls:
            if isinstance(tool_call, dict):
                # Ensure ID is present
                if not tool_call.get('id'):
                    continue
                serialized.append(tool_call)
            else:
                # Ensure ID is present
                if not hasattr(tool_call, 'id') or not tool_call.id:
                    continue
                serialized.append({
                    "id": str(tool_call.id),
                    "type": str(tool_call.type),
                    "function": {
                        "name": str(tool_call.function.name),
                        "arguments": str(tool_call.function.arguments)
                    }
                })
        return serialized if serialized else None

    def _create_tool_source(self, tool_name: str) -> Dict:
        """Creates a standardized source entity dict for tool messages."""
        return {
            "id": tool_name,
            "name": tool_name,
            "type": "tool",
            "attributes": {
                "agent_id": self.name
            }
        }

    def _create_assistant_source(self, include_version: bool = True) -> Dict:
        """Creates a standardized source entity dict for assistant messages."""
        attributes = {
            "model": self.model_name
        }
        
        return {
            "id": self.name,
            "name": self.name,
            "type": "agent",
            "attributes": attributes
        } 

    def _create_error_message(self, error_msg: str, source: Optional[Dict] = None) -> Message:
        """Create a standardized error message."""
        return self.message_factory.create_error_message(error_msg, source=source)
