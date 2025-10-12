"""Tool registration strategies for different tool types.

This module provides a strategy pattern for registering different types of tools
with the tool runner, making tool registration logic more maintainable and extensible.
"""
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Callable
import types
from tyler.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistrationStrategy(ABC):
    """Abstract base class for tool registration strategies."""
    
    @abstractmethod
    def can_handle(self, tool: Any) -> bool:
        """Check if this strategy can handle the given tool type.
        
        Args:
            tool: Tool to check
            
        Returns:
            True if this strategy handles this tool type
        """
        pass
    
    @abstractmethod
    def register(self, tool: Any, tool_runner) -> List[Dict]:
        """Register tool(s) and return their definitions.
        
        Args:
            tool: Tool to register
            tool_runner: ToolRunner instance to register with
            
        Returns:
            List of tool definition dicts in OpenAI format
            
        Raises:
            ValueError: If tool is invalid or can't be registered
        """
        pass


class StringToolStrategy(ToolRegistrationStrategy):
    """Strategy for handling string tool specifications.
    
    Handles formats like:
    - "web" - Load entire web module
    - "web:download,search" - Load specific tools from web module
    """
    
    def can_handle(self, tool: Any) -> bool:
        """Check if tool is a string."""
        return isinstance(tool, str)
    
    def register(self, tool: str, tool_runner) -> List[Dict]:
        """Register tools from a module string specification.
        
        Args:
            tool: Module name or "module:tool1,tool2" format
            tool_runner: ToolRunner instance
            
        Returns:
            List of tool definitions
        """
        logger.debug(f"Registering string tool specification: {tool}")
        
        # Load built-in tool module
        loaded_tools = tool_runner.load_tool_module(tool)
        
        if not loaded_tools:
            logger.warning(f"No tools loaded from module specification: {tool}")
            return []
        
        logger.debug(f"Loaded {len(loaded_tools)} tools from {tool}")
        return loaded_tools


class ModuleToolStrategy(ToolRegistrationStrategy):
    """Strategy for handling module object tools.
    
    Handles module objects like lye.web, lye.files that have a TOOLS attribute.
    """
    
    def can_handle(self, tool: Any) -> bool:
        """Check if tool is a module with TOOLS attribute."""
        return isinstance(tool, types.ModuleType) and hasattr(tool, 'TOOLS')
    
    def register(self, tool: types.ModuleType, tool_runner) -> List[Dict]:
        """Register tools from a module object.
        
        Args:
            tool: Module object with TOOLS attribute
            tool_runner: ToolRunner instance
            
        Returns:
            List of tool definitions
        """
        module_name = getattr(tool, '__name__', 'unknown')
        logger.debug(f"Registering module tool: {module_name}")
        
        module_tools = getattr(tool, 'TOOLS', [])
        processed_tools = []
        
        for module_tool in module_tools:
            if not isinstance(module_tool, dict):
                logger.warning(f"Invalid tool format in {module_name}, skipping")
                continue
            
            if 'definition' not in module_tool or 'implementation' not in module_tool:
                logger.warning(f"Tool missing definition or implementation in {module_name}, skipping")
                continue
            
            tool_name = module_tool['definition']['function']['name']
            
            # Register the tool
            tool_runner.register_tool(
                name=tool_name,
                implementation=module_tool['implementation'],
                definition=module_tool['definition']['function']
            )
            
            # Register any attributes
            if 'attributes' in module_tool:
                tool_runner.register_tool_attributes(tool_name, module_tool['attributes'])
            
            processed_tools.append(module_tool['definition'])
            logger.debug(f"Registered tool: {tool_name}")
        
        return processed_tools


class DictToolStrategy(ToolRegistrationStrategy):
    """Strategy for handling dict-format tool definitions.
    
    Handles complete tool definitions with 'definition' and 'implementation' keys.
    """
    
    def can_handle(self, tool: Any) -> bool:
        """Check if tool is a dict (regardless of keys - we'll validate in register)."""
        return isinstance(tool, dict)
    
    def register(self, tool: Dict, tool_runner) -> List[Dict]:
        """Register a custom tool from dict format.
        
        Args:
            tool: Tool dict with 'definition' and 'implementation'
            tool_runner: ToolRunner instance
            
        Returns:
            List with single tool definition
            
        Raises:
            ValueError: If dict is missing required keys
        """
        # Validate required keys
        if 'definition' not in tool or 'implementation' not in tool:
            raise ValueError(
                "Custom tools must have 'definition' and 'implementation' keys. "
                "Expected format: {'definition': {'type': 'function', 'function': {...}}, 'implementation': callable}"
            )
        
        tool_name = tool['definition']['function']['name']
        logger.debug(f"Registering dict tool: {tool_name}")
        
        # Register the tool
        tool_runner.register_tool(
            name=tool_name,
            implementation=tool['implementation'],
            definition=tool['definition']['function']
        )
        
        # Register any attributes
        if 'attributes' in tool:
            tool_runner.register_tool_attributes(tool_name, tool['attributes'])
        
        return [tool['definition']]


class CallableToolStrategy(ToolRegistrationStrategy):
    """Strategy for handling direct function references.
    
    Handles callable objects, attempting to find their definitions in Lye's registry.
    """
    
    def can_handle(self, tool: Any) -> bool:
        """Check if tool is a callable."""
        return callable(tool)
    
    def register(self, tool: Callable, tool_runner) -> List[Dict]:
        """Register a callable tool.
        
        Args:
            tool: Callable function
            tool_runner: ToolRunner instance
            
        Returns:
            List with single tool definition
        """
        tool_name = getattr(tool, '__name__', str(tool))
        logger.debug(f"Registering callable tool: {tool_name}")
        
        # Try to get tool definition from Lye's registry
        tool_def = self._get_tool_definition_from_function(tool)
        
        if tool_def:
            # Found in Lye registry
            tool_runner.register_tool(
                name=tool_def['definition']['function']['name'],
                implementation=tool_def['implementation'],
                definition=tool_def['definition']['function']
            )
            return [tool_def['definition']]
        else:
            # Not in Lye registry, create basic definition
            logger.warning(f"Tool '{tool_name}' not found in Lye registry. Creating basic definition.")
            
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": getattr(tool, '__doc__', f"Function {tool_name}"),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            tool_runner.register_tool(
                name=tool_name,
                implementation=tool,
                definition=tool_def['function']
            )
            
            return [tool_def]
    
    def _get_tool_definition_from_function(self, func: Callable) -> Dict:
        """Look up a tool definition from function reference using Lye's registry.
        
        Args:
            func: Function to look up
            
        Returns:
            Tool definition dict or None if not found
        """
        try:
            import lye
            
            # Check each module's tools
            for module_name, tools_list in lye.TOOL_MODULES.items():
                for tool_info in tools_list:
                    if (isinstance(tool_info, dict) and 
                        'implementation' in tool_info and 
                        tool_info['implementation'] == func):
                        return tool_info
            
            # Also check the combined TOOLS list
            for tool_info in lye.TOOLS:
                if (isinstance(tool_info, dict) and 
                    'implementation' in tool_info and 
                    tool_info['implementation'] == func):
                    return tool_info
        
        except ImportError:
            logger.warning("Could not import lye to look up tool definitions")
        except Exception as e:
            logger.warning(f"Error looking up tool definition: {e}")
        
        return None


class ToolRegistrar:
    """Coordinates tool registration using appropriate strategies.
    
    This class manages the registration of various tool types by delegating
    to specific strategy implementations.
    """
    
    def __init__(self):
        """Initialize the registrar with all available strategies."""
        self.strategies = [
            StringToolStrategy(),
            ModuleToolStrategy(),
            DictToolStrategy(),
            CallableToolStrategy()
        ]
    
    def register_tools(self, tools: List[Any], tool_runner) -> List[Dict]:
        """Register a list of tools using appropriate strategies.
        
        Args:
            tools: List of tools in various formats
            tool_runner: ToolRunner instance to register with
            
        Returns:
            List of all registered tool definitions
            
        Raises:
            ValueError: If a tool can't be handled by any strategy
        """
        processed_tools = []
        
        for tool in tools:
            # Find appropriate strategy
            strategy = self._get_strategy_for_tool(tool)
            
            if not strategy:
                raise ValueError(
                    f"Invalid tool type: {type(tool)}. "
                    f"Tool must be a string, module, dict, or callable."
                )
            
            # Register using the strategy
            try:
                tool_defs = strategy.register(tool, tool_runner)
                processed_tools.extend(tool_defs)
            except Exception as e:
                logger.error(f"Failed to register tool: {e}")
                raise
        
        return processed_tools
    
    def _get_strategy_for_tool(self, tool: Any) -> ToolRegistrationStrategy:
        """Find the appropriate strategy for a tool.
        
        Args:
            tool: Tool to find strategy for
            
        Returns:
            Strategy that can handle this tool, or None
        """
        for strategy in self.strategies:
            if strategy.can_handle(tool):
                return strategy
        
        return None

