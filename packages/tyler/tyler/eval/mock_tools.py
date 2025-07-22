"""Mock tools for safe agent evaluation"""
from typing import Dict, Any, List, Optional, Callable, Union
import asyncio
import weave


class MockTool:
    """Wrapper to mock a tool during evaluation.
    
    Records tool calls and returns user-defined responses.
    """
    
    def __init__(self, 
                 original_tool: Callable,
                 response: Union[Any, Callable] = None):
        """Initialize a mock tool.
        
        Args:
            original_tool: The original tool being mocked
            response: Either a static response or a function that generates responses
                     If a function, it will receive the same args/kwargs as the tool
        """
        self.original_tool = original_tool
        self.name = getattr(original_tool, '__name__', str(original_tool))
        self.response = response
        self.call_history: List[Dict[str, Any]] = []
        
        # Copy over attributes from the original tool for compatibility
        for attr in ['__name__', '__doc__', '__module__', '__qualname__']:
            if hasattr(original_tool, attr):
                setattr(self, attr, getattr(original_tool, attr))
    
    def __repr__(self):
        return f"MockTool({self.name})"
        
    @weave.op()
    async def __call__(self, *args, **kwargs):
        """Mock tool execution"""
        # Record the call
        self.call_history.append({
            'args': args,
            'kwargs': kwargs
        })
        
        # Return the response
        if callable(self.response):
            # If response is a function, call it with the tool arguments
            if asyncio.iscoroutinefunction(self.response):
                return await self.response(*args, **kwargs)
            else:
                return self.response(*args, **kwargs)
        elif self.response is not None:
            # Return static response
            return self.response
        else:
            # Default minimal response
            return {"success": True, "mock": True}
    
    def was_called(self) -> bool:
        """Check if tool was called"""
        return len(self.call_history) > 0
    
    def was_called_with(self, *args, **kwargs) -> bool:
        """Check if tool was called with specific arguments"""
        for call in self.call_history:
            if call['args'] == args and call['kwargs'] == kwargs:
                return True
        return False
    
    def get_call_args(self, call_index: int = -1) -> Dict[str, Any]:
        """Get arguments from a specific call (default: most recent)"""
        if not self.call_history:
            return {}
        return self.call_history[call_index]
    
    @property
    def call_count(self) -> int:
        """Number of times the tool was called"""
        return len(self.call_history)


class MockToolRegistry:
    """Registry for managing mock tools during evaluation"""
    
    def __init__(self):
        self.mocks: Dict[str, MockTool] = {}
        
    def register(self, tool: Callable, response: Union[Any, Callable] = None) -> MockTool:
        """Register a mock for a tool with a specific response.
        
        Args:
            tool: The tool to mock
            response: The response to return (static value or function)
            
        Returns:
            The created MockTool instance
        """
        tool_name = getattr(tool, '__name__', str(tool))
        mock = MockTool(tool, response)
        self.mocks[tool_name] = mock
        return mock
        
    def get_mock_tools(self, tools: List[Callable]) -> List[MockTool]:
        """Convert a list of tools to their mocks"""
        mock_tools = []
        for tool in tools:
            tool_name = getattr(tool, '__name__', str(tool))
            
            if tool_name in self.mocks:
                # Use existing mock
                mock_tools.append(self.mocks[tool_name])
            else:
                # Create basic mock with default response
                mock = MockTool(tool)
                self.mocks[tool_name] = mock
                mock_tools.append(mock)
                
        return mock_tools
    
    def reset_all(self):
        """Reset all mock call histories"""
        for mock in self.mocks.values():
            mock.call_history = []
    
    def get_tool_calls(self, tool_name: str) -> List[Dict[str, Any]]:
        """Get all calls made to a specific tool"""
        if tool_name in self.mocks:
            return self.mocks[tool_name].call_history
        return []


# Import asyncio only when needed to avoid issues
import asyncio


# Helper functions for common mock patterns

def mock_success(message: str = "Operation completed successfully", **extra_fields):
    """Create a successful response with optional extra fields"""
    return {"success": True, "message": message, **extra_fields}


def mock_error(error: str = "Operation failed", **extra_fields):
    """Create an error response with optional extra fields"""
    return {"success": False, "error": error, **extra_fields}


def mock_from_args(template: Dict[str, Any]):
    """Create a mock function that incorporates arguments into the response.
    
    Example:
        mock_from_args({"result": "Searched for: {query}", "count": 5})
    """
    def response_generator(*args, **kwargs):
        # Create a copy of the template
        result = template.copy()
        
        # Format any string values with kwargs
        for key, value in result.items():
            if isinstance(value, str) and '{' in value:
                try:
                    result[key] = value.format(**kwargs)
                except KeyError:
                    pass  # Keep original if formatting fails
                    
        return result
    
    return response_generator 