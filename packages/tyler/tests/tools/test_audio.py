import pytest
import os
import uuid
from unittest.mock import patch, MagicMock, mock_open
from tyler.tools.audio import text_to_speech, speech_to_text
from pathlib import Path

# Mock UUID to ensure consistent filenames in tests
@pytest.fixture(autouse=True)
def mock_uuid():
    """Mock UUID to return a consistent value for testing"""
    with patch('uuid.uuid4', return_value=MagicMock(hex='test_uuid_hex')):
        yield

@pytest.fixture
def mock_speech_response():
    """Mock response for LiteLLM's speech function"""
    mock_resp = MagicMock()
    mock_resp.stream_to_file = MagicMock()
    return mock_resp

@pytest.fixture
def mock_audio_bytes():
    """Mock audio bytes for testing"""
    return b"fake audio data"

@pytest.fixture
def mock_transcription_response():
    """Mock response for LiteLLM's transcription function"""
    return {
        "text": "This is a transcribed text from audio."
    }

@pytest.mark.asyncio
async def test_text_to_speech_success(mock_speech_response, mock_audio_bytes):
    """Test successful text to speech conversion"""
    # Create mocks
    with patch('tyler.tools.audio.speech', return_value=mock_speech_response) as mock_speech, \
         patch('tempfile.NamedTemporaryFile') as mock_temp, \
         patch('os.unlink') as mock_unlink, \
         patch('builtins.open', mock_open(read_data=mock_audio_bytes)):
        
        # Configure the mock temp file
        mock_temp_instance = MagicMock()
        mock_temp_instance.name = "/tmp/test_audio.mp3"
        mock_temp.return_value.__enter__.return_value = mock_temp_instance
        
        # Call the function
        result = await text_to_speech(
            input="Hello, this is a test.",
            voice="alloy",
            model="tts-1",
            response_format="mp3",
            speed=1.0
        )
        
        # Verify the mocks were called correctly
        mock_speech.assert_called_once_with(
            model="tts-1",
            voice="alloy",
            input="Hello, this is a test.",
            response_format="mp3",
            speed=1.0
        )
        mock_speech_response.stream_to_file.assert_called_once_with(mock_temp_instance.name)
        mock_unlink.assert_called_once_with(mock_temp_instance.name)
        
        # Check result structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        # Check content dict
        content, files = result
        assert content["success"] is True
        assert "description" in content
        assert "Speech generated from text: 'Hello, this is a test.'" == content["description"]
        
        # Check files list
        assert isinstance(files, list)
        assert len(files) == 1
        file_info = files[0]
        assert file_info["content"] == mock_audio_bytes
        assert file_info["filename"] == "speech_test_uuid_hex.mp3"
        assert file_info["mime_type"] == "audio/mpeg"
        assert file_info["description"] == "Speech generated from text: 'Hello, this is a test.'"
        
        # Check details moved to file attributes
        assert "attributes" in file_info
        assert file_info["attributes"]["voice"] == "alloy"
        assert file_info["attributes"]["model"] == "tts-1"
        assert file_info["attributes"]["format"] == "mp3"
        assert file_info["attributes"]["speed"] == 1.0
        assert file_info["attributes"]["text_length"] == len("Hello, this is a test.")

@pytest.mark.asyncio
async def test_text_to_speech_invalid_voice():
    """Test text to speech with invalid voice parameter"""
    # No need to mock API calls for validation tests as they should fail before any API call
    result = await text_to_speech(
        input="Hello, this is a test.",
        voice="invalid_voice",  # Invalid voice
        model="tts-1",
        response_format="mp3",
        speed=1.0
    )
    
    # Check error response
    content, files = result
    assert content["success"] is False
    assert "error" in content
    assert "Voice invalid_voice not supported" in content["error"]
    assert len(files) == 0

@pytest.mark.asyncio
async def test_text_to_speech_invalid_model():
    """Test text to speech with invalid model parameter"""
    # No need to mock API calls for validation tests as they should fail before any API call
    result = await text_to_speech(
        input="Hello, this is a test.",
        voice="alloy",
        model="invalid-model",  # Invalid model
        response_format="mp3",
        speed=1.0
    )
    
    # Check error response
    content, files = result
    assert content["success"] is False
    assert "error" in content
    assert "Model invalid-model not supported" in content["error"]
    assert len(files) == 0

@pytest.mark.asyncio
async def test_text_to_speech_exception():
    """Test text to speech with an exception during processing"""
    with patch('tyler.tools.audio.speech', side_effect=Exception("Test exception")):
        result = await text_to_speech(
            input="Hello, this is a test.",
            voice="alloy",
            model="tts-1",
            response_format="mp3",
            speed=1.0
        )
        
        # Check error response
        content, files = result
        assert content["success"] is False
        assert "error" in content
        assert "Test exception" in content["error"]
        assert len(files) == 0

@pytest.mark.asyncio
async def test_speech_to_text_success(mock_transcription_response):
    """Test successful speech to text conversion"""
    file_path = "/path/to/audio.mp3"
    
    # Create a mock Path object that exists
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    
    with patch('tyler.tools.audio.Path', return_value=mock_path), \
         patch('builtins.open', mock_open()), \
         patch('tyler.tools.audio.transcription', return_value=mock_transcription_response) as mock_transcribe:
        
        result = await speech_to_text(
            file_url=file_path,
            language="en",
            prompt="This is a test prompt"
        )
        
        # Verify the mock was called correctly
        mock_transcribe.assert_called_once()
        
        # Check result
        assert result["success"] is True
        assert result["text"] == "This is a transcribed text from audio."
        assert "details" in result
        assert result["details"]["model"] == "whisper-1"
        assert result["details"]["language"] == "en"
        assert result["details"]["file_url"] == file_path

@pytest.mark.asyncio
async def test_speech_to_text_file_not_found():
    """Test speech to text with file not found"""
    file_path = "/path/to/nonexistent.mp3"
    
    # Create a mock Path object that doesn't exist
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = False
    
    with patch('tyler.tools.audio.Path', return_value=mock_path):
        result = await speech_to_text(file_url=file_path)
        
        # Check error response
        assert result["success"] is False
        assert "error" in result
        assert "Audio file not found" in result["error"]

@pytest.mark.asyncio
async def test_speech_to_text_exception():
    """Test speech to text with an exception during processing"""
    file_path = "/path/to/audio.mp3"
    
    # Create a mock Path object that exists
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    
    with patch('tyler.tools.audio.Path', return_value=mock_path), \
         patch('builtins.open', mock_open()), \
         patch('tyler.tools.audio.transcription', side_effect=Exception("Test exception")):
        
        result = await speech_to_text(file_url=file_path)
        
        # Check error response
        assert result["success"] is False
        assert "error" in result
        assert "Test exception" in result["error"] 