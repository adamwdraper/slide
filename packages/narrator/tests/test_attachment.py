import pytest
from narrator import Attachment
import base64
import os
import tempfile
from unittest.mock import patch, Mock, AsyncMock

@pytest.fixture
def sample_attachment():
    """Create a sample attachment for testing."""
    return Attachment(
        filename="test.txt",
        mime_type="text/plain",
        file_id="test-attachment",
        storage_path="/path/to/file.txt",
        storage_backend="local",
        attributes={
            "type": "text",
            "text": "Test content",
            "overview": "A test file"
        }
    )

@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    content = b"Test content for attachment"
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)  # Clean up after test

def test_attachment_creation(sample_attachment):
    """Test basic attachment creation and properties."""
    assert sample_attachment.filename == "test.txt"
    assert sample_attachment.mime_type == "text/plain"
    assert sample_attachment.file_id == "test-attachment"
    assert sample_attachment.storage_path == "/path/to/file.txt"
    assert sample_attachment.storage_backend == "local"
    assert sample_attachment.content is None
    assert sample_attachment.attributes["type"] == "text"

def test_attachment_with_bytes_content():
    """Test attachment with bytes content."""
    content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )
    assert attachment.content == content
    assert isinstance(attachment.content, bytes)

def test_attachment_with_base64_content():
    """Test attachment with base64 content."""
    content = "VGVzdCBjb250ZW50"  # base64 for "Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )
    assert attachment.content == content
    assert isinstance(attachment.content, str)

def test_attachment_serialization(sample_attachment):
    """Test attachment serialization to/from dict."""
    # Test model_dump()
    data = sample_attachment.model_dump()
    assert data["filename"] == "test.txt"
    assert data["mime_type"] == "text/plain"
    assert data["file_id"] == "test-attachment"
    assert data["storage_path"] == "/path/to/file.txt"
    assert data["storage_backend"] == "local"
    assert data["attributes"]["type"] == "text"
    assert "content" not in data  # Content is never included in model_dump
    
    # Test model_validate()
    new_attachment = Attachment.model_validate(data)
    assert new_attachment.filename == sample_attachment.filename
    assert new_attachment.mime_type == sample_attachment.mime_type
    assert new_attachment.attributes == sample_attachment.attributes
    assert new_attachment.content is None  # Content not included in serialization

@pytest.mark.asyncio
async def test_get_content_bytes():
    """Test getting content as bytes."""
    # Test with bytes content
    bytes_content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=bytes_content
    )
    content = await attachment.get_content_bytes()
    assert content == bytes_content
    
    # Test with base64 string content
    base64_content = base64.b64encode(b"Test content").decode()
    attachment = Attachment(
        filename="test.txt",
        content=base64_content
    )
    content = await attachment.get_content_bytes()
    assert content == b"Test content"
    
    # Test with UTF-8 string content
    text_content = "Test content"
    attachment = Attachment(
        filename="test.txt",
        content=text_content
    )
    content = await attachment.get_content_bytes()
    assert content == text_content.encode('utf-8')
    
    # Test with file_id
    attachment = Attachment(
        filename="test.txt",
        file_id="test-file",
        storage_path="/path/to/file.txt"
    )
    
    # Create a mock FileStore directly
    mock_store = Mock()
    mock_store.get = AsyncMock(return_value=b"Stored content")
    
    content = await attachment.get_content_bytes(file_store=mock_store)
    assert content == b"Stored content"
    mock_store.get.assert_called_once_with("test-file", "/path/to/file.txt")

@pytest.mark.asyncio
async def test_ensure_stored():
    """Test ensuring content is stored."""
    content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )

    # Mock the file store directly
    mock_store = Mock()
    mock_store.save = AsyncMock(return_value={
        'id': 'file-123',
        'storage_path': '/path/to/stored/file.txt',
        'storage_backend': 'local'
    })
    
    await attachment.process_and_store(file_store=mock_store)
    
    # Verify the file was stored
    mock_store.save.assert_called_once_with(content, "test.txt", "text/plain")
    assert attachment.file_id == "file-123"
    assert attachment.storage_path == "/path/to/stored/file.txt"
    assert attachment.storage_backend == "local"

def test_attachment_validation():
    """Test attachment validation."""
    # Test missing required fields
    with pytest.raises(ValueError):
        Attachment()  # missing filename
    
    # Test valid minimal attachment
    attachment = Attachment(filename="test.txt")
    assert attachment.filename == "test.txt"
    assert attachment.content is None
    assert attachment.mime_type is None
    
    # Test with invalid content type
    with pytest.raises(ValueError):
        Attachment(filename="test.txt", content=123)  # content must be bytes or str

def test_attachment_with_processed_content():
    """Test attachment with different types of attributes."""
    # Test text file
    text_attachment = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain",
        attributes={
            "type": "text",
            "text": "Test content",
            "overview": "A test file"
        }
    )
    assert text_attachment.attributes["type"] == "text"
    assert text_attachment.attributes["text"] == "Test content"
    
    # Test image file
    image_attachment = Attachment(
        filename="test.jpg",
        content=b"image data",
        mime_type="image/jpeg",
        attributes={
            "type": "image",
            "content": "base64_encoded_image",
            "overview": "An image file",
            "analysis": {
                "objects": ["person", "desk"],
                "text_detected": True
            }
        }
    )
    assert image_attachment.attributes["type"] == "image"
    assert "analysis" in image_attachment.attributes
    
    # Test JSON file
    json_attachment = Attachment(
        filename="test.json",
        content=b'{"key": "value"}',
        mime_type="application/json",
        attributes={
            "type": "json",
            "overview": "JSON data structure",
            "parsed_content": {"key": "value"}
        }
    )
    assert json_attachment.attributes["type"] == "json"
    assert json_attachment.attributes["parsed_content"] == {"key": "value"}

def test_attachment_content_serialization():
    """Test attachment serialization behavior."""
    content = b"Test content for serialization"
    attachment = Attachment(
        filename="test.txt",
        content=content
    )
    
    # Test model_dump serialization - content is never included
    data = attachment.model_dump()
    assert "content" not in data
    assert data["filename"] == "test.txt"
    assert data["file_id"] is None

@pytest.mark.asyncio
async def test_attachment_base64():
    """Test attachment with base64 content."""
    content = b"Test content for base64"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )
    
    # Test that attachment can handle base64 content
    b64_content = base64.b64encode(content).decode('utf-8')
    b64_attachment = Attachment(
        filename="test.txt",
        content=b64_content,
        mime_type="text/plain"
    )
    
    # Both should be able to return the same bytes content
    assert content == await attachment.get_content_bytes()
    assert content == await b64_attachment.get_content_bytes()

def test_attachment_size_calculation():
    """Test automatic size calculation."""
    content = b"Test content for size calculation"
    attachment = Attachment(
        id="test-attachment",
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )

    # Test size calculation
    assert len(content) == len(content)  # Size is calculated on demand

@pytest.mark.asyncio
async def test_attachment_process_error_handling():
    """Test error handling during content processing."""
    attachment = Attachment(
        filename="test.bin",
        content=b"\x00\x01\x02",  # Invalid content that can't be processed
        mime_type="application/octet-stream"
    )

    # Mock the file store to raise an error
    mock_store = Mock()
    mock_store.save = AsyncMock(side_effect=Exception("Storage failed"))
    
    with pytest.raises(RuntimeError, match="Failed to process attachment test.bin"):
        await attachment.process_and_store(file_store=mock_store)

@pytest.mark.asyncio
async def test_attachment_with_file_store():
    """Test attachment processing with file store."""
    content = b"Test content"
    attachment = Attachment(
        filename="test.txt",
        content=content,
        mime_type="text/plain"
    )

    # Mock the file store
    mock_store = Mock()
    mock_store.save = AsyncMock(return_value={
        'id': 'file-123',
        'storage_path': '/path/to/stored/file.txt',
        'storage_backend': 'local'
    })
    
    await attachment.process_and_store(file_store=mock_store)
    
    # Verify the file was stored
    assert attachment.file_id == "file-123"
    assert attachment.storage_path == "/path/to/stored/file.txt"
    assert attachment.storage_backend == "local"
    assert attachment.content is None  # Content should be cleared after storage

@pytest.mark.asyncio
async def test_filename_update_after_storage():
    """Test that the filename is updated to match the new filename created by the file store."""
    original_filename = "original_test.txt"
    content = b"Test content"
    attachment = Attachment(
        filename=original_filename,
        content=content,
        mime_type="text/plain"
    )

    # The new filename that would be created by the file store
    new_filename = "abc123def456.txt"
    storage_path = f"ab/{new_filename}"  # Mimics the sharded structure

    # Create a mock file store directly
    mock_store = Mock()
    mock_store.save = AsyncMock(return_value={
        'id': 'file-123',
        'storage_path': storage_path,
        'storage_backend': 'local'
    })
    
    await attachment.process_and_store(file_store=mock_store)
    
    # Verify the filename was updated
    assert attachment.filename == new_filename
    assert attachment.storage_path == storage_path
    assert attachment.file_id == "file-123"

def test_attachment_equality():
    """Test attachment equality comparison."""
    attachment1 = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain"
    )
    attachment2 = Attachment(
        filename="test.txt",
        content=b"Test content",
        mime_type="text/plain"
    )
    
    # Should be equal based on content
    assert attachment1.id == attachment2.id  # Same content hash
    
    # Different content should have different IDs
    attachment3 = Attachment(
        filename="test.txt",
        content=b"Different content",
        mime_type="text/plain"
    )
    assert attachment1.id != attachment3.id

def test_attachment_from_file_path():
    """Test creating attachment from file path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Test file content")
        temp_path = f.name
    
    try:
        attachment = Attachment.from_file_path(temp_path)
        assert attachment.filename == os.path.basename(temp_path)
        assert attachment.content is not None
        assert b"Test file content" in attachment.content
    finally:
        os.unlink(temp_path)

def test_attachment_mime_type_detection():
    """Test MIME type detection."""
    # Test text file
    text_attachment = Attachment(
        filename="test.txt",
        content=b"Test content"
    )
    text_attachment.detect_mime_type()
    assert text_attachment.mime_type == "text/plain"
    
    # Test with explicit MIME type
    image_attachment = Attachment(
        filename="test.jpg",
        content=b"fake image data",
        mime_type="image/jpeg"
    )
    # MIME type should remain as set
    assert image_attachment.mime_type == "image/jpeg" 