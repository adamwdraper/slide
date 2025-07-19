import os
import weave
import base64
from typing import Dict, List, Optional, Any, Tuple
from litellm import speech, transcription
import uuid
import tempfile
from pathlib import Path

@weave.op(name="text-to-speech")
async def text_to_speech(*, 
    input: str,
    voice: str = "alloy",
    model: str = "tts-1",
    response_format: str = "mp3",
    speed: float = 1.0
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Convert text to speech using LiteLLM's speech API.

    Args:
        input (str): The text to convert to speech (max 4096 characters)
        voice (str, optional): The voice to use. Defaults to "alloy"
        model (str, optional): The model to use. Defaults to "tts-1"
        response_format (str, optional): The format of the audio file. Defaults to "mp3"
        speed (float, optional): The speed of the generated audio. Defaults to 1.0

    Returns:
        Tuple[Dict[str, Any], List[Dict[str, Any]]]: Tuple containing:
            - Dict with success status and metadata
            - List of file dictionaries with base64 encoded content and metadata
    """
    try:
        # Validate voice
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice not in valid_voices:
            return (
                {
                    "success": False,
                    "error": f"Voice {voice} not supported. Choose from: {valid_voices}"
                },
                []  # Empty files list for error case
            )

        # Validate model
        valid_models = ["tts-1", "tts-1-hd"]
        if not model.endswith(tuple(valid_models)) and model not in valid_models:
            # Allow for provider prefixes like "openai/tts-1"
            model_name = model.split('/')[-1]
            if model_name not in valid_models:
                return (
                    {
                        "success": False,
                        "error": f"Model {model} not supported. Choose from: {valid_models}"
                    },
                    []  # Empty files list for error case
                )

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{response_format}") as temp_file:
            temp_path = temp_file.name

        # Generate speech
        response = speech(
            model=model,
            voice=voice,
            input=input,
            response_format=response_format,
            speed=speed
        )
        
        # Stream to file
        response.stream_to_file(temp_path)
        
        # Read the file content
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        # Create a unique filename
        timestamp = uuid.uuid4().hex
        filename = f"speech_{timestamp}.{response_format}"
        
        # Determine mime type based on response_format
        mime_type_map = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac"
        }
        mime_type = mime_type_map.get(response_format, f"audio/{response_format}")
        
        # Create a short description
        description = f"Speech generated from text: '{input[:50]}{'...' if len(input) > 50 else ''}'"

        # Return tuple with content dict and files list
        return (
            {
                "success": True,
                "description": description,
            },
            [{
                "content": audio_bytes,  # Return raw bytes instead of base64 string
                "filename": filename,
                "mime_type": mime_type,
                "description": description,
                "attributes": {
                    "voice": voice,
                    "model": model,
                    "format": response_format,
                    "speed": speed,
                    "text_length": len(input)
                }
            }]
        )

    except Exception as e:
        return (
            {
                "success": False,
                "error": str(e)
            },
            []  # Empty files list for error case
        )

@weave.op(name="speech-to-text")
async def speech_to_text(*, 
    file_url: str,
    language: str = None,
    prompt: str = None
) -> Dict[str, Any]:
    """
    Transcribe speech to text using LiteLLM's transcription API.

    Args:
        file_url: Full path to the audio file
        language: Optional language code in ISO-639-1 format. If not specified, the model will auto-detect.
        prompt: Optional text to guide the model's style or continue a previous audio segment

    Returns:
        Dict[str, Any]: Dictionary with transcription results or error
    """
    try:
        # Use the file_url directly as the path
        file_path = Path(file_url)
            
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found at {file_path}")
            
        # Prepare optional parameters
        optional_params = {}
        if language:
            optional_params["language"] = language
        if prompt:
            optional_params["prompt"] = prompt
            
        # Open the file and transcribe
        with open(file_path, "rb") as audio_file:
            response = transcription(
                model="whisper-1",
                file=audio_file,
                **optional_params
            )
        
        # Extract the transcription text
        if isinstance(response, dict) and "text" in response:
            transcription_text = response["text"]
        elif hasattr(response, "text"):
            transcription_text = response.text
        else:
            transcription_text = str(response)
        
        return {
            "success": True,
            "text": transcription_text,
            "details": {
                "model": "whisper-1",
                "language": language,
                "file_url": file_url
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Define the tools list in the same format as other tool modules
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "text-to-speech",
                "description": "Converts text to speech audio using AI voices. Use this for generating spoken audio from text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "The text to convert to speech (max 4096 characters)"
                        },
                        "voice": {
                            "type": "string",
                            "description": "The voice to use for the speech",
                            "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                            "default": "alloy"
                        },
                        "model": {
                            "type": "string",
                            "description": "The model to use for speech generation",
                            "enum": ["tts-1", "tts-1-hd"],
                            "default": "tts-1"
                        },
                        "response_format": {
                            "type": "string",
                            "description": "The format of the audio file",
                            "enum": ["mp3", "opus", "aac", "flac"],
                            "default": "mp3"
                        },
                        "speed": {
                            "type": "number",
                            "description": "The speed of the generated audio (0.25 to 4.0)",
                            "minimum": 0.25,
                            "maximum": 4.0,
                            "default": 1.0
                        }
                    },
                    "required": ["input"]
                }
            }
        },
        "implementation": text_to_speech
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "speech-to-text",
                "description": "Transcribes speech from an audio file to text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_url": {
                            "type": "string",
                            "description": "URL or path to the audio file"
                        },
                        "language": {
                            "type": "string",
                            "description": "The language of the audio (ISO-639-1 format). If not specified, the model will auto-detect.",
                            "default": None
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Optional text to guide the model's style or continue a previous audio segment",
                            "default": None
                        }
                    },
                    "required": ["file_url"]
                }
            }
        },
        "implementation": speech_to_text
    }
] 