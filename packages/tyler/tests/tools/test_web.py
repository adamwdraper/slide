import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from tyler.tools.web import fetch_page, download_file, extract_text_from_html, fetch_html

# Mock responses
MOCK_HTML_CONTENT = """
<html>
    <head>
        <title>Test Page</title>
        <style>
            body { color: black; }
        </style>
        <script>
            console.log('test');
        </script>
    </head>
    <body>
        <h1>Test Header</h1>
        <p>Test paragraph</p>
        <div>Test div content</div>
    </body>
</html>
"""

MOCK_CLEAN_TEXT = """Test Header

Test paragraph

Test div content"""

@pytest.fixture(autouse=True)
def mock_requests():
    """Mock all requests to prevent any real API calls"""
    with patch('requests.get') as mock_get, patch('requests.head') as mock_head:
        mock_response = MagicMock()
        mock_response.text = MOCK_HTML_CONTENT
        mock_response.headers = {
            'content-type': 'text/html',
            'content-length': '1000'
        }
        mock_get.return_value = mock_response
        mock_head.return_value = mock_response
        yield mock_get, mock_head

@pytest.fixture
def mock_downloads_dir(tmp_path):
    """Create a temporary downloads directory"""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    with patch('tyler.utils.files.user_downloads_dir', return_value=str(downloads)):
        yield downloads

def test_fetch_html_success():
    """Test successful HTML fetching"""
    html = fetch_html("https://example.com")
    assert html == MOCK_HTML_CONTENT

def test_fetch_html_with_headers():
    """Test HTML fetching with custom headers"""
    headers = {"User-Agent": "Test Bot"}
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = MOCK_HTML_CONTENT
        mock_get.return_value = mock_response
        
        fetch_html("https://example.com", headers)
        
        mock_get.assert_called_with(
            "https://example.com",
            headers=headers,
            timeout=30
        )

def test_fetch_html_error():
    """Test error handling in fetch_html"""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Connection error")
        with pytest.raises(Exception, match="Error fetching URL: Connection error"):
            fetch_html("https://example.com")

def test_extract_text_from_html():
    """Test HTML to text extraction"""
    text = extract_text_from_html(MOCK_HTML_CONTENT)
    assert text == MOCK_CLEAN_TEXT

def test_fetch_page_text_format():
    """Test fetch_page with text format"""
    result = fetch_page(url="https://example.com", format="text")
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["content"] == MOCK_CLEAN_TEXT
    assert result["content_type"] == "text"
    assert result["error"] is None

def test_fetch_page_html_format():
    """Test fetch_page with HTML format"""
    result = fetch_page(url="https://example.com", format="html")
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["content"] == MOCK_HTML_CONTENT
    assert result["content_type"] == "html"
    assert result["error"] is None

def test_fetch_page_error():
    """Test fetch_page error handling"""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Test error")
        result = fetch_page(url="https://example.com")
        assert result["success"] is False
        assert result["status_code"] is None
        assert result["content"] is None
        assert result["content_type"] is None
        assert result["error"] == "Error fetching URL: Test error"

def test_download_file_success(mock_downloads_dir):
    """Test successful file download"""
    result, files = download_file(url="https://example.com/file.txt")
    
    assert result["success"] is True
    assert result["content_type"] == "text/html"
    assert result["file_size"] == 1000
    assert result["filename"] == "file.txt"
    assert len(files) == 1
    assert files[0]["filename"] == "file.txt"
    assert files[0]["mime_type"] == "text/html"
    assert "content" in files[0]
    assert "url" in files[0]["attributes"]

def test_download_file_with_content_disposition(mock_downloads_dir):
    """Test file download with Content-Disposition header"""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.headers = {
            'Content-Disposition': 'attachment; filename="server_file.txt"',
            'content-type': 'text/plain',
            'content-length': '1000'
        }
        mock_response.iter_content.return_value = [b'test content']
        mock_get.return_value = mock_response
        
        result, files = download_file(url="https://example.com/file")
        
        assert result["success"] is True
        assert result["filename"] == "server_file.txt"
        assert files[0]["filename"] == "server_file.txt"

def test_download_file_error():
    """Test download_file error handling"""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Download failed")
        result, files = download_file(url="https://example.com/file.txt")
        
        assert result["success"] is False
        assert "error" in result
        assert result["error"] == "Download failed"
        assert len(files) == 0 