"""
Agent system for Space Monkey bot framework
"""

from .base import SlackAgent, ClassifierAgent
from .registry import AgentRegistry

__all__ = [
    "SlackAgent",
    "ClassifierAgent", 
    "AgentRegistry",
] 