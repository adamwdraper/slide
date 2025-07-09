import pytest
from tyler.tools.image import generate_image, analyze_image
import base64
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

@pytest.fixture
def mock_image_response():
    """Mock response that matches litellm's image_generation format"""
    return {
        "created": 1234567890,
        "data": [{
            "url": "https://example.com/image.png",
            "revised_prompt": "A beautiful test image",
            "model": "dall-e-3"
        }]
    }

@pytest.fixture
def mock_image_bytes():
    return b"fake image data"

@pytest.fixture
def mock_completion_response():
    """Mock response for GPT-4V completion"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is an image of a test scene."
    return mock_response

@pytest.mark.asyncio
async def test_generate_image_success(mock_image_response, mock_image_bytes):
    """Test successful image generation with new tuple return format"""
    # Create a mock for litellm.image_generation
    mock_generation = MagicMock(return_value=mock_image_response)
    
    with patch('tyler.tools.image.image_generation', mock_generation), \
         patch('httpx.AsyncClient') as mock_client:
        # Mock the HTTP response for image download
        mock_response = AsyncMock()
        mock_response.content = mock_image_bytes
        mock_response.raise_for_status = AsyncMock()
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await generate_image(prompt="test image")
        
        # Verify litellm was called with correct parameters
        mock_generation.assert_called_once_with(
            prompt="test image",
            model="dall-e-3",
            n=1,
            size="1024x1024",
            quality="standard",
            style="vivid",
            response_format="url"
        )
        
        # Check tuple structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        # Check content dict
        content, files = result
        assert isinstance(content, dict)
        assert content["success"] is True
        assert content["description"] == mock_image_response["data"][0]["revised_prompt"]
        
        # Check files list
        assert isinstance(files, list)
        assert len(files) == 1
        file_info = files[0]
        assert file_info["content"] == base64.b64encode(mock_image_bytes).decode('utf-8')
        assert file_info["filename"] == f"generated_image_{mock_image_response['created']}.png"
        assert file_info["mime_type"] == "image/png"
        assert file_info["description"] == mock_image_response["data"][0]["revised_prompt"]
        
        # Check details moved to file attributes
        assert "attributes" in file_info
        assert file_info["attributes"]["size"] == "1024x1024"
        assert file_info["attributes"]["quality"] == "standard"
        assert file_info["attributes"]["style"] == "vivid"
        assert file_info["attributes"]["created"] == mock_image_response["created"]
        assert file_info["attributes"]["prompt"] == "test image"
        assert file_info["attributes"]["model"] == "dall-e-3"

@pytest.mark.asyncio
async def test_generate_image_error():
    """Test error handling with new tuple return format"""
    # Test with invalid size to trigger error
    result = await generate_image(prompt="test", size="invalid")
    
    # Check tuple structure
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    # Check error content
    content, files = result
    assert isinstance(content, dict)
    assert content["success"] is False
    assert "error" in content
    assert "Size invalid not supported" in content["error"]
    
    # Check files is empty list for error case
    assert isinstance(files, list)
    assert len(files) == 0

@pytest.mark.asyncio
async def test_generate_image_parameters(mock_image_response, mock_image_bytes):
    """Test image generation with different parameters"""
    # Create a mock for litellm.image_generation
    mock_generation = MagicMock(return_value=mock_image_response)
    
    with patch('tyler.tools.image.image_generation', mock_generation), \
         patch('httpx.AsyncClient') as mock_client:
        # Mock the HTTP response for image download
        mock_response = AsyncMock()
        mock_response.content = mock_image_bytes
        mock_response.raise_for_status = AsyncMock()
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await generate_image(
            prompt="test image",
            size="1024x1024",
            quality="hd",
            style="natural"
        )
        
        # Verify litellm was called with correct parameters
        mock_generation.assert_called_once_with(
            prompt="test image",
            model="dall-e-3",
            n=1,
            size="1024x1024",
            quality="hd",
            style="natural",
            response_format="url"
        )
        
        # Check content
        content, files = result
        assert content["success"] is True
        
        # Check file was generated
        assert len(files) == 1
        file_info = files[0]
        assert file_info["mime_type"] == "image/png"
        
        # Check details moved to file attributes
        assert "attributes" in file_info
        assert file_info["attributes"]["size"] == "1024x1024"
        assert file_info["attributes"]["quality"] == "hd"
        assert file_info["attributes"]["style"] == "natural"
        assert file_info["attributes"]["created"] == mock_image_response["created"]
        assert file_info["attributes"]["prompt"] == "test image"
        assert file_info["attributes"]["model"] == "dall-e-3"

@pytest.mark.asyncio
async def test_generate_image_no_data():
    """Test handling when no image data is received"""
    # Create a mock response with empty data
    mock_response = {
        "created": 1234567890,
        "data": []
    }
    
    with patch('tyler.tools.image.image_generation', return_value=mock_response):
        result = await generate_image(prompt="test image")
        
        # Check error response
        content, files = result
        assert content["success"] is False
        assert "No image data received" in content["error"]
        assert len(files) == 0

@pytest.mark.asyncio
async def test_generate_image_no_url():
    """Test handling when no URL is in the response"""
    # Create a mock response with data but no URL
    mock_response = {
        "created": 1234567890,
        "data": [{"revised_prompt": "A test image"}]  # No URL
    }
    
    with patch('tyler.tools.image.image_generation', return_value=mock_response):
        result = await generate_image(prompt="test image")
        
        # Check error response
        content, files = result
        assert content["success"] is False
        assert "No image URL in response" in content["error"]
        assert len(files) == 0

@pytest.mark.asyncio
async def test_generate_image_http_error():
    """Test handling when HTTP request fails"""
    mock_response = {
        "created": 1234567890,
        "data": [{
            "url": "https://example.com/image.png",
            "revised_prompt": "A test image"
        }]
    }
    
    with patch('tyler.tools.image.image_generation', return_value=mock_response), \
         patch('httpx.AsyncClient') as mock_client:
        # Mock HTTP error
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=Exception("HTTP error"))
        mock_client.return_value.__aenter__.return_value = mock_http_client
        
        result = await generate_image(prompt="test image")
        
        # Check error response
        content, files = result
        assert content["success"] is False
        assert "HTTP error" in content["error"]
        assert len(files) == 0

@pytest.mark.asyncio
async def test_analyze_image_success(mock_completion_response):
    """Test successful image analysis"""
    # Create a temporary file path
    file_path = "/tmp/test_image.jpg"
    
    with patch('tyler.tools.image.Path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('tyler.tools.image.completion', return_value=mock_completion_response):
        
        # Mock file reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = b"test image data"
        with patch('builtins.open', return_value=mock_file):
            result = await analyze_image(file_url=file_path)
            
            # Check success response
            assert result["success"] is True
            assert result["analysis"] == "This is an image of a test scene."
            assert result["file_url"] == file_path

@pytest.mark.asyncio
async def test_analyze_image_with_prompt(mock_completion_response):
    """Test image analysis with a custom prompt"""
    file_path = "/tmp/test_image.jpg"
    custom_prompt = "Describe the colors in this image"
    
    with patch('tyler.tools.image.Path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('tyler.tools.image.completion', return_value=mock_completion_response) as mock_completion:
        
        # Mock file reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = b"test image data"
        with patch('builtins.open', return_value=mock_file):
            result = await analyze_image(file_url=file_path, prompt=custom_prompt)
            
            # Verify the custom prompt was used
            called_messages = mock_completion.call_args[1]['messages']
            assert called_messages[0]['content'][0]['text'] == custom_prompt
            
            # Check success response
            assert result["success"] is True
            assert result["analysis"] == "This is an image of a test scene."

@pytest.mark.asyncio
async def test_analyze_image_file_not_found():
    """Test handling when image file is not found"""
    file_path = "/tmp/nonexistent_image.jpg"
    
    with patch('tyler.tools.image.Path.exists', return_value=False):
        result = await analyze_image(file_url=file_path)
        
        # Check error response
        assert result["success"] is False
        assert "Image file not found" in result["error"]
        assert result["file_url"] == file_path

@pytest.mark.asyncio
async def test_analyze_image_api_error():
    """Test handling when the vision API call fails"""
    file_path = "/tmp/test_image.jpg"
    
    with patch('tyler.tools.image.Path.exists', return_value=True), \
         patch('builtins.open', MagicMock()), \
         patch('tyler.tools.image.completion', side_effect=Exception("API error")):
        
        # Mock file reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = b"test image data"
        with patch('builtins.open', return_value=mock_file):
            result = await analyze_image(file_url=file_path)
            
            # Check error response
            assert result["success"] is False
            assert "API error" in result["error"]
            assert result["file_url"] == file_path 