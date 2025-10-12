"""ToolManager for coordinating tool registration and agent delegation.

This module provides centralized management of tool registration, including
delegation tools for child agents.
"""
from typing import List, Dict, Any, TYPE_CHECKING
from narrator import Thread, Message
from tyler.utils.tool_runner import tool_runner
from tyler.utils.tool_strategies import ToolRegistrar
from tyler.utils.logging import get_logger

if TYPE_CHECKING:
    from weave import Prompt

logger = get_logger(__name__)


class ToolManager:
    """Manages tool registration and agent delegation.
    
    This class coordinates the registration of various tool types and
    sets up delegation tools for child agents.
    
    Attributes:
        tools: List of tools in various formats
        agents: List of child agents for delegation
        registrar: ToolRegistrar instance for strategy-based registration
    """
    
    def __init__(self, tools: List[Any] = None, agents: List = None):
        """Initialize the ToolManager.
        
        Args:
            tools: List of tools in various formats (strings, modules, dicts, callables)
            agents: List of Agent instances that can be delegated to
        """
        self.tools = tools or []
        self.agents = agents or []
        self.registrar = ToolRegistrar()
    
    def register_all_tools(self) -> List[Dict]:
        """Register all tools and return their definitions.
        
        This registers both regular tools and creates delegation tools for
        any child agents.
        
        Returns:
            List of all registered tool definitions in OpenAI format
            
        Raises:
            ValueError: If any tool is invalid or can't be registered
        """
        processed_tools = []
        
        # Register regular tools
        if self.tools:
            logger.debug(f"Registering {len(self.tools)} tools")
            tool_definitions = self.registrar.register_tools(self.tools, tool_runner)
            processed_tools.extend(tool_definitions)
        
        # Create delegation tools for agents
        if self.agents:
            logger.debug(f"Creating delegation tools for {len(self.agents)} agents")
            delegation_tools = self._create_delegation_tools()
            processed_tools.extend(delegation_tools)
        
        logger.info(f"Total tools registered: {len(processed_tools)}")
        return processed_tools
    
    def _create_delegation_tools(self) -> List[Dict]:
        """Create delegation tools for all child agents.
        
        Returns:
            List of delegation tool definitions
        """
        delegation_tools = []
        
        for agent in self.agents:
            tool_def = self._create_delegation_tool_for_agent(agent)
            delegation_tools.append(tool_def)
            
            # Register the tool implementation
            tool_name = tool_def['function']['name']
            implementation = self._create_delegation_handler(agent)
            
            tool_runner.register_tool(
                name=tool_name,
                implementation=implementation,
                definition=tool_def['function']
            )
            
            logger.info(f"Registered delegation tool: {tool_name}")
        
        return [{"type": "function", "function": tool_def['function']} 
                for tool_def in delegation_tools]
    
    def _create_delegation_tool_for_agent(self, agent) -> Dict:
        """Create a tool definition for delegating to an agent.
        
        Args:
            agent: Agent instance to delegate to
            
        Returns:
            Tool definition dict
        """
        # Get agent purpose for description
        # str() works for all types including strings and Prompt objects
        purpose = str(agent.purpose)
        
        return {
            "type": "function",
            "function": {
                "name": f"delegate_to_{agent.name}",
                "description": f"Delegate task to {agent.name}: {purpose}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": f"The task or question to delegate to the {agent.name} agent"
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context to provide to the agent (optional)",
                            "additionalProperties": True
                        }
                    },
                    "required": ["task"]
                }
            }
        }
    
    def _create_delegation_handler(self, agent):
        """Create a delegation handler function for an agent.
        
        Args:
            agent: Agent instance to delegate to
            
        Returns:
            Async function that handles delegation
        """
        async def delegation_handler(task, context=None, **kwargs):
            """Delegate a task to the child agent."""
            # Create a new thread for the delegated task
            thread = Thread()
            
            # Add context as a system message if provided
            if context:
                context_content = "Context information:\n"
                for key, value in context.items():
                    context_content += f"- {key}: {value}\n"
                thread.add_message(Message(
                    role="system",
                    content=context_content
                ))
            
            # Add the task as a user message
            thread.add_message(Message(
                role="user",
                content=task
            ))
            
            # Execute the child agent directly
            logger.info(f"Delegating task to {agent.name}: {task}")
            try:
                result_thread, messages = await agent.go(thread)
                
                # Extract response from assistant messages
                response = "\n\n".join([
                    m.content for m in messages 
                    if m.role == "assistant" and m.content
                ])
                
                logger.info(f"Agent {agent.name} completed delegated task")
                return response
                
            except Exception as e:
                logger.error(f"Error in delegated agent {agent.name}: {str(e)}")
                return f"Error in delegated agent '{agent.name}': {str(e)}"
        
        # Set function metadata
        delegation_handler.__name__ = f"delegate_to_{agent.name}"
        delegation_handler.__doc__ = f"Delegate tasks to agent: {agent.name}"
        
        return delegation_handler

