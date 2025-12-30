"""A2A type definitions and helpers for Tyler.

This module provides type definitions and conversion utilities for A2A Protocol v0.3.0
Part types (TextPart, FilePart, DataPart) and Artifacts.
"""

import base64
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import ipaddress
import socket

try:
    from a2a.types import (
        TextPart as A2ATextPart,
        FilePart as A2AFilePart,
        DataPart as A2ADataPart,
        Part as A2APart,
        Artifact as A2AArtifact,
    )
    HAS_A2A = True
except ImportError:
    HAS_A2A = False
    # Type stubs for when a2a-sdk is not installed
    A2ATextPart = None
    A2AFilePart = None
    A2ADataPart = None
    A2APart = None
    A2AArtifact = None

logger = logging.getLogger(__name__)


# Constants
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB default limit
ALLOWED_URI_SCHEMES = {"https"}  # Only HTTPS for security
A2A_PROTOCOL_VERSION = "0.3.0"  # A2A Protocol version supported


class PartType(Enum):
    """Enumeration of A2A Part types."""
    TEXT = "text"
    FILE = "file"
    DATA = "data"


class PushEventType(Enum):
    """Enumeration of push notification event types."""
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    ARTIFACT_PRODUCED = "task.artifact"


@dataclass
class FilePart:
    """Represents a file part in an A2A message.
    
    Files can be transmitted either inline (Base64 encoded) or via URI reference.
    
    Attributes:
        name: The filename
        mime_type: MIME type of the file (e.g., "application/pdf")
        data: Raw bytes for inline file content (mutually exclusive with uri)
        uri: URI reference to the file (mutually exclusive with data)
    """
    name: str
    mime_type: str
    data: Optional[bytes] = None
    uri: Optional[str] = None
    
    def __post_init__(self):
        if self.data is None and self.uri is None:
            raise ValueError("FilePart must have either data or uri")
        if self.data is not None and self.uri is not None:
            raise ValueError("FilePart cannot have both data and uri")
    
    @property
    def is_inline(self) -> bool:
        """Check if this is an inline file (Base64 encoded)."""
        return self.data is not None
    
    @property
    def is_remote(self) -> bool:
        """Check if this is a remote file (URI reference)."""
        return self.uri is not None
    
    def to_base64(self) -> Optional[str]:
        """Convert inline data to Base64 string."""
        if self.data is None:
            return None
        return base64.b64encode(self.data).decode("utf-8")
    
    @classmethod
    def from_base64(cls, name: str, mime_type: str, base64_data: str) -> "FilePart":
        """Create FilePart from Base64 encoded string."""
        data = base64.b64decode(base64_data)
        return cls(name=name, mime_type=mime_type, data=data)
    
    @classmethod
    def from_path(cls, path: Union[str, Path], mime_type: Optional[str] = None) -> "FilePart":
        """Create FilePart from a file path."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Infer MIME type if not provided
        if mime_type is None:
            import filetype
            kind = filetype.guess(str(path))
            mime_type = kind.mime if kind else "application/octet-stream"
        
        with open(path, "rb") as f:
            data = f.read()
        
        return cls(name=path.name, mime_type=mime_type, data=data)


@dataclass
class DataPart:
    """Represents structured JSON data in an A2A message.
    
    Attributes:
        data: The structured data as a dictionary
        mime_type: MIME type (defaults to application/json)
    """
    data: Dict[str, Any]
    mime_type: str = "application/json"


@dataclass
class Artifact:
    """Represents a tangible output produced by an agent during task processing.
    
    Artifacts are the formal deliverables of a task, distinct from general messages.
    
    Attributes:
        artifact_id: Unique identifier for this artifact
        name: Human-readable name for the artifact
        parts: List of content parts (TextPart, FilePart, DataPart)
        created_at: Timestamp when the artifact was created
        metadata: Optional additional metadata
    """
    artifact_id: str
    name: str
    parts: List[Union["TextPart", FilePart, DataPart]]
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def create(
        cls,
        name: str,
        parts: List[Union["TextPart", FilePart, DataPart]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> "Artifact":
        """Create a new artifact with auto-generated ID."""
        return cls(
            artifact_id=str(uuid.uuid4()),
            name=name,
            parts=parts,
            created_at=datetime.utcnow(),
            metadata=metadata
        )


@dataclass
class TextPart:
    """Represents plain text content in an A2A message.
    
    Attributes:
        text: The text content
    """
    text: str


@dataclass
class PushNotificationConfig:
    """Configuration for push notifications on task updates.
    
    Attributes:
        webhook_url: URL to POST notifications to (must be HTTPS)
        events: List of event types to subscribe to
        headers: Optional custom headers to include in webhook requests
        secret: Optional secret for HMAC signing of webhook payloads
    """
    webhook_url: str
    events: List[str] = field(default_factory=lambda: [
        PushEventType.TASK_CREATED.value,
        PushEventType.TASK_UPDATED.value,
        PushEventType.TASK_COMPLETED.value,
    ])
    headers: Optional[Dict[str, str]] = None
    secret: Optional[str] = None
    
    def __post_init__(self):
        if not validate_webhook_url(self.webhook_url):
            raise ValueError(f"Invalid webhook URL: {self.webhook_url}")


@dataclass
class PushNotificationEvent:
    """A push notification event to be sent to a webhook.
    
    Attributes:
        event_id: Unique identifier for this event
        event_type: Type of event (from PushEventType)
        task_id: ID of the task this event relates to
        context_id: Optional context ID grouping related tasks
        timestamp: When the event occurred
        data: Event-specific payload data
    """
    event_id: str
    event_type: str
    task_id: str
    timestamp: datetime
    data: Dict[str, Any]
    context_id: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        event_type: PushEventType,
        task_id: str,
        data: Dict[str, Any],
        context_id: Optional[str] = None
    ) -> "PushNotificationEvent":
        """Create a new push notification event."""
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type.value,
            task_id=task_id,
            timestamp=datetime.utcnow(),
            data=data,
            context_id=context_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }
        if self.context_id:
            result["context_id"] = self.context_id
        return result


def validate_webhook_url(url: str) -> bool:
    """Validate a webhook URL for security.
    
    Ensures the URL uses HTTPS and doesn't point to private IP ranges.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if the URL is valid and safe, False otherwise
    """
    try:
        parsed = urlparse(url)
        
        # Must be HTTPS
        if parsed.scheme not in ALLOWED_URI_SCHEMES:
            logger.warning(f"Webhook URL must use HTTPS: {url}")
            return False
        
        # Must have a hostname
        if not parsed.hostname:
            logger.warning(f"Webhook URL missing hostname: {url}")
            return False
        
        # Check for private IP ranges
        try:
            # Resolve hostname to IP
            ip = socket.gethostbyname(parsed.hostname)
            ip_obj = ipaddress.ip_address(ip)
            
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                logger.error(f"SSRF attempt blocked - private IP detected: {url} -> {ip}")
                return False
        except socket.gaierror:
            # DNS resolution failed - might be valid but unreachable
            logger.warning(f"Could not resolve hostname: {parsed.hostname}")
            # Allow it - the request will fail at runtime if unreachable
            pass
        
        return True
        
    except Exception as e:
        logger.warning(f"Error validating webhook URL '{url}': {e}")
        return False


def validate_file_uri(uri: str) -> bool:
    """Validate a file URI for security.
    
    Similar to webhook URL validation - ensures HTTPS and no private IPs.
    
    Args:
        uri: The URI to validate
        
    Returns:
        True if the URI is valid and safe, False otherwise
    """
    return validate_webhook_url(uri)


# Type conversion utilities

def tyler_content_to_parts(
    content: Union[str, Dict[str, Any], bytes, Path, List[Any]]
) -> List[Union[TextPart, FilePart, DataPart]]:
    """Convert Tyler content to A2A Parts.
    
    Args:
        content: Content to convert - can be string, dict, bytes, Path, or list
        
    Returns:
        List of Part objects
    """
    if isinstance(content, str):
        return [TextPart(text=content)]
    
    elif isinstance(content, dict):
        return [DataPart(data=content)]
    
    elif isinstance(content, bytes):
        return [FilePart(name="data.bin", mime_type="application/octet-stream", data=content)]
    
    elif isinstance(content, Path):
        return [FilePart.from_path(content)]
    
    elif isinstance(content, list):
        # Recursively convert list items
        parts = []
        for item in content:
            parts.extend(tyler_content_to_parts(item))
        return parts
    
    else:
        # Fallback - convert to string
        return [TextPart(text=str(content))]


def parts_to_tyler_content(
    parts: List[Union[TextPart, FilePart, DataPart]]
) -> Dict[str, Any]:
    """Convert A2A Parts to Tyler-friendly content dictionary.
    
    Args:
        parts: List of Part objects
        
    Returns:
        Dictionary with 'text', 'files', and 'data' keys
    """
    result = {
        "text": [],
        "files": [],
        "data": [],
    }
    
    for part in parts:
        if isinstance(part, TextPart):
            result["text"].append(part.text)
        elif isinstance(part, FilePart):
            result["files"].append({
                "name": part.name,
                "mime_type": part.mime_type,
                "data": part.data,
                "uri": part.uri,
                "is_inline": part.is_inline,
            })
        elif isinstance(part, DataPart):
            result["data"].append(part.data)
    
    return result


def extract_text_from_parts(
    parts: List[Union[TextPart, FilePart, DataPart]]
) -> str:
    """Extract and concatenate all text content from parts.
    
    Args:
        parts: List of Part objects
        
    Returns:
        Concatenated text content
    """
    texts = []
    for part in parts:
        if isinstance(part, TextPart):
            texts.append(part.text)
    return "\n".join(texts) if texts else ""


# A2A SDK conversion utilities

def to_a2a_part(part: Union[TextPart, FilePart, DataPart]) -> Any:
    """Convert internal Part to A2A SDK Part.
    
    Args:
        part: Internal Part object
        
    Returns:
        A2A SDK Part object
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for A2A support")
    
    if isinstance(part, TextPart):
        return A2ATextPart(text=part.text)
    
    elif isinstance(part, FilePart):
        if part.is_inline:
            return A2AFilePart(
                name=part.name,
                mime_type=part.mime_type,
                data=part.to_base64(),
            )
        else:
            return A2AFilePart(
                name=part.name,
                mime_type=part.mime_type,
                uri=part.uri,
            )
    
    elif isinstance(part, DataPart):
        return A2ADataPart(
            data=part.data,
            mime_type=part.mime_type,
        )
    
    else:
        raise ValueError(f"Unknown part type: {type(part)}")


def from_a2a_part(a2a_part: Any) -> Union[TextPart, FilePart, DataPart]:
    """Convert A2A SDK Part to internal Part.
    
    Args:
        a2a_part: A2A SDK Part object
        
    Returns:
        Internal Part object
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for A2A support")
    
    # Check the type by attribute presence (duck typing)
    if hasattr(a2a_part, 'text'):
        return TextPart(text=a2a_part.text)
    
    elif hasattr(a2a_part, 'name') and hasattr(a2a_part, 'mime_type'):
        # FilePart
        if hasattr(a2a_part, 'data') and a2a_part.data:
            # Inline file
            data = base64.b64decode(a2a_part.data) if isinstance(a2a_part.data, str) else a2a_part.data
            return FilePart(
                name=a2a_part.name,
                mime_type=a2a_part.mime_type,
                data=data,
            )
        elif hasattr(a2a_part, 'uri') and a2a_part.uri:
            # Remote file
            return FilePart(
                name=a2a_part.name,
                mime_type=a2a_part.mime_type,
                uri=a2a_part.uri,
            )
        else:
            raise ValueError("FilePart must have either data or uri")
    
    elif hasattr(a2a_part, 'data') and isinstance(getattr(a2a_part, 'data', None), dict):
        # DataPart
        return DataPart(
            data=a2a_part.data,
            mime_type=getattr(a2a_part, 'mime_type', 'application/json'),
        )
    
    else:
        # Unknown - try to extract text
        logger.warning(f"Unknown A2A part type, attempting text extraction: {type(a2a_part)}")
        return TextPart(text=str(a2a_part))


def to_a2a_artifact(artifact: Artifact) -> Any:
    """Convert internal Artifact to A2A SDK Artifact.
    
    Args:
        artifact: Internal Artifact object
        
    Returns:
        A2A SDK Artifact object
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for A2A support")
    
    return A2AArtifact(
        artifact_id=artifact.artifact_id,
        name=artifact.name,
        parts=[to_a2a_part(p) for p in artifact.parts],
    )


def from_a2a_artifact(a2a_artifact: Any) -> Artifact:
    """Convert A2A SDK Artifact to internal Artifact.
    
    Args:
        a2a_artifact: A2A SDK Artifact object
        
    Returns:
        Internal Artifact object
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for A2A support")
    
    return Artifact(
        artifact_id=a2a_artifact.artifact_id,
        name=a2a_artifact.name,
        parts=[from_a2a_part(p) for p in a2a_artifact.parts],
        created_at=getattr(a2a_artifact, 'created_at', datetime.utcnow()),
        metadata=getattr(a2a_artifact, 'metadata', None),
    )

