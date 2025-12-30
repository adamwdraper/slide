"""Tyler A2A (Agent-to-Agent) integration module.

This module provides support for the A2A (Agent2Agent) protocol v0.3.0,
enabling Tyler agents to communicate with other agents across platforms.

Key features:
- Full Part type support (TextPart, FilePart, DataPart)
- Artifact production and consumption
- Context-based task grouping
- Push notifications for long-running tasks (using SDK infrastructure)
"""

from .adapter import A2AAdapter
from .client import A2AClient
from .server import A2AServer
from .types import (
    # Part types
    TextPart,
    FilePart,
    DataPart,
    PartType,
    # Task state
    TaskState,
    # Artifacts
    Artifact,
    # Utility functions
    tyler_content_to_parts,
    parts_to_tyler_content,
    extract_text_from_parts,
    # A2A SDK conversion utilities
    to_a2a_part,
    from_a2a_part,
    to_a2a_artifact,
    from_a2a_artifact,
    # Constants
    MAX_FILE_SIZE_BYTES,
    A2A_PROTOCOL_VERSION,
)
from .notifications import (
    TylerPushNotificationSender,
    create_push_notification_sender,
)

# Protocol version
try:
    from .server import A2A_PROTOCOL_VERSION
except ImportError:
    A2A_PROTOCOL_VERSION = "0.3.0"

__all__ = [
    # Core classes
    "A2AAdapter",
    "A2AClient",
    "A2AServer",
    # Part types
    "TextPart",
    "FilePart",
    "DataPart",
    "PartType",
    # Task state
    "TaskState",
    # Artifacts
    "Artifact",
    # Push notifications (uses SDK infrastructure)
    "TylerPushNotificationSender",
    "create_push_notification_sender",
    # Utility functions
    "tyler_content_to_parts",
    "parts_to_tyler_content",
    "extract_text_from_parts",
    "to_a2a_part",
    "from_a2a_part",
    "to_a2a_artifact",
    "from_a2a_artifact",
    # Constants
    "MAX_FILE_SIZE_BYTES",
    "A2A_PROTOCOL_VERSION",
]
