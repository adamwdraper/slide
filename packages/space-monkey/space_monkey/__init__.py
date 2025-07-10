"""
Space Monkey: Agent orchestration and workflow management for the Slide AI framework.
"""

__version__ = "0.1.0"
__author__ = "adamwdraper"
__email__ = "adam@adamdraper.com"

# Core exports
from .templates import TemplateManager, AgentTemplate

__all__ = ["TemplateManager", "AgentTemplate"]
