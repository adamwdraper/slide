"""
Space Monkey - A powerful, extensible Slack bot framework

Built on the slide-narrator storage system, Space Monkey provides a comprehensive
framework for building production-ready Slack bots with AI agent capabilities.
"""

from .core.bot import SpaceMonkey
from .agents.base import SlackAgent, ClassifierAgent
from .core.config import Config

__version__ = "0.1.0"
__all__ = [
    "SpaceMonkey",
    "SlackAgent", 
    "ClassifierAgent",
    "Config",
] 