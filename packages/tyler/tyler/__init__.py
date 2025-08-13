"""Tyler - A development kit for AI agents with a complete lack of conventional limitations"""

__version__ = "2.0.2"

from tyler.utils.logging import get_logger
from tyler.models.agent import Agent
from tyler.models.execution import (
    AgentResult,
    ExecutionEvent,
    EventType
)
from narrator import Thread, Message, ThreadStore, FileStore, Attachment

# Configure logging when package is imported
logger = get_logger(__name__) 