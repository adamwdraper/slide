"""
Space Monkey - Tyler Slack Bot

A simple, powerful way to deploy Tyler AI agents as Slack bots.
"""

# Re-export core components from other packages
from narrator import ThreadStore, FileStore
from tyler import Agent

# Import our own classes
from .slack_app import SlackApp

# Version
__version__ = "0.1.1"

# Main exports
__all__ = [
    "SlackApp",
    "Agent", 
    "ThreadStore",
    "FileStore"
] 