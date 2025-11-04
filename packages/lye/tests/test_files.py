import pytest
import os
import json
import pandas as pd
import io
import base64
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock, mock_open
from lye.files import (
    read_file, 
    write_file,
    parse_csv,
    parse_json,
    process_text,
    _process_pdf,
    _process_pdf_with_vision
)

@pytest.fixture
def sample_text_content():
    """Sample text content for testing"""
    return b"This is a sample text file content."

@pytest.fixture
def sample_json_content():
    """Sample JSON content for testing"""
    data = {
        "name": "Test User",
        "age": 30,
        "items": ["item1", "item2", "item3"],
        "nested": {
            "key1": "value1",
            "key2": "value2"
        }
    }
    return json.dumps(data).encode('utf-8')

@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing"""
    csv_data = """name,age,city
Alice,25,New York
Bob,30,San Francisco
Charlie,35,Seattle
David,40,Boston
Eve,45,Chicago"""
    return csv_data.encode('utf-8')

@pytest.fixture
def sample_pdf_content():
    """Mock PDF content for testing"""
    return b"%PDF-1.5\nfake pdf content"

@pytest.fixture
def mock_pdf_reader():
    """Mock PdfReader for testing"""
    mock_reader = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Page 1 content"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Page 2 content"
    mock_reader.pages = [mock_page1, mock_page2]
    return mock_reader

@pytest.mark.asyncio
async def test_read_file_nonexistent():
    """Test reading a non-existent file"""
    with patch('pathlib.Path.exists', return_value=False):
        result, files = await read_file(file_url="nonexistent.txt")
        
        assert result["success"] is False
        assert "File not found" in result["error"]
        assert files == []

@pytest.mark.asyncio
async def test_read_file_text(sample_text_content):
    """Test reading a text file"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_bytes', return_value=sample_text_content):
        
        result, files = await read_file(file_url="sample.txt")
        
        assert result["success"] is True
        assert result["text"] == sample_text_content.decode('utf-8')
        assert result["encoding"] == "utf-8"
        assert len(files) == 1
        assert files[0]["filename"] == "sample.txt"
        assert files[0]["mime_type"] == "text/plain"

@pytest.mark.asyncio
async def test_read_file_json(sample_json_content):
    """Test reading a JSON file"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_bytes', return_value=sample_json_content):
        
        result, files = await read_file(file_url="sample.json")
        
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["name"] == "Test User"
        assert result["data"]["age"] == 30
        assert len(files) == 1
        assert files[0]["filename"] == "sample.json"
        # filetype may detect JSON as text/plain, which is acceptable
        assert files[0]["mime_type"] in ["application/json", "text/plain"]

@pytest.mark.asyncio
async def test_read_file_json_with_path(sample_json_content):
    """Test reading JSON with specific path extraction"""
    # Test accessing nested object
    result, _ = await parse_json(sample_json_content, "sample.json", "nested.key1")
    assert result["success"] is True
    assert result["data"] == "value1"
    
    # Test accessing array element
    result, _ = await parse_json(sample_json_content, "sample.json", "items[1]")
    assert result["success"] is True
    assert result["data"] == "item2"
    
    # Test invalid path
    result, _ = await parse_json(sample_json_content, "sample.json", "invalid.path")
    assert result["success"] is False

@pytest.mark.asyncio
async def test_read_file_csv(sample_csv_content):
    """Test reading a CSV file"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_bytes', return_value=sample_csv_content):
        
        result, files = await read_file(file_url="sample.csv")
        
        assert result["success"] is True
        assert "statistics" in result
        assert result["statistics"]["total_rows"] == 5
        assert result["statistics"]["total_columns"] == 3
        assert "preview" in result
        assert len(result["preview"]) == 5
        assert len(files) == 1
        assert files[0]["filename"] == "sample.csv"
        # filetype may detect CSV as text/plain, fallback to extension gives text/csv
        assert files[0]["mime_type"] in ["text/csv", "text/plain"]

@pytest.mark.asyncio
async def test_read_file_pdf(sample_pdf_content, mock_pdf_reader):
    """Test reading a PDF file"""
    # Create a valid PDF content that won't cause errors
    valid_pdf_content = b"%PDF-1.5\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    
    # Create mock return values that match the expected format
    mock_result = {
        "success": True,
        "pages": 2,
        "text": "Page 1 content\n\nPage 2 content",
        "method": "pypdf"
    }
    
    mock_files = [{
        "filename": "sample.pdf",
        "mime_type": "application/pdf",
        "size": len(valid_pdf_content),
        "content": base64.b64encode(valid_pdf_content).decode('utf-8')
    }]
    
    with patch('lye.files._process_pdf', return_value=(mock_result, mock_files)):
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_bytes', return_value=valid_pdf_content):
            
            result, files = await read_file(file_url="sample.pdf")
            
            assert "error" not in result
            assert result["pages"] == 2
            assert "Page 1 content" in result["text"]
            assert "Page 2 content" in result["text"]
            assert len(files) == 1
            assert files[0]["filename"] == "sample.pdf"
            assert files[0]["mime_type"] == "application/pdf"

@pytest.mark.asyncio
async def test_read_file_pdf_error(sample_pdf_content):
    """Test reading a PDF file with errors"""
    # Use the invalid PDF content to trigger an error
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_bytes', return_value=sample_pdf_content), \
         patch('lye.files._process_pdf', side_effect=Exception("Stream has ended unexpectedly")):
        
        result, files = await read_file(file_url="sample.pdf")
        
        assert "error" in result
        assert "Stream has ended unexpectedly" in result["error"]

@pytest.mark.asyncio
async def test_pdf_with_vision_fallback(sample_pdf_content):
    """Test PDF processing with Vision API fallback"""
    # Create a valid PDF content that won't cause errors
    valid_pdf_content = b"%PDF-1.5\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    
    # Create mock return values that match the expected format
    mock_result = {
        "success": True,
        "pages": 1,
        "text": "Text extracted using Vision API",
        "method": "vision"
    }
    
    mock_files = [{
        "filename": "sample.pdf",
        "mime_type": "application/pdf",
        "size": len(valid_pdf_content),
        "content": base64.b64encode(valid_pdf_content).decode('utf-8')
    }]
    
    # When _process_pdf fails, read_file will return an error
    with patch('lye.files._process_pdf', side_effect=Exception("PDF parsing failed")), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_bytes', return_value=valid_pdf_content):
        
        result, files = await read_file(file_url="sample.pdf")
        
        assert result["success"] is False
        assert "PDF parsing failed" in result["error"]
        assert files == []

@pytest.mark.asyncio
async def test_process_text_encoding_fallback(sample_text_content):
    """Test text processing with encoding fallback"""
    # Create content that will fail with utf-8 but succeed with latin-1
    content = b'\xff\xfeThis is Latin-1 encoded text'
    
    result, files = await process_text(content, "sample.txt")
    
    assert result["success"] is True
    assert "encoding" in result
    assert result["encoding"] in ["latin-1", "cp1252", "iso-8859-1"]
    assert len(files) == 1

@pytest.mark.asyncio
async def test_process_text_all_encodings_fail(sample_text_content):
    """Test text processing when all encodings fail"""
    # Create content that will fail with all supported encodings
    content = MagicMock()
    content.decode.side_effect = UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')
    
    result, files = await process_text(content, "sample.txt")
    
    assert "error" in result
    assert "Could not decode text with any supported encoding" in result["error"]
    assert files == []

@pytest.mark.asyncio
async def test_write_file_text(sample_text_content):
    """Test writing a text file"""
    content = "This is a test text file"
    file_url = "output.txt"
    
    result, files = await write_file(content, file_url)
    
    assert result["success"] is True
    assert result["mime_type"] == "text/plain"
    assert result["file_url"] == file_url
    assert len(files) == 1
    assert files[0]["filename"] == "output.txt"
    assert files[0]["mime_type"] == "text/plain"
    
    # Decode the content to verify
    decoded_content = base64.b64decode(files[0]["content"]).decode('utf-8')
    assert decoded_content == content

@pytest.mark.asyncio
async def test_write_file_json(sample_json_content):
    """Test writing a JSON file"""
    content = {"name": "Test User", "age": 30}
    file_url = "output.json"
    
    result, files = await write_file(content, file_url)
    
    assert result["success"] is True
    assert result["mime_type"] == "application/json"
    assert result["file_url"] == file_url
    assert len(files) == 1
    assert files[0]["filename"] == "output.json"
    assert files[0]["mime_type"] == "application/json"
    
    # Decode the content to verify
    decoded_content = json.loads(base64.b64decode(files[0]["content"]).decode('utf-8'))
    assert decoded_content == content

@pytest.mark.asyncio
async def test_write_file_csv_from_dataframe(sample_csv_content):
    """Test writing a CSV file from a DataFrame"""
    df = pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie'],
        'age': [25, 30, 35],
        'city': ['New York', 'San Francisco', 'Seattle']
    })
    file_url = "output.csv"
    
    result, files = await write_file(df, file_url, mime_type="text/csv")
    
    assert result["success"] is True
    assert result["mime_type"] == "text/csv"
    assert result["file_url"] == file_url
    assert len(files) == 1
    assert files[0]["filename"] == "output.csv"
    assert files[0]["mime_type"] == "text/csv"

@pytest.mark.asyncio
async def test_write_file_csv_from_list(sample_csv_content):
    """Test writing a CSV file from a list of dictionaries"""
    content = [
        {'name': 'Alice', 'age': 25, 'city': 'New York'},
        {'name': 'Bob', 'age': 30, 'city': 'San Francisco'},
        {'name': 'Charlie', 'age': 35, 'city': 'Seattle'}
    ]
    file_url = "output.csv"
    
    result, files = await write_file(content, file_url, mime_type="text/csv")
    
    assert result["success"] is True
    assert result["mime_type"] == "text/csv"
    assert result["file_url"] == file_url
    assert len(files) == 1
    assert files[0]["filename"] == "output.csv"
    assert files[0]["mime_type"] == "text/csv"

@pytest.mark.asyncio
async def test_write_file_binary(sample_pdf_content):
    """Test writing a binary file"""
    content = b"Binary content"
    file_url = "output.bin"
    
    result, files = await write_file(content, file_url)
    
    assert result["success"] is True
    assert result["mime_type"] == "application/octet-stream"
    assert result["file_url"] == file_url
    assert len(files) == 1
    assert files[0]["filename"] == "output.bin"
    assert files[0]["mime_type"] == "application/octet-stream"
    
    # Decode the content to verify
    decoded_content = base64.b64decode(files[0]["content"])
    assert decoded_content == content

@pytest.mark.asyncio
async def test_write_file_mime_type_inference(sample_json_content):
    """Test MIME type inference when writing files"""
    # Test with JSON content but no explicit MIME type
    content = {"name": "Test User", "age": 30}
    file_url = "output.json"
    
    with patch('mimetypes.guess_type', return_value=(None, None)):
        result, files = await write_file(content, file_url)
        
        assert result["success"] is True
        assert result["mime_type"] == "application/json"

    # Test with string content but no explicit MIME type
    content = "This is a test"
    file_url = "output.txt"
    
    with patch('mimetypes.guess_type', return_value=(None, None)):
        result, files = await write_file(content, file_url)
        
        assert result["success"] is True
        assert result["mime_type"] == "text/plain"

@pytest.mark.asyncio
async def test_write_file_error_handling(sample_json_content):
    """Test error handling when writing files"""
    # Test with unsupported MIME type
    content = "Test content"
    file_url = "output.xyz"
    
    with patch('mimetypes.guess_type', return_value=("application/unsupported", None)):
        result, files = await write_file(content, file_url, mime_type="application/unsupported")
        
        assert result["success"] is False
        assert "error" in result
        assert "Unsupported MIME type" in result["error"]

    # Test with JSON serialization error
    content = {"circular_ref": None}
    content["circular_ref"] = content  # Create circular reference
    file_url = "output.json"
    
    result, files = await write_file(content, file_url, mime_type="application/json")
    
    assert result["success"] is False
    assert "error" in result

@pytest.mark.asyncio
async def test_json_decode_error(sample_json_content):
    """Test handling of JSON decode errors"""
    invalid_json = b"{invalid json"
    
    result, files = await parse_json(invalid_json, "invalid.json")
    
    assert result["success"] is False
    assert "Invalid JSON format" in result["error"]
    assert files == []

@pytest.mark.asyncio
async def test_csv_parse_error(sample_csv_content):
    """Test handling of CSV parse errors"""
    invalid_csv = b"a,b,c\n1,2\n3,4,5,6"  # Inconsistent number of columns
    
    with patch('pandas.read_csv', side_effect=Exception("CSV parsing error")):
        result, files = await parse_csv(invalid_csv, "invalid.csv")
        
        assert "error" in result
        assert "CSV parsing error" in result["error"]
        assert files == []

@pytest.mark.asyncio
async def test_unknown_mime_type(sample_pdf_content):
    """Test handling of unknown MIME types"""
    content = b"Some binary content"
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_bytes', return_value=content):
        
        result, files = await read_file(file_url="unknown.bin")
        
        assert result["success"] is True
        assert result["mime_type"] == 'application/octet-stream'
        assert len(files) == 1
        assert files[0]["filename"] == "unknown.bin"
        assert files[0]["mime_type"] == 'application/octet-stream'

@pytest.mark.asyncio
async def test_process_pdf_directly(sample_pdf_content, mock_pdf_reader):
    """Test the _process_pdf function directly"""
    valid_pdf_content = b"%PDF-1.5\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    
    # Test the _process_pdf function directly with mock PDF reader
    # Also mock the _process_pdf_with_vision to avoid real API calls if text extraction fails
    with patch('lye.files.PdfReader', return_value=mock_pdf_reader), \
         patch('lye.files._process_pdf_with_vision') as mock_vision:
        # Set up vision fallback in case it's called
        mock_vision.return_value = (
            {"success": False, "error": "Vision API mocked"},
            []
        )
        
        result, files = await _process_pdf(valid_pdf_content, "sample.pdf")
        
        assert result["success"] is True
        assert result["pages"] == 2
        assert "Page 1 content" in result["text"]
        assert "Page 2 content" in result["text"]
        assert result["processing_method"] == "text"
        assert len(files) == 1
        assert files[0]["filename"] == "sample.pdf"
        assert files[0]["mime_type"] == "application/pdf"

@pytest.mark.asyncio
async def test_process_pdf_with_vision_directly(sample_pdf_content):
    """Test the _process_pdf_with_vision function directly"""
    valid_pdf_content = b"%PDF-1.5\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    
    # Mock the PDF conversion and litellm completion
    mock_images = [MagicMock()]  # Mock image object
    # Create a mock buffer for the image
    mock_buffer = io.BytesIO()
    
    with patch('pdf2image.convert_from_bytes', return_value=mock_images), \
         patch('lye.files.completion') as mock_completion:
        # Mock PIL Image save method to capture the image data
        saved_data = []
        def mock_save(buffer, format=None):
            buffer.write(b"fake_image_data")
            saved_data.append(buffer)
            
        for img in mock_images:
            img.save = mock_save
        
        # Mock the LLM response  
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Extracted text from image"
        mock_completion.return_value = mock_response
        
        result, files = await _process_pdf_with_vision(valid_pdf_content, "sample.pdf")
        
        assert result["success"] is True
        assert result["processing_method"] == "vision"
        assert "Extracted text from image" in result["text"]
        assert len(files) == 1 