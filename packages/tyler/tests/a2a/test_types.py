"""Tests for A2A type definitions and utilities.

Tests cover:
- Part type creation and validation (AC-3, AC-4, AC-5, AC-6)
- Artifact creation (AC-7)
- Push notification configuration
- URL validation for SSRF prevention
- Type conversion utilities

Updated for A2A Protocol v0.3.0 spec field names:
- FilePart: mediaType, fileWithBytes, fileWithUri
- DataPart: mediaType
- Artifact: artifactId (camelCase in JSON)
"""

import pytest
import base64
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from tyler.a2a.types import (
    TextPart,
    FilePart,
    DataPart,
    Artifact,
    PartType,
    TaskState,
    tyler_content_to_parts,
    parts_to_tyler_content,
    extract_text_from_parts,
    MAX_FILE_SIZE_BYTES,
    A2A_PROTOCOL_VERSION,
)


class TestTextPart:
    """Test cases for TextPart (AC-3)."""
    
    def test_create_text_part(self):
        """Test basic TextPart creation."""
        part = TextPart(text="Hello, world!")
        assert part.text == "Hello, world!"
    
    def test_text_part_empty_string(self):
        """Test TextPart with empty string."""
        part = TextPart(text="")
        assert part.text == ""
    
    def test_text_part_unicode(self):
        """Test TextPart with unicode content."""
        part = TextPart(text="Hello 世界 🌍")
        assert part.text == "Hello 世界 🌍"


class TestFilePart:
    """Test cases for FilePart (AC-4, AC-5).
    
    Uses A2A v0.3.0 spec field names: mediaType, fileWithBytes, fileWithUri
    """
    
    def test_create_file_part_inline(self):
        """Test FilePart with inline data (AC-4)."""
        data = b"Hello, file content!"
        part = FilePart(name="test.txt", media_type="text/plain", file_with_bytes=data)
        
        assert part.name == "test.txt"
        assert part.media_type == "text/plain"
        assert part.file_with_bytes == data
        assert part.file_with_uri is None
        assert part.is_inline is True
        assert part.is_remote is False
        
        # Test backward compatibility aliases
        assert part.mime_type == "text/plain"
        assert part.data == data
        assert part.uri is None
    
    def test_create_file_part_uri(self):
        """Test FilePart with URI reference (AC-5)."""
        part = FilePart(
            name="document.pdf",
            media_type="application/pdf",
            file_with_uri="https://example.com/files/document.pdf"
        )
        
        assert part.name == "document.pdf"
        assert part.media_type == "application/pdf"
        assert part.file_with_bytes is None
        assert part.file_with_uri == "https://example.com/files/document.pdf"
        assert part.is_inline is False
        assert part.is_remote is True
        
        # Test backward compatibility aliases
        assert part.mime_type == "application/pdf"
        assert part.data is None
        assert part.uri == "https://example.com/files/document.pdf"
    
    def test_file_part_requires_data_or_uri(self):
        """Test FilePart validation - must have file_with_bytes or file_with_uri."""
        with pytest.raises(ValueError, match="must have either file_with_bytes or file_with_uri"):
            FilePart(name="test.txt", media_type="text/plain")
    
    def test_file_part_cannot_have_both(self):
        """Test FilePart validation - cannot have both file_with_bytes and file_with_uri."""
        with pytest.raises(ValueError, match="cannot have both file_with_bytes and file_with_uri"):
            FilePart(
                name="test.txt",
                media_type="text/plain",
                file_with_bytes=b"content",
                file_with_uri="https://example.com/file.txt"
            )
    
    def test_file_part_to_base64(self):
        """Test Base64 encoding of inline file."""
        data = b"Hello, world!"
        part = FilePart(name="test.txt", media_type="text/plain", file_with_bytes=data)
        
        expected = base64.b64encode(data).decode("utf-8")
        assert part.to_base64() == expected
    
    def test_file_part_to_base64_remote(self):
        """Test Base64 encoding returns None for remote file."""
        part = FilePart(
            name="test.txt",
            media_type="text/plain",
            file_with_uri="https://example.com/file.txt"
        )
        assert part.to_base64() is None
    
    def test_file_part_from_base64(self):
        """Test creating FilePart from Base64 string."""
        original_data = b"Hello, world!"
        base64_data = base64.b64encode(original_data).decode("utf-8")
        
        part = FilePart.from_base64("test.txt", "text/plain", base64_data)
        
        assert part.name == "test.txt"
        assert part.media_type == "text/plain"
        assert part.file_with_bytes == original_data
        # Backward compat
        assert part.data == original_data


class TestDataPart:
    """Test cases for DataPart (AC-6).
    
    Uses A2A v0.3.0 spec field name: mediaType
    """
    
    def test_create_data_part(self):
        """Test basic DataPart creation."""
        data = {"key": "value", "number": 42}
        part = DataPart(data=data)
        
        assert part.data == data
        assert part.media_type == "application/json"
        # Backward compat
        assert part.mime_type == "application/json"
    
    def test_data_part_custom_media_type(self):
        """Test DataPart with custom media type."""
        data = {"key": "value"}
        part = DataPart(data=data, media_type="application/x-custom")
        
        assert part.media_type == "application/x-custom"
        assert part.mime_type == "application/x-custom"  # Backward compat
    
    def test_data_part_nested_structure(self):
        """Test DataPart with nested data structure."""
        data = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ],
            "metadata": {
                "total": 2,
                "page": 1
            }
        }
        part = DataPart(data=data)
        
        assert part.data["users"][0]["name"] == "Alice"
        assert part.data["metadata"]["total"] == 2


class TestTaskState:
    """Test cases for TaskState enum (A2A spec Section 4.1.3)."""
    
    def test_task_states(self):
        """Test all task states are defined per spec."""
        assert TaskState.SUBMITTED.value == "submitted"
        assert TaskState.WORKING.value == "working"
        assert TaskState.INPUT_REQUIRED.value == "input-required"
        assert TaskState.COMPLETED.value == "completed"
        assert TaskState.CANCELED.value == "canceled"
        assert TaskState.FAILED.value == "failed"
        assert TaskState.REJECTED.value == "rejected"
        assert TaskState.AUTH_REQUIRED.value == "auth-required"
        assert TaskState.UNKNOWN.value == "unknown"


class TestArtifact:
    """Test cases for Artifact (AC-7).
    
    Artifacts use artifactId (camelCase) in JSON per spec.
    """
    
    def test_create_artifact(self):
        """Test basic Artifact creation."""
        parts = [TextPart(text="Result content")]
        artifact = Artifact(
            artifact_id="test-id-123",
            name="Test Artifact",
            parts=parts
        )
        
        assert artifact.artifact_id == "test-id-123"
        assert artifact.name == "Test Artifact"
        assert len(artifact.parts) == 1
        assert isinstance(artifact.created_at, datetime)
    
    def test_artifact_create_factory(self):
        """Test Artifact.create() factory method."""
        parts = [TextPart(text="Result")]
        artifact = Artifact.create(name="Auto ID Artifact", parts=parts)
        
        assert artifact.artifact_id  # Should be auto-generated UUID
        assert artifact.name == "Auto ID Artifact"
        assert len(artifact.artifact_id) == 36  # UUID format
    
    def test_artifact_with_metadata(self):
        """Test Artifact with metadata."""
        parts = [TextPart(text="Content")]
        metadata = {"source": "test", "version": 1}
        
        artifact = Artifact.create(
            name="Metadata Artifact",
            parts=parts,
            metadata=metadata
        )
        
        assert artifact.metadata == metadata
    
    def test_artifact_with_multiple_parts(self):
        """Test Artifact with multiple part types."""
        parts = [
            TextPart(text="Analysis results"),
            DataPart(data={"score": 0.95}),
            FilePart(name="chart.png", media_type="image/png", file_with_bytes=b"...png data..."),
        ]
        
        artifact = Artifact.create(name="Multi-part Artifact", parts=parts)
        
        assert len(artifact.parts) == 3
        assert isinstance(artifact.parts[0], TextPart)
        assert isinstance(artifact.parts[1], DataPart)
        assert isinstance(artifact.parts[2], FilePart)
    
    def test_artifact_to_dict_camel_case(self):
        """Test Artifact serializes to camelCase per A2A spec."""
        parts = [TextPart(text="Content")]
        artifact = Artifact.create(
            name="Test Artifact",
            parts=parts,
            description="A test artifact",
            index=0,
        )
        
        d = artifact.to_dict()
        
        # Should use camelCase per A2A spec
        assert "artifactId" in d
        assert d["artifactId"] == artifact.artifact_id
        assert d["name"] == "Test Artifact"
        assert d["description"] == "A test artifact"
        assert d["index"] == 0
    
    def test_artifact_with_streaming_fields(self):
        """Test Artifact with append and lastChunk fields for streaming."""
        parts = [TextPart(text="Chunk 1")]
        artifact = Artifact(
            artifact_id="stream-123",
            name="Streaming Artifact",
            parts=parts,
            append=True,
            last_chunk=False,
        )
        
        d = artifact.to_dict()
        
        assert d["append"] is True
        assert d["lastChunk"] is False


class TestTypeConversion:
    """Test cases for type conversion utilities."""
    
    def test_string_to_parts(self):
        """Test converting string to parts."""
        parts = tyler_content_to_parts("Hello, world!")
        
        assert len(parts) == 1
        assert isinstance(parts[0], TextPart)
        assert parts[0].text == "Hello, world!"
    
    def test_dict_to_parts(self):
        """Test converting dict to parts."""
        data = {"key": "value"}
        parts = tyler_content_to_parts(data)
        
        assert len(parts) == 1
        assert isinstance(parts[0], DataPart)
        assert parts[0].data == data
    
    def test_bytes_to_parts(self):
        """Test converting bytes to parts."""
        data = b"binary content"
        parts = tyler_content_to_parts(data)
        
        assert len(parts) == 1
        assert isinstance(parts[0], FilePart)
        assert parts[0].file_with_bytes == data
        assert parts[0].data == data  # Backward compat
    
    def test_list_to_parts(self):
        """Test converting list to parts."""
        content = ["text1", "text2"]
        parts = tyler_content_to_parts(content)
        
        assert len(parts) == 2
        assert all(isinstance(p, TextPart) for p in parts)
    
    def test_parts_to_tyler_content(self):
        """Test converting parts back to Tyler content."""
        parts = [
            TextPart(text="Hello"),
            DataPart(data={"key": "value"}),
            FilePart(name="test.txt", media_type="text/plain", file_with_bytes=b"content"),
        ]
        
        result = parts_to_tyler_content(parts)
        
        assert result["text"] == ["Hello"]
        assert result["data"] == [{"key": "value"}]
        assert len(result["files"]) == 1
        # Check both new and legacy field names
        assert result["files"][0]["media_type"] == "text/plain"
        assert result["files"][0]["mime_type"] == "text/plain"
        assert result["files"][0]["file_with_bytes"] == b"content"
        assert result["files"][0]["data"] == b"content"
    
    def test_extract_text_from_parts(self):
        """Test extracting text from mixed parts."""
        parts = [
            TextPart(text="Line 1"),
            DataPart(data={"key": "value"}),
            TextPart(text="Line 2"),
        ]
        
        text = extract_text_from_parts(parts)
        
        assert text == "Line 1\nLine 2"


class TestConstants:
    """Test cases for module constants."""
    
    def test_max_file_size(self):
        """Test MAX_FILE_SIZE_BYTES constant."""
        assert MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024  # 10 MB
    
    def test_protocol_version(self):
        """Test A2A_PROTOCOL_VERSION constant (AC-1)."""
        assert A2A_PROTOCOL_VERSION == "0.3.0"
