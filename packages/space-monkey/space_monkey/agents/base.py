"""
Base agent classes for Space Monkey bot framework
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from narrator import Thread, Message, ThreadStore, FileStore

if TYPE_CHECKING:
    from ..core.bot import SpaceMonkey

class SlackAgent(ABC):
    """
    Base class for all Slack agents in Space Monkey
    
    Agents process messages and can react to various Slack events.
    Each agent has access to the thread store and file store for persistence.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], thread_store: ThreadStore, file_store: FileStore, bot: "SpaceMonkey"):
        self.name = name
        self.config = config
        self.thread_store = thread_store
        self.file_store = file_store
        self.bot = bot
        self.version = config.get("version", "1.0.0")
    
    @abstractmethod
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        """
        Determine if this agent should handle the given event
        
        Args:
            event: The Slack event data
            thread: The thread associated with the event
            
        Returns:
            bool: True if this agent should handle the event
        """
        pass
    
    @abstractmethod
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        """
        Process a message and return a response
        
        Args:
            thread: The thread containing the message
            event: The Slack event data
            
        Returns:
            Optional[str]: The response message, or None if no response needed
        """
        pass
    
    async def on_reaction_added(self, event: Dict[str, Any], thread: Thread) -> None:
        """
        Handle reaction added events (optional)
        
        Args:
            event: The reaction event data
            thread: The thread containing the reacted message
        """
        pass
    
    async def on_reaction_removed(self, event: Dict[str, Any], thread: Thread) -> None:
        """
        Handle reaction removed events (optional)
        
        Args:
            event: The reaction event data
            thread: The thread containing the reacted message
        """
        pass
    
    async def on_startup(self) -> None:
        """
        Called when the agent is initialized (optional)
        """
        pass
    
    async def on_shutdown(self) -> None:
        """
        Called when the agent is shut down (optional)
        """
        pass

class ClassifierAgent(SlackAgent):
    """
    Special agent type that classifies messages and returns structured responses
    
    Classifier agents run first in the pipeline and can determine how other agents
    should respond to a message (ignore, emoji reaction, full response, etc.)
    """
    
    @abstractmethod
    async def classify_message(self, thread: Thread, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a message and return structured response
        
        Args:
            thread: The thread containing the message
            event: The Slack event data
            
        Returns:
            Dict[str, Any]: Classification result with keys:
                - response_type: "ignore", "emoji_reaction", "full_response"
                - reasoning: str explanation
                - suggested_emoji: str (if response_type is "emoji_reaction")
                - confidence: float (optional confidence score)
        """
        pass
    
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        """
        For classifier agents, this calls classify_message and returns None
        The classification result is handled by the bot's event processing pipeline
        """
        # Classifier agents don't return text responses directly
        # They return structured classification data
        return None

class SimpleAgent(SlackAgent):
    """
    A simple agent implementation for basic use cases
    
    This class provides a concrete implementation that users can subclass
    for simple agents that just need to respond to certain patterns.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], thread_store: ThreadStore, file_store: FileStore, bot: "SpaceMonkey"):
        super().__init__(name, config, thread_store, file_store, bot)
        self.patterns = config.get("patterns", [])
        self.response_template = config.get("response_template", "Hello from {name}!")
    
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        """Handle messages matching configured patterns"""
        text = event.get("text", "").lower()
        return any(pattern.lower() in text for pattern in self.patterns)
    
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        """Return the configured response template"""
        return self.response_template.format(name=self.name, **self.config) 