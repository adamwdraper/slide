"""
Space Monkey - Tyler Slack Agent

A simple, powerful way to deploy Tyler AI agents as Slack agents.
"""

# Re-export core components from other packages
from narrator import ThreadStore, FileStore
from tyler import Agent

# Import our own classes
from .slack_app import SlackApp
from .message_classifier_prompt import format_classifier_prompt
from .utils import get_logger

# Version
__version__ = "5.2.1"

# Main exports
__all__ = [
    "SlackApp",
    "Agent", 
    "ThreadStore",
    "FileStore",
    "format_classifier_prompt",
    "get_logger"
] 