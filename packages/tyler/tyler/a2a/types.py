"""A2A type definitions and helpers for Tyler.

This module provides type definitions and conversion utilities for A2A Protocol v0.3.0
Part types (TextPart, FilePart, DataPart) and Artifacts.
"""

import base64
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

try:
    from a2a.types import (
        TextPart as A2ATextPart,
        FilePart as A2AFilePart,
        DataPart as A2ADataPart,
        Part as A2APart,
        Artifact as A2AArtifact,
        FileWithBytes as A2AFileWithBytes,
        FileWithUri as A2AFileWithUri,
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
    A2AFileWithBytes = None
    A2AFileWithUri = None

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


@dataclass
class FilePart:
    """Represents a file part in an A2A message.
    
    Files can be transmitted either inline (Base64 encoded) or via URI reference.
    Per A2A spec v0.3.0 (Section 4.1.7):
    - mediaType: MIME type of the file
    - name: Optional filename
    - fileWithBytes: Base64 encoded file content (mutually exclusive with fileWithUri)
    - fileWithUri: URI reference to the file (mutually exclusive with fileWithBytes)
    
    Attributes:
        name: The filename (optional per spec, but we require it)
        media_type: MIME type of the file (e.g., "application/pdf")
        file_with_bytes: Raw bytes for inline file content (mutually exclusive with file_with_uri)
        file_with_uri: URI reference to the file (mutually exclusive with file_with_bytes)
    """
    name: str
    media_type: str
    file_with_bytes: Optional[bytes] = None
    file_with_uri: Optional[str] = None
    
    # Backward compatibility aliases
    @property
    def mime_type(self) -> str:
        """Alias for media_type (backward compatibility)."""
        return self.media_type
    
    @property
    def data(self) -> Optional[bytes]:
        """Alias for file_with_bytes (backward compatibility)."""
        return self.file_with_bytes
    
    @property
    def uri(self) -> Optional[str]:
        """Alias for file_with_uri (backward compatibility)."""
        return self.file_with_uri
    
    def __post_init__(self):
        if self.file_with_bytes is None and self.file_with_uri is None:
            raise ValueError("FilePart must have either file_with_bytes or file_with_uri")
        if self.file_with_bytes is not None and self.file_with_uri is not None:
            raise ValueError("FilePart cannot have both file_with_bytes and file_with_uri")
    
    @property
    def is_inline(self) -> bool:
        """Check if this is an inline file (Base64 encoded)."""
        return self.file_with_bytes is not None
    
    @property
    def is_remote(self) -> bool:
        """Check if this is a remote file (URI reference)."""
        return self.file_with_uri is not None
    
    def to_base64(self) -> Optional[str]:
        """Convert inline data to Base64 string."""
        if self.file_with_bytes is None:
            return None
        return base64.b64encode(self.file_with_bytes).decode("utf-8")
    
    @classmethod
    def from_base64(cls, name: str, media_type: str, base64_data: str) -> "FilePart":
        """Create FilePart from Base64 encoded string."""
        data = base64.b64decode(base64_data)
        return cls(name=name, media_type=media_type, file_with_bytes=data)
    
    @classmethod
    def from_path(cls, path: Union[str, Path], media_type: Optional[str] = None) -> "FilePart":
        """Create FilePart from a file path."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Infer MIME type if not provided
        if media_type is None:
            import filetype
            kind = filetype.guess(str(path))
            media_type = kind.mime if kind else "application/octet-stream"
        
        with open(path, "rb") as f:
            data = f.read()
        
        return cls(name=path.name, media_type=media_type, file_with_bytes=data)


@dataclass
class DataPart:
    """Represents structured JSON data in an A2A message.
    
    Per A2A spec v0.3.0 (Section 4.1.8):
    - data: The structured data as a dictionary
    - mediaType: MIME type (defaults to application/json)
    
    Attributes:
        data: The structured data as a dictionary
        media_type: MIME type (defaults to application/json)
    """
    data: Dict[str, Any]
    media_type: str = "application/json"
    
    # Backward compatibility alias
    @property
    def mime_type(self) -> str:
        """Alias for media_type (backward compatibility)."""
        return self.media_type


class TaskState(Enum):
    """A2A Task states per spec Section 4.1.3."""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"
    UNKNOWN = "unknown"


@dataclass
class Artifact:
    """Represents a tangible output produced by an agent during task processing.
    
    Artifacts are the formal deliverables of a task, distinct from general messages.
    Per A2A spec v0.3.0 (Section 4.1.9):
    - artifactId: Unique identifier for this artifact (camelCase in JSON)
    - name: Human-readable name
    - parts: List of content parts
    
    Attributes:
        artifact_id: Unique identifier for this artifact (serialized as artifactId)
        name: Human-readable name for the artifact
        parts: List of content parts (TextPart, FilePart, DataPart)
        created_at: Timestamp when the artifact was created
        metadata: Optional additional metadata
        description: Optional description of the artifact
        index: Optional index for ordering multiple artifacts
        append: Optional flag indicating if artifact appends to previous
        last_chunk: Optional flag indicating if this is the last chunk
    """
    artifact_id: str
    name: str
    parts: List[Union["TextPart", FilePart, DataPart]]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    index: Optional[int] = None
    append: Optional[bool] = None
    last_chunk: Optional[bool] = None
    
    @classmethod
    def create(
        cls,
        name: str,
        parts: List[Union["TextPart", FilePart, DataPart]],
        metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        index: Optional[int] = None,
    ) -> "Artifact":
        """Create a new artifact with auto-generated ID."""
        return cls(
            artifact_id=str(uuid.uuid4()),
            name=name,
            parts=parts,
            created_at=datetime.now(timezone.utc),
            metadata=metadata,
            description=description,
            index=index,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with camelCase keys per A2A spec."""
        result = {
            "artifactId": self.artifact_id,
            "name": self.name,
            "parts": [],  # Parts need separate conversion
        }
        if self.description:
            result["description"] = self.description
        if self.index is not None:
            result["index"] = self.index
        if self.append is not None:
            result["append"] = self.append
        if self.last_chunk is not None:
            result["lastChunk"] = self.last_chunk
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class TextPart:
    """Represents plain text content in an A2A message.
    
    Attributes:
        text: The text content
    """
    text: str


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
        return [FilePart(name="data.bin", media_type="application/octet-stream", file_with_bytes=content)]
    
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
                "media_type": part.media_type,
                "mime_type": part.media_type,  # Alias for backward compat
                "file_with_bytes": part.file_with_bytes,
                "data": part.file_with_bytes,  # Alias for backward compat
                "file_with_uri": part.file_with_uri,
                "uri": part.file_with_uri,  # Alias for backward compat
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
    
    A2A SDK structure (v0.3.0):
    - TextPart: { text: str, kind: 'text' }
    - FilePart: { file: FileWithBytes | FileWithUri, kind: 'file' }
      - FileWithBytes: { bytes: str (base64), mimeType: str, name: str }
      - FileWithUri: { uri: str, mimeType: str, name: str }
    - DataPart: { data: dict, kind: 'data' }
    
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
            # A2A SDK uses nested FileWithBytes for inline files
            file_obj = A2AFileWithBytes(
                bytes=part.to_base64(),
                mimeType=part.media_type,
                name=part.name,
            )
            return A2AFilePart(file=file_obj)
        else:
            # A2A SDK uses nested FileWithUri for remote files
            file_obj = A2AFileWithUri(
                uri=part.file_with_uri,
                mimeType=part.media_type,
                name=part.name,
            )
            return A2AFilePart(file=file_obj)
    
    elif isinstance(part, DataPart):
        return A2ADataPart(data=part.data)
    
    else:
        raise ValueError(f"Unknown part type: {type(part)}")


def from_a2a_part(a2a_part: Any) -> Union[TextPart, FilePart, DataPart]:
    """Convert A2A SDK Part to internal Part.
    
    A2A SDK structure (v0.3.0):
    - TextPart: has 'text' attribute
    - FilePart: has 'file' attribute (FileWithBytes or FileWithUri)
      - FileWithBytes: has 'bytes' (base64 str), 'mime_type', 'name'
      - FileWithUri: has 'uri', 'mime_type', 'name'
    - DataPart: has 'data' attribute (dict)
    
    Also handles legacy field names for backward compatibility.
    
    Args:
        a2a_part: A2A SDK Part object
        
    Returns:
        Internal Part object
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for A2A support")
    
    # Handle Part wrapper type (SDK may wrap parts in a Part container with 'root')
    if hasattr(a2a_part, 'root'):
        a2a_part = a2a_part.root
    
    # Check the type by 'kind' attribute first (SDK v0.3.0 uses discriminator)
    kind = getattr(a2a_part, 'kind', None)
    
    if kind == 'text' or hasattr(a2a_part, 'text'):
        return TextPart(text=a2a_part.text)
    
    elif kind == 'file' or hasattr(a2a_part, 'file'):
        # SDK v0.3.0 uses nested 'file' object
        file_obj = getattr(a2a_part, 'file', None)
        if file_obj:
            # Get name and mime_type from nested file object (SDK uses snake_case attrs)
            name = getattr(file_obj, 'name', None) or 'unnamed'
            media_type = getattr(file_obj, 'mime_type', None) or 'application/octet-stream'
            
            # Check for FileWithBytes (has 'bytes' attr)
            file_bytes = getattr(file_obj, 'bytes', None)
            if file_bytes:
                # Decode Base64
                if isinstance(file_bytes, str):
                    file_bytes = base64.b64decode(file_bytes)
                return FilePart(
                    name=name,
                    media_type=media_type,
                    file_with_bytes=file_bytes,
                )
            
            # Check for FileWithUri (has 'uri' attr)
            file_uri = getattr(file_obj, 'uri', None)
            if file_uri:
                return FilePart(
                    name=name,
                    media_type=media_type,
                    file_with_uri=file_uri,
                )
            
            raise ValueError("FilePart.file must have either 'bytes' or 'uri'")
        
        # Legacy: direct attributes on FilePart
        name = getattr(a2a_part, 'name', 'unnamed')
        media_type = getattr(a2a_part, 'mediaType', None) or getattr(a2a_part, 'mime_type', 'application/octet-stream')
        
        file_bytes = getattr(a2a_part, 'fileWithBytes', None) or getattr(a2a_part, 'data', None)
        if file_bytes:
            if isinstance(file_bytes, str):
                file_bytes = base64.b64decode(file_bytes)
            return FilePart(name=name, media_type=media_type, file_with_bytes=file_bytes)
        
        file_uri = getattr(a2a_part, 'fileWithUri', None) or getattr(a2a_part, 'uri', None)
        if file_uri:
            return FilePart(name=name, media_type=media_type, file_with_uri=file_uri)
        
        raise ValueError("FilePart must have either file data or URI")
    
    elif kind == 'data' or (hasattr(a2a_part, 'data') and isinstance(getattr(a2a_part, 'data', None), dict)):
        return DataPart(data=a2a_part.data)
    
    else:
        # Unknown - try to extract text
        logger.warning(f"Unknown A2A part type, attempting text extraction: {type(a2a_part)}")
        return TextPart(text=str(a2a_part))


def to_a2a_artifact(artifact: Artifact) -> Any:
    """Convert internal Artifact to A2A SDK Artifact.
    
    A2A SDK Artifact signature:
    - artifactId: str (required)
    - name: str | None
    - description: str | None
    - parts: list[Part]
    - metadata: dict | None
    - extensions: list[str] | None
    
    Args:
        artifact: Internal Artifact object
        
    Returns:
        A2A SDK Artifact object
    """
    if not HAS_A2A:
        raise ImportError("a2a-sdk is required for A2A support")
    
    return A2AArtifact(
        artifactId=artifact.artifact_id,
        name=artifact.name,
        description=artifact.description,
        parts=[to_a2a_part(p) for p in artifact.parts],
        metadata=artifact.metadata,
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
        created_at=getattr(a2a_artifact, 'created_at', datetime.now(timezone.utc)),
        metadata=getattr(a2a_artifact, 'metadata', None),
    )

