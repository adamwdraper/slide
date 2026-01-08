"""Agent tool execution mixin."""
import logging
from typing import Any, Dict, List, Optional, Tuple

from narrator import Message, Attachment

from tyler.utils.tool_runner import tool_runner, ToolContext


class AgentToolsMixin:
    """Mixin providing tool execution methods for Agent.
    
    This mixin expects the following attributes on the class:
    - name: str
    - _tool_attributes_cache: Dict[str, Optional[Dict[str, Any]]]
    - _tool_context: Optional[Dict[str, Any]]
    
    And the following methods from AgentHelpersMixin:
    - _get_timestamp() -> str
    - _create_tool_source(tool_name: str) -> Dict
    - _get_tool_attributes(tool_name: str) -> Optional[Dict[str, Any]]
    """
    
    def _get_tool_attributes(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool attributes with caching."""
        if tool_name not in self._tool_attributes_cache:
            self._tool_attributes_cache[tool_name] = tool_runner.get_tool_attributes(tool_name)
        return self._tool_attributes_cache[tool_name]

    def _normalize_tool_call(self, tool_call):
        """Ensure tool_call has a consistent format for tool_runner without modifying the original."""
        if isinstance(tool_call, dict):
            # Create a minimal wrapper that provides the expected interface
            class ToolCallWrapper:
                def __init__(self, tool_dict):
                    self.id = tool_dict.get('id')
                    self.type = tool_dict.get('type', 'function')
                    self.function = type('obj', (object,), {
                        'name': tool_dict.get('function', {}).get('name', ''),
                        'arguments': tool_dict.get('function', {}).get('arguments', '{}') or '{}'
                    })
            return ToolCallWrapper(tool_call)
        else:
            # For objects, ensure arguments is not empty
            if not tool_call.function.arguments or tool_call.function.arguments.strip() == "":
                # Create a copy to avoid modifying the original
                class ToolCallCopy:
                    def __init__(self, original):
                        self.id = original.id
                        self.type = getattr(original, 'type', 'function')
                        self.function = type('obj', (object,), {
                            'name': original.function.name,
                            'arguments': '{}'
                        })
                return ToolCallCopy(tool_call)
            return tool_call

    async def _handle_tool_execution(self, tool_call, progress_callback=None) -> dict:
        """
        Execute a single tool call and format the result message
        
        Args:
            tool_call: The tool call object from the model response
            progress_callback: Optional async callback for progress updates.
                Signature: async (progress: float, total: float | None, message: str | None) -> None
                Used by MCP tools to emit progress notifications during long-running operations.
        
        Returns:
            dict: Formatted tool result message
        """
        normalized_tool_call = self._normalize_tool_call(tool_call)
        
        # Build rich ToolContext with metadata if user provided tool_context
        if self._tool_context is not None:
            # Extract tool_name and tool_call_id from the normalized tool_call
            tool_name = getattr(normalized_tool_call.function, 'name', None)
            tool_call_id = getattr(normalized_tool_call, 'id', None)
            
            # Shallow copy deps to prevent direct mutations from affecting other tool calls.
            # Note: Nested mutable objects (dicts within dicts) are still shared references.
            # We intentionally avoid deepcopy as it would fail for non-picklable objects
            # like database connections and API clients which are common deps.
            deps_copy = dict(self._tool_context)
            
            # Handle progress callbacks - combine if both parameter and tool_context have one
            # This allows streaming mode to emit TOOL_PROGRESS events while also calling
            # a user's custom callback
            user_callback = deps_copy.pop('progress_callback', None)
            
            if progress_callback is not None and user_callback is not None:
                # Both exist - create composite that calls both (best-effort)
                async def composite_callback(progress, total, message):
                    # Call both callbacks, continuing even if one fails
                    # Progress callbacks are informational, so we don't want
                    # one failure to prevent the other from being called
                    try:
                        await progress_callback(progress, total, message)
                    except Exception:
                        pass  # Progress callback failure shouldn't stop execution
                    try:
                        await user_callback(progress, total, message)
                    except Exception:
                        pass  # Progress callback failure shouldn't stop execution
                effective_progress_callback = composite_callback
            elif progress_callback is not None:
                effective_progress_callback = progress_callback
            else:
                effective_progress_callback = user_callback
            
            rich_context = ToolContext(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                deps=deps_copy,
                progress_callback=effective_progress_callback,
            )
        else:
            # Create minimal context just for progress callback if provided
            if progress_callback is not None:
                tool_name = getattr(normalized_tool_call.function, 'name', None)
                tool_call_id = getattr(normalized_tool_call, 'id', None)
                rich_context = ToolContext(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    progress_callback=progress_callback,
                )
            else:
                rich_context = None
        
        return await tool_runner.execute_tool_call(normalized_tool_call, context=rich_context)

    def _process_tool_result(self, result: Any, tool_call: Any, tool_name: str) -> Tuple[Message, bool]:
        """
        Process a tool execution result and create a message.
        
        Returns:
            Tuple[Message, bool]: The tool message and whether to break iteration
        """
        timestamp = self._get_timestamp()
        
        # Handle exceptions in tool execution
        if isinstance(result, Exception):
            error_msg = f"Tool execution failed: {str(result)}"
            tool_message = Message(
                role="tool",
                name=tool_name,
                content=error_msg,
                tool_call_id=tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                source=self._create_tool_source(tool_name),
                metrics={
                    "timing": {
                        "started_at": timestamp,
                        "ended_at": timestamp,
                        "latency": 0
                    }
                }
            )
            return tool_message, False
        
        # Process successful result
        content = None
        files = []
        
        if isinstance(result, tuple):
            # Handle tuple return (content, files)
            content = str(result[0])
            if len(result) >= 2:
                files = result[1]
        else:
            # Handle any content type - just convert to string
            content = str(result)
            
        # Create tool message
        tool_message = Message(
            role="tool",
            name=tool_name,
            content=content,
            tool_call_id=tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
            source=self._create_tool_source(tool_name),
            metrics={
                "timing": {
                    "started_at": timestamp,
                    "ended_at": timestamp,
                    "latency": 0
                }
            }
        )
        
        # Add any files as attachments
        if files:
            logging.getLogger(__name__).debug(f"Processing {len(files)} files from tool result")
            for file_info in files:
                logging.getLogger(__name__).debug(f"Creating attachment for {file_info.get('filename')} with mime type {file_info.get('mime_type')}")
                attachment = Attachment(
                    filename=file_info["filename"],
                    content=file_info["content"],
                    mime_type=file_info["mime_type"]
                )
                tool_message.attachments.append(attachment)
        
        # Check if tool wants to break iteration
        tool_attributes = self._get_tool_attributes(tool_name)
        should_break = tool_attributes and tool_attributes.get('type') == 'interrupt'
        
        return tool_message, should_break
