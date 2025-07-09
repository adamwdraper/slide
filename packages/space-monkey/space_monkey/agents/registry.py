"""
Agent registry system for Space Monkey bot framework
"""

import logging
from typing import Dict, List, Type, Any, Optional, TYPE_CHECKING
from narrator import Thread, ThreadStore, FileStore

from .base import SlackAgent, ClassifierAgent

if TYPE_CHECKING:
    from ..core.bot import SpaceMonkey

logger = logging.getLogger(__name__)

class AgentRegistry:
    """
    Registry for managing agents in Space Monkey
    
    The registry handles agent registration, instantiation, and lifecycle management.
    """
    
    def __init__(self, bot: "SpaceMonkey"):
        self.bot = bot
        self._agent_classes: Dict[str, Type[SlackAgent]] = {}
        self._agent_configs: Dict[str, Dict[str, Any]] = {}
        self._agent_instances: Dict[str, SlackAgent] = {}
        self._classifiers: List[ClassifierAgent] = []
        self._regular_agents: List[SlackAgent] = []
    
    def register(self, name: str, agent_class: Type[SlackAgent], config: Dict[str, Any] = None) -> None:
        """
        Register an agent class with the registry
        
        Args:
            name: Unique name for the agent
            agent_class: The agent class to register
            config: Configuration for the agent
        """
        if name in self._agent_classes:
            logger.warning(f"Agent '{name}' is already registered, overwriting")
        
        self._agent_classes[name] = agent_class
        self._agent_configs[name] = config or {}
        
        logger.info(f"Registered agent '{name}' of type {agent_class.__name__}")
    
    async def initialize_all(self, thread_store: ThreadStore, file_store: FileStore) -> None:
        """
        Initialize all registered agents
        
        Args:
            thread_store: The thread store instance
            file_store: The file store instance
        """
        logger.info(f"Initializing {len(self._agent_classes)} agents...")
        
        for name, agent_class in self._agent_classes.items():
            config = self._agent_configs[name]
            
            try:
                # Create agent instance
                agent = agent_class(name, config, thread_store, file_store, self.bot)
                
                # Call startup hook
                await agent.on_startup()
                
                # Store instance
                self._agent_instances[name] = agent
                
                # Categorize agents
                if isinstance(agent, ClassifierAgent):
                    self._classifiers.append(agent)
                else:
                    self._regular_agents.append(agent)
                
                logger.info(f"Initialized agent '{name}' successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize agent '{name}': {e}")
                raise
        
        logger.info(f"Successfully initialized {len(self._agent_instances)} agents "
                   f"({len(self._classifiers)} classifiers, {len(self._regular_agents)} regular)")
    
    async def shutdown_all(self) -> None:
        """Shutdown all agent instances"""
        logger.info("Shutting down all agents...")
        
        for name, agent in self._agent_instances.items():
            try:
                await agent.on_shutdown()
                logger.info(f"Shut down agent '{name}' successfully")
            except Exception as e:
                logger.error(f"Error shutting down agent '{name}': {e}")
    
    def get_agent(self, name: str) -> Optional[SlackAgent]:
        """Get an agent instance by name"""
        return self._agent_instances.get(name)
    
    def get_classifiers(self) -> List[ClassifierAgent]:
        """Get all classifier agents"""
        return self._classifiers.copy()
    
    def get_agents_for_event(self, event: Dict[str, Any], thread: Thread) -> List[SlackAgent]:
        """
        Get all agents that should handle the given event
        
        Args:
            event: The Slack event data
            thread: The thread associated with the event
            
        Returns:
            List[SlackAgent]: List of agents that should handle the event
        """
        handling_agents = []
        
        for agent in self._regular_agents:
            try:
                if agent.should_handle(event, thread):
                    handling_agents.append(agent)
            except Exception as e:
                logger.error(f"Error checking if agent '{agent.name}' should handle event: {e}")
        
        logger.debug(f"Found {len(handling_agents)} agents to handle event")
        return handling_agents
    
    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered agents with their info
        
        Returns:
            Dict mapping agent names to their info
        """
        agents_info = {}
        
        for name, agent in self._agent_instances.items():
            agents_info[name] = {
                "name": name,
                "class": agent.__class__.__name__,
                "version": agent.version,
                "type": "classifier" if isinstance(agent, ClassifierAgent) else "regular",
                "config": agent.config
            }
        
        return agents_info
    
    @property
    def agent_count(self) -> int:
        """Total number of registered agents"""
        return len(self._agent_instances)
    
    @property
    def classifier_count(self) -> int:
        """Number of classifier agents"""
        return len(self._classifiers)
    
    @property
    def regular_agent_count(self) -> int:
        """Number of regular agents"""
        return len(self._regular_agents) 