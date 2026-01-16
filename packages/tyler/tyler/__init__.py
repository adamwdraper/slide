"""Tyler - A development kit for AI agents with a complete lack of conventional limitations"""

__version__ = "6.2.0"

from tyler.utils.logging import get_logger
from tyler.models.agent import Agent
from tyler.config import load_config
from tyler.models.execution import (
    AgentResult,
    ExecutionEvent,
    EventType,
    StructuredOutputError,
    ToolContextError
)
from tyler.models.retry_config import RetryConfig
from tyler.utils.tool_runner import ToolContext
from narrator import Thread, Message, ThreadStore, FileStore, Attachment
from tyler.streaming import (
    VercelStreamFormatter,
    VERCEL_STREAM_HEADERS,
)

# Configure logging when package is imported
logger = get_logger(__name__) 