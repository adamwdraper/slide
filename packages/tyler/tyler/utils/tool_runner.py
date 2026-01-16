import importlib
import inspect
from typing import Dict, Any, List, Optional, Callable, Union, Coroutine, Iterator, KeysView, ItemsView, ValuesView, Mapping, Awaitable
import os
import glob
from pathlib import Path
import weave
import json
import asyncio
from functools import wraps
from dataclasses import dataclass, field
from tyler.utils.logging import get_logger
from tyler.models.execution import ToolContextError
# Direct import
from narrator import Attachment
import base64

# Get configured logger
logger = get_logger(__name__)


# Type alias for progress callbacks (matches MCP SDK's ProgressFnT protocol)
ProgressCallback = Callable[[float, Optional[float], Optional[str]], Awaitable[None]]


@dataclass
class ToolContext:
    """Context passed to tools during execution.
    
    Provides typed fields for tool metadata while supporting dict-style access
    for backward compatibility with existing tools that use `ctx["key"]` syntax.
    
    Attributes:
        tool_name: Name of the tool being executed
        tool_call_id: Unique identifier for the tool call
        deps: User-provided dependencies (database connections, API clients, etc.)
        progress_callback: Optional async callback for reporting progress updates.
            Used by MCP tools to emit progress events during long-running operations.
            Signature: async (progress: float, total: float | None, message: str | None) -> None
    
    Example:
        ```python
        # Tools can access both typed fields and user deps:
        async def my_tool(ctx: ToolContext, query: str) -> str:
            # Typed field access
            print(f"Running tool: {ctx.tool_name}")
            
            # Dict-style access for user deps (backward compatible)
            db = ctx["db"]
            user_id = ctx["user_id"]
            return await db.query(query, user_id)
        ```
    """
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    deps: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[ProgressCallback] = None
    
    # Dict-style access for backward compatibility
    def __getitem__(self, key: str) -> Any:
        """Get a value from deps using dict-style access: ctx['key']"""
        return self.deps[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set a value in deps using dict-style access: ctx['key'] = value"""
        self.deps[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from deps with optional default: ctx.get('key', default)"""
        return self.deps.get(key, default)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in deps: 'key' in ctx"""
        return key in self.deps
    
    def keys(self) -> KeysView[str]:
        """Return deps keys: ctx.keys()"""
        return self.deps.keys()
    
    def items(self) -> ItemsView[str, Any]:
        """Return deps items: ctx.items()"""
        return self.deps.items()
    
    def values(self) -> ValuesView[Any]:
        """Return deps values: ctx.values()"""
        return self.deps.values()
    
    def __iter__(self) -> Iterator[str]:
        """Iterate over deps keys: for key in ctx"""
        return iter(self.deps)
    
    def __len__(self) -> int:
        """Return number of deps: len(ctx)"""
        return len(self.deps)
    
    def __bool__(self) -> bool:
        """ToolContext is always truthy, even when deps is empty.
        
        Without this method, `bool(ctx)` would return False when deps is empty
        because Python falls back to `__len__()`. This caused a bug where
        `if ctx and ctx.progress_callback:` failed when deps={}.
        """
        return True
    
    def update(self, other: Union[Mapping[str, Any], "ToolContext", None] = None, **kwargs: Any) -> None:
        """Update deps with key/value pairs: ctx.update({"key": "value"})"""
        if other is not None:
            if isinstance(other, ToolContext):
                self.deps.update(other.deps)
            else:
                self.deps.update(other)
        self.deps.update(kwargs)

class ToolRunner:
    def __init__(self):
        self.tools = {}  # name -> {implementation, is_async, definition}
        self.tool_attributes = {}  # name -> tool attributes
        self._module_cache = {}  # module_spec -> loaded tools

    def _should_skip_weave_wrap(self, func: Callable) -> bool:
        """Check if function should skip weave.op wrapping.
        
        Returns True if:
        - Function is already wrapped by weave.op (prevents double-wrapping)
        - Function is an MCP tool (MCP SDK provides its own Weave tracing)
        
        Args:
            func: The function to check
            
        Returns:
            True if the function should not be wrapped with weave.op
        """
        # Already wrapped by weave.op
        if hasattr(func, 'resolve_fn') or getattr(func, '_is_weave_op', False):
            return True
        # MCP tools are traced by the MCP SDK itself
        if getattr(func, '_is_mcp_tool', False):
            return True
        return False

    def register_tool(
        self, 
        name: str, 
        implementation: Union[Callable, Coroutine], 
        definition: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> None:
        """
        Register a new tool implementation.
        
        Tools are automatically wrapped with weave.op() for tracing, using the
        tool name as the operation name. This provides clean trace trees where
        each tool call appears as a named span. If the implementation is already
        wrapped with @weave.op(), it won't be double-wrapped.
        
        Args:
            name: The name of the tool
            implementation: The function or coroutine that implements the tool
            definition: Optional OpenAI function definition
            timeout: Optional timeout in seconds for tool execution.
                If the tool takes longer than this, a TimeoutError is raised.
                Must be a positive number if provided.
        
        Raises:
            ValueError: If timeout is not a positive number
        """
        self._validate_timeout(timeout, name)
        
        # Wrap with weave.op for automatic tracing
        # Skip if already wrapped or if it's an MCP tool (MCP SDK traces those)
        if not self._should_skip_weave_wrap(implementation):
            implementation = weave.op(name=name)(implementation)
        
        self.tools[name] = {
            'implementation': implementation,
            'is_async': inspect.iscoroutinefunction(implementation),
            'definition': definition,
            'timeout': timeout
        }
        
    def _validate_timeout(self, timeout: Optional[float], tool_name: str) -> None:
        """Validate that timeout is positive if provided.
        
        Args:
            timeout: The timeout value to validate
            tool_name: Tool name for error messages
            
        Raises:
            ValueError: If timeout is not a positive number
        """
        if timeout is not None and timeout <= 0:
            raise ValueError(f"timeout for tool '{tool_name}' must be a positive number, got {timeout}")
    
    def register_tool_attributes(self, name: str, attributes: Dict[str, Any]) -> None:
        """
        Register optional tool-specific attributes.
        
        Args:
            name: The name of the tool
            attributes: Dictionary of tool-specific attributes
        """
        self.tool_attributes[name] = attributes
        
    def get_tool_attributes(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool-specific attributes if they exist.
        
        Args:
            name: The name of the tool
            
        Returns:
            Optional dictionary of tool attributes. None if no attributes were set.
        """
        return self.tool_attributes.get(name)
        
    def get_tool_definition(self, name: str) -> Optional[Dict[str, Any]]:
        """Get OpenAI function definition for a tool"""
        tool = self.tools.get(name)
        return tool['definition'] if tool else None

    def run_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Executes a synchronous tool by name with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Dictionary of parameters to pass to the tool
            
        Returns:
            The result of the tool execution
            
        Raises:
            ValueError: If tool_name is not found or parameters are invalid
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
            
        tool = self.tools[tool_name]
        if 'implementation' not in tool:
            raise ValueError(f"Implementation for tool '{tool_name}' not found")
            
        if tool.get('is_async', False):
            raise ValueError(f"Tool '{tool_name}' is async and must be run with run_tool_async")
            
        # Execute the tool
        try:
            return tool['implementation'](**parameters)
        except Exception as e:
            raise ValueError(f"Error executing tool '{tool_name}': {str(e)}")

    async def run_tool_async(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        context: Optional[ToolContext] = None
    ) -> Any:
        """
        Executes an async tool by name with the given parameters.
        
        Supports optional context injection for tools that declare a 'ctx' or 'context'
        parameter as their first argument.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Dictionary of parameters to pass to the tool
            context: Optional context dictionary to inject into tools that expect it.
                Tools that have 'ctx' or 'context' as their first parameter will
                receive this context. Tools without such a parameter ignore it.
            
        Returns:
            The result of the tool execution
            
        Raises:
            ValueError: If tool_name is not found or parameters are invalid
            ToolContextError: If tool expects context but none was provided
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
            
        tool = self.tools[tool_name]
        if 'implementation' not in tool:
            raise ValueError(f"Implementation for tool '{tool_name}' not found")
        
        implementation = tool['implementation']
        is_async = tool.get('is_async', False)
        timeout = tool.get('timeout')
        
        # Execute the tool using shared implementation
        try:
            return await self._execute_implementation(
                tool_name=tool_name,
                implementation=implementation,
                arguments=parameters,
                is_async=is_async,
                context=context,
                timeout=timeout
            )
        except ToolContextError:
            raise  # Re-raise context errors as-is
        except TimeoutError:
            raise  # Re-raise timeout errors as-is
        except Exception as e:
            raise ValueError(f"Error executing tool '{tool_name}': {str(e)}")
    
    # Valid parameter names for context injection
    _CONTEXT_PARAM_NAMES = frozenset({'ctx', 'context', '_agent_ctx'})
    
    def _tool_expects_context(self, implementation: Callable) -> bool:
        """Check if a tool implementation expects context injection.
        
        A tool expects context if its first parameter is named 'ctx', 'context',
        or '_agent_ctx' AND the parameter does NOT have a default value (i.e., it's required).
        
        Parameters with default values (like `ctx: ToolContext = None`) are treated
        as optional and will receive context if available, but won't raise an error
        if context is not provided.
        
        Args:
            implementation: The tool function/coroutine
            
        Returns:
            True if the tool REQUIRES context (no default), False otherwise
        """
        try:
            sig = inspect.signature(implementation)
            params = list(sig.parameters.values())
            
            if not params:
                return False
            
            first_param = params[0]
            # Check if named 'ctx', 'context', or '_agent_ctx'
            if first_param.name not in self._CONTEXT_PARAM_NAMES:
                return False
            
            # Check if the parameter has a default value (is optional)
            # If it has a default, context is optional and shouldn't raise error
            if first_param.default is not inspect.Parameter.empty:
                return False
            
            return True
        except (ValueError, TypeError):
            # If we can't inspect the signature, assume no context
            return False

    def _tool_accepts_optional_context(self, implementation: Callable) -> bool:
        """Check if a tool implementation accepts an optional context parameter.
        
        A tool accepts optional context if its first parameter is named 'ctx', 'context',
        or '_agent_ctx' AND the parameter HAS a default value (i.e., it's optional).
        
        These tools will receive context if available, but won't raise an error if not.
        This is used by MCP tools which declare `_agent_ctx: Optional[ToolContext] = None`.
        
        Args:
            implementation: The tool function/coroutine
            
        Returns:
            True if the tool accepts optional context, False otherwise
        """
        try:
            sig = inspect.signature(implementation)
            params = list(sig.parameters.values())
            
            if not params:
                return False
            
            first_param = params[0]
            # Check if named 'ctx', 'context', or '_agent_ctx'
            if first_param.name not in self._CONTEXT_PARAM_NAMES:
                return False
            
            # Check if the parameter has a default value (is optional)
            return first_param.default is not inspect.Parameter.empty
        except (ValueError, TypeError):
            return False

    async def _execute_with_timeout(
        self,
        tool_name: str,
        coro: Coroutine,
        timeout: Optional[float]
    ) -> Any:
        """Execute a coroutine with optional timeout.
        
        Args:
            tool_name: Name of the tool (for error messages)
            coro: The coroutine to execute
            timeout: Timeout in seconds, or None for no timeout
            
        Returns:
            The result of the coroutine
            
        Raises:
            TimeoutError: If execution exceeds the timeout
        """
        if timeout is None:
            return await coro
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool '{tool_name}' timed out after {timeout} seconds")

    async def _execute_implementation(
        self,
        tool_name: str,
        implementation: Callable,
        arguments: Dict[str, Any],
        is_async: bool,
        context: Optional[Union[Dict[str, Any], "ToolContext"]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """Execute a tool implementation with optional context injection and timeout.
        
        This is the shared execution logic used by both run_tool_async and
        execute_tool_call to avoid duplication.
        
        Args:
            tool_name: Name of the tool (for error messages)
            implementation: The tool function/coroutine
            arguments: Arguments to pass to the tool
            is_async: Whether the implementation is async
            context: Optional context to inject (Dict or ToolContext for backward compatibility)
            timeout: Optional timeout in seconds
            
        Returns:
            The result of the tool execution
            
        Raises:
            ToolContextError: If tool expects context but none was provided
            TimeoutError: If execution exceeds the timeout
        
        Note:
            For synchronous tools with timeouts, the thread executing the tool
            will continue running even after TimeoutError is raised. This is a
            known limitation of thread-based timeouts in Python. For truly
            cancellable timeouts, implement tools as async functions.
        """
        requires_context = self._tool_expects_context(implementation)
        accepts_context = self._tool_accepts_optional_context(implementation)
        
        if requires_context:
            if context is None:
                raise ToolContextError(
                    f"Tool '{tool_name}' requires context (has 'ctx' or 'context' parameter) "
                    f"but no tool_context was provided to agent.run()"
                )
            # Inject context as first argument
            if is_async:
                coro = implementation(context, **arguments)
            else:
                coro = asyncio.to_thread(
                    lambda: implementation(context, **arguments)
                )
        elif accepts_context and context is not None:
            # Tool accepts optional context and we have context available
            if is_async:
                coro = implementation(context, **arguments)
            else:
                coro = asyncio.to_thread(
                    lambda: implementation(context, **arguments)
                )
        else:
            # Standard execution without context
            if is_async:
                coro = implementation(**arguments)
            else:
                coro = asyncio.to_thread(implementation, **arguments)
        
        # Execute with optional timeout
        return await self._execute_with_timeout(tool_name, coro, timeout)

    def load_tool_module(self, module_spec: str) -> List[dict]:
        """
        Load tools from a specific module in the tools directory.
        
        Args:
            module_spec: Name of the module to load (e.g., 'web', 'slack')
                      or in format 'module:tool1,tool2' to load specific tools
            
        Returns:
            List of loaded tool definitions
            
        Raises:
            ValueError: If the module doesn't exist or can't be loaded
        """
        try:
            # Check cache first
            if module_spec in self._module_cache:
                logger.debug(f"Loading from cache for module_spec: {module_spec}")
                return self._module_cache[module_spec]

            # Parse module spec to get module name and optional tool filters
            if ":" in module_spec:
                module_name, tool_filters = module_spec.split(":", 1)
                tool_filters = [f.strip() for f in tool_filters.split(",")]
                logger.debug(f"Loading module {module_name} with tool filters: {tool_filters}")
            else:
                module_name = module_spec
                tool_filters = None
                logger.debug(f"Loading module {module_name} with no filters")
            
            # Import the module using the full package path
            module_path = f"lye.{module_name}"
            logger.debug(f"Loading module {module_path}")
            
            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                logger.error(f"Import failed: {str(e)}")
                # Try to import from lye directly
                try:
                    from lye import TOOL_MODULES
                    if module_name in TOOL_MODULES:
                        tools_list = TOOL_MODULES[module_name]
                        loaded_tools = []
                        for tool in tools_list:
                            if not isinstance(tool, dict) or 'definition' not in tool or 'implementation' not in tool:
                                logger.warning(f"Invalid tool format in {module_name}")
                                continue
                                
                            if tool['definition'].get('type') != 'function':
                                logger.warning(f"Tool in {module_name} is not a function type")
                                continue
                                
                            func_name = tool['definition']['function']['name']
                            
                            # Skip this tool if it's not in the filter list
                            if tool_filters and func_name not in tool_filters:
                                logger.debug(f"Skipping tool {func_name} due to filter")
                                continue
                                
                            implementation = tool['implementation']
                            timeout = tool.get('timeout')
                            
                            # Validate timeout if provided
                            self._validate_timeout(timeout, func_name)
                            
                            # Register the tool with its implementation and definition
                            self.tools[func_name] = {
                                'implementation': implementation,
                                'is_async': inspect.iscoroutinefunction(implementation),
                                'definition': tool['definition']['function'],
                                'timeout': timeout
                            }
                            
                            # Register any attributes if present at top level
                            if 'attributes' in tool:
                                self.tool_attributes[func_name] = tool['attributes']
                                
                            # Add only the OpenAI function definition
                            loaded_tools.append({
                                "type": "function",
                                "function": tool['definition']['function']
                            })
                            logger.debug(f"Loaded tool: {func_name}")
                        self._module_cache[module_spec] = loaded_tools # Cache the result
                        return loaded_tools
                    else:
                        error_msg = f"Tool module '{module_name}' not found in TOOL_MODULES"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                except Exception as e2:
                    # This catches any exception in the fallback path, including
                    # ImportError, AttributeError, etc.
                    error_msg = f"Tool module '{module_name}' not found"
                    logger.error(f"{error_msg}: {str(e2)}")
                    raise ValueError(error_msg)
            
            loaded_tools = []
            # Look for TOOLS attribute directly
            if hasattr(module, 'TOOLS'):
                tools_list = getattr(module, 'TOOLS')
                for tool in tools_list:
                    if not isinstance(tool, dict) or 'definition' not in tool or 'implementation' not in tool:
                        logger.warning(f"Invalid tool format")
                        continue
                        
                    if tool['definition'].get('type') != 'function':
                        logger.warning(f"Tool in {module_name} is not a function type")
                        continue
                        
                    func_name = tool['definition']['function']['name']
                    
                    # Skip this tool if it's not in the filter list
                    if tool_filters and func_name not in tool_filters:
                        logger.debug(f"Skipping tool {func_name} due to filter")
                        continue
                        
                    implementation = tool['implementation']
                    timeout = tool.get('timeout')
                    
                    # Validate timeout if provided
                    self._validate_timeout(timeout, func_name)
                    
                    # Register the tool with its implementation and definition
                    self.tools[func_name] = {
                        'implementation': implementation,
                        'is_async': inspect.iscoroutinefunction(implementation),
                        'definition': tool['definition']['function'],
                        'timeout': timeout
                    }
                    
                    # Register any attributes if present at top level
                    if 'attributes' in tool:
                        self.tool_attributes[func_name] = tool['attributes']
                        
                    # Add only the OpenAI function definition
                    loaded_tools.append({
                        "type": "function",
                        "function": tool['definition']['function']
                    })
                    logger.debug(f"Loaded tool: {func_name}")
            else:
                error_msg = f"No TOOLS attribute found in module {module_name}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                    
            self._module_cache[module_spec] = loaded_tools # Cache the result
            return loaded_tools
        except Exception as e:
            # Only use this generic error handler if it's not one of our specific errors
            if "Tool module" not in str(e):
                error_msg = f"Error loading tool module '{module_spec}': {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            # Otherwise re-raise the specific error
            raise

    def get_tool_description(self, tool_name: str) -> Optional[str]:
        """Returns the description of a tool if it exists."""
        if tool_name in self.tools:
            return self.tools[tool_name]['definition'].get('description')
        return None

    def list_tools(self) -> List[str]:
        """Returns a list of all available tool names."""
        return list(self.tools.keys())

    def get_tool_parameters(self, tool_name: str) -> Optional[Dict]:
        """Returns the parameter schema for a tool if it exists."""
        if tool_name in self.tools:
            return self.tools[tool_name]['definition'].get('parameters')
        return None

    def get_tools_for_chat_completion(self) -> List[dict]:
        """Returns tools in the format needed for chat completion."""
        tools = []
        for tool_name in self.list_tools():
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": self.get_tool_description(tool_name),
                    "parameters": self.get_tool_parameters(tool_name)
                }
            }
            tools.append(tool_def)
        return tools

    async def execute_tool_call(
        self, 
        tool_call, 
        context: Optional[ToolContext] = None
    ) -> Any:
        """Execute a tool call and return its raw result.
        
        Args:
            tool_call: The tool call object from the LLM response
            context: Optional context to inject into tools that expect it
            
        Returns:
            The result of the tool execution
        """
        logger.debug(f"Executing tool call: {tool_call}")
        
        # Get tool name and arguments
        tool_name = getattr(tool_call.function, 'name', None)
        logger.debug(f"Tool name: {tool_name}")
        logger.debug(f"Available tools: {list(self.tools.keys())}")
        
        if not tool_name:
            raise ValueError("Tool call missing function name")
            
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}")
            
        tool = self.tools[tool_name]
        logger.debug(f"Found tool implementation: {tool}")
        
        # Parse arguments
        try:
            arguments = json.loads(tool_call.function.arguments)
            logger.debug(f"Parsed arguments: {arguments}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in tool arguments: {e}")
        
        implementation = tool['implementation']
        is_async = tool['is_async']
        timeout = tool.get('timeout')
            
        try:
            result = await self._execute_implementation(
                tool_name=tool_name,
                implementation=implementation,
                arguments=arguments,
                is_async=is_async,
                context=context,
                timeout=timeout
            )
            logger.debug(f"Tool execution result: {result}")
            return result

        except ToolContextError:
            raise  # Re-raise context errors as-is
        except TimeoutError:
            raise  # Re-raise timeout errors as-is
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise

# Create a shared instance
tool_runner = ToolRunner() 