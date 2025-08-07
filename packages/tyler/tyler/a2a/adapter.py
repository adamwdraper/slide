"""Tyler A2A adapter for converting A2A capabilities to Tyler format.

This module adapts A2A agent capabilities to work with Tyler's tool system,
allowing Tyler agents to delegate tasks to remote A2A agents.
"""

import re
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator

from .client import A2AClient, HAS_A2A
from ..utils.tool_runner import tool_runner

logger = logging.getLogger(__name__)


class A2AAdapter:
    """Adapter that converts A2A agent capabilities to Tyler's tool format.
    
    This adapter handles the conversion between A2A agent capabilities
    and Tyler's internal tool representation, enabling Tyler agents to
    delegate tasks to remote A2A agents.
    """
    
    def __init__(self, a2a_client: Optional[A2AClient] = None):
        """Initialize the adapter.
        
        Args:
            a2a_client: Optional A2A client instance. If not provided, creates a new one.
        """
        if not HAS_A2A:
            raise ImportError(
                "a2a-sdk is required for A2A support. Install with: pip install a2a-sdk"
            )
        
        self.client = a2a_client or A2AClient()
        self._registered_tools: Dict[str, str] = {}  # tyler_name -> agent_name
        
    async def connect(self, name: str, base_url: str, **kwargs) -> bool:
        """Connect to an A2A agent and register its capabilities with Tyler.
        
        Args:
            name: Unique name for this connection
            base_url: Base URL of the A2A agent
            **kwargs: Connection-specific arguments (headers, auth, etc.)
            
        Returns:
            bool: True if connection successful and capabilities registered
        """
        # Connect to the agent
        connected = await self.client.connect(name, base_url, **kwargs)
        if not connected:
            return False
            
        # Register agent capabilities with Tyler
        try:
            await self._register_agent_capabilities(name)
            return True
        except Exception as e:
            logger.error(f"Failed to register capabilities from agent '{name}': {e}")
            await self.client.disconnect(name)
            return False
    
    async def _register_agent_capabilities(self, agent_name: str) -> None:
        """Register all capabilities from an agent with Tyler's tool runner."""
        agent_card = self.client.get_agent_card(agent_name)
        
        if not agent_card:
            logger.warning(f"No agent card found for agent '{agent_name}'")
            return
        
        # Create a general delegation tool for this agent
        delegation_tool = self._create_delegation_tool(agent_name, agent_card)
        tool_name = delegation_tool["definition"]["function"]["name"]
        
        # Register with tool runner
        tool_runner.register_tool(
            name=tool_name,
            implementation=delegation_tool["implementation"],
            definition=delegation_tool["definition"]["function"]
        )
        
        # Register attributes
        if "attributes" in delegation_tool:
            tool_runner.register_tool_attributes(tool_name, delegation_tool["attributes"])
        
        # Track registration
        self._registered_tools[tool_name] = agent_name
        
        logger.info(f"Registered delegation tool for agent '{agent_name}'")
    
    def _create_delegation_tool(self, agent_name: str, agent_card) -> Dict[str, Any]:
        """Create a Tyler tool that delegates tasks to the A2A agent.
        
        Args:
            agent_name: Name of the agent
            agent_card: A2A agent card with capabilities
            
        Returns:
            Tyler tool definition dictionary
        """
        # Create a safe, namespaced tool name
        tyler_name = self._create_tyler_name(agent_name)
        
        # Extract capabilities and description from agent card
        capabilities = getattr(agent_card, 'capabilities', [])
        description = getattr(agent_card, 'description', f'Delegate tasks to {agent_name} agent')
        
        # Enhanced description with capabilities
        if capabilities:
            cap_list = ", ".join(capabilities)
            description = f"{description}. Capabilities: {cap_list}"
        
        # Create the Tyler tool definition
        tyler_tool = {
            "definition": {
                "type": "function",
                "function": {
                    "name": tyler_name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_description": {
                                "type": "string",
                                "description": "Detailed description of the task to delegate to the agent"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context or constraints for the task (optional)",
                                "default": ""
                            },
                            "stream_response": {
                                "type": "boolean",
                                "description": "Whether to stream the response as it arrives",
                                "default": False
                            }
                        },
                        "required": ["task_description"]
                    }
                }
            },
            "implementation": self._create_delegation_implementation(agent_name),
            "attributes": {
                "source": "a2a",
                "agent_name": agent_name,
                "agent_capabilities": capabilities,
                "delegation_tool": True,
                "supports_streaming": True
            }
        }
        
        return tyler_tool
    
    def _create_tyler_name(self, agent_name: str) -> str:
        """Create a Tyler-safe tool name for the agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Tyler-safe namespaced tool name
        """
        # Clean agent name
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', agent_name)
        
        # Create delegation tool name
        tyler_name = f"delegate_to_{clean_name}"
        
        # Ensure it starts with a letter or underscore
        if tyler_name and tyler_name[0].isdigit():
            tyler_name = f"_{tyler_name}"
            
        return tyler_name
    
    def _create_delegation_implementation(self, agent_name: str):
        """Create a function that delegates tasks to the A2A agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Async function that delegates tasks to the A2A agent
        """
        async def delegate_task(
            task_description: str, 
            context: str = "",
            stream_response: bool = False,
            **kwargs
        ):
            """Delegate a task to the A2A agent."""
            try:
                # Prepare the full task content
                full_content = task_description
                if context:
                    full_content = f"{task_description}\n\nContext: {context}"
                
                # Create task
                task_id = await self.client.create_task(agent_name, full_content, **kwargs)
                if not task_id:
                    return f"Failed to create task with agent {agent_name}"
                
                if stream_response:
                    # Return a streaming response
                    return self._handle_streaming_response(agent_name, task_id, full_content)
                else:
                    # Wait for completion and return final result
                    return await self._handle_sync_response(agent_name, task_id, full_content)
                
            except Exception as e:
                error_msg = f"Error delegating to A2A agent {agent_name}: {e}"
                logger.error(error_msg)
                return f"Delegation failed: {str(e)}"
        
        # Set function metadata for better debugging
        delegate_task.__name__ = f"delegate_to_{agent_name}"
        delegate_task.__doc__ = f"Delegate tasks to A2A agent: {agent_name}"
        
        return delegate_task
    
    async def _handle_sync_response(self, agent_name: str, task_id: str, task_content: str) -> str:
        """Handle synchronous task completion.
        
        Args:
            agent_name: Name of the agent
            task_id: ID of the task
            task_content: Original task content
            
        Returns:
            Final task result
        """
        try:
            # Collect all messages from the task
            messages = []
            async for message in self.client.stream_task_messages(agent_name, task_id):
                messages.append(message["content"])
                
                # Check if task is complete (implementation may vary)
                status = await self.client.get_task_status(agent_name, task_id)
                if status and status.get("status") == "completed":
                    break
            
            if messages:
                return "\n".join(messages)
            else:
                return f"Task {task_id} completed but no response received"
                
        except Exception as e:
            logger.error(f"Error handling sync response for task {task_id}: {e}")
            return f"Error retrieving response: {str(e)}"
    
    async def _handle_streaming_response(
        self, 
        agent_name: str, 
        task_id: str, 
        task_content: str
    ) -> AsyncGenerator[str, None]:
        """Handle streaming task responses.
        
        Args:
            agent_name: Name of the agent
            task_id: ID of the task
            task_content: Original task content
            
        Yields:
            Response chunks as they arrive
        """
        try:
            async for message in self.client.stream_task_messages(agent_name, task_id):
                yield message["content"]
                
        except Exception as e:
            logger.error(f"Error handling streaming response for task {task_id}: {e}")
            yield f"Stream error: {str(e)}"
    
    def get_tools_for_agent(self, agent_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get Tyler-formatted delegation tools for use with an Agent.
        
        Args:
            agent_names: Optional list of agent names. If None, returns tools for all agents.
            
        Returns:
            List of Tyler tool definitions ready for use with Agent
        """
        tyler_tools = []
        
        # Determine which agents to get tools for
        if agent_names is None:
            agents = self.client.list_connections()
        else:
            agents = [name for name in agent_names if self.client.is_connected(name)]
        
        # Create delegation tools for selected agents
        for agent_name in agents:
            agent_card = self.client.get_agent_card(agent_name)
            if agent_card:
                tyler_tool = self._create_delegation_tool(agent_name, agent_card)
                tyler_tools.append(tyler_tool)
        
        return tyler_tools
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from an agent and unregister its tools.
        
        Args:
            name: Name of the agent to disconnect from
        """
        # Unregister tools
        tools_to_remove = [
            tool_name for tool_name, agent_name in self._registered_tools.items()
            if agent_name == name
        ]
        
        for tool_name in tools_to_remove:
            # Note: tool_runner doesn't have unregister, so we just track it
            del self._registered_tools[tool_name]
        
        # Disconnect from agent
        await self.client.disconnect(name)
        
    async def disconnect_all(self) -> None:
        """Disconnect from all agents and clean up."""
        self._registered_tools.clear()
        await self.client.disconnect_all()
    
    def list_connected_agents(self) -> List[Dict[str, Any]]:
        """List all connected agents with their information.
        
        Returns:
            List of agent information dictionaries
        """
        agents = []
        for agent_name in self.client.list_connections():
            info = self.client.get_connection_info(agent_name)
            if info:
                agents.append(info)
        return agents
    
    async def get_agent_status(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get status information for a connected agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent status information or None
        """
        if not self.client.is_connected(agent_name):
            return None
        
        info = self.client.get_connection_info(agent_name)
        if info:
            # Add additional status information
            info["active_tasks"] = len([
                task_id for task_id, task in self.client._tasks.items()
                if hasattr(task, '_connection_name') and task._connection_name == agent_name
            ])
        
        return info