import requests
import weave
import base64
from typing import Optional, Dict, List, Any, Tuple
from bs4 import BeautifulSoup
from tyler.utils.files import save_to_downloads
from pathlib import Path
from urllib.parse import urlparse

def fetch_html(url: str, headers: Optional[Dict] = None) -> str:
    """
    Fetches the HTML content from the given URL.
    
    Args:
        url (str): The URL to fetch the HTML from
        headers (Dict, optional): Headers to send with the request
    
    Returns:
        str: The HTML content of the page
    
    Raises:
        Exception: If there's an error fetching the URL
    """
    try:
        response = requests.get(url, headers=headers or {}, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        raise Exception(f"Error fetching URL: {e}")

def extract_text_from_html(html_content: str) -> str:
    """
    Extracts clean, readable text from HTML content.
    
    Args:
        html_content (str): The HTML content to parse
    
    Returns:
        str: The extracted text content
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script, style, and title elements
    for element in soup(["script", "style", "title"]):
        element.decompose()
    
    # Get text with better spacing
    text = soup.get_text(separator='\n', strip=True)
    
    # Clean up excessive newlines while preserving paragraph structure
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = '\n\n'.join(lines)
    
    return text

@weave.op(name="web-download_file")
def download_file(*, url: str, headers: Optional[Dict] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Download a file from a URL and return it as a file object.

    Args:
        url (str): The URL of the file to download
        headers (Dict, optional): Headers to send with the request

    Returns:
        Tuple[Dict[str, Any], List[Dict[str, Any]]]: Tuple containing:
            - Dict with success status and metadata
            - List of file dictionaries with base64 encoded content and metadata
    """
    try:
        # Download the file with streaming
        response = requests.get(url, headers=headers or {}, stream=True, timeout=30)
        response.raise_for_status()
        
        # Get content info
        content_type = response.headers.get('content-type', 'unknown')
        file_size = int(response.headers.get('content-length', 0))
        content_disposition = response.headers.get('Content-Disposition')
        
        # Download content
        content = b''.join(chunk for chunk in response.iter_content(chunk_size=8192) if chunk)
        
        # Determine filename from content-disposition or URL
        filename = ""
        if content_disposition:
            import re
            if match := re.search(r'filename="?([^"]+)"?', content_disposition):
                filename = match.group(1)
        
        if not filename:
            parsed_url = urlparse(url)
            path = parsed_url.path
            if path and '/' in path:
                filename = path.split('/')[-1]
                # Remove query parameters if they got included
                if '?' in filename:
                    filename = filename.split('?')[0]
        
        # Fall back to default if still no filename
        if not filename:
            filename = 'downloaded_file'
            
            # Try to add extension based on content type
            if content_type and content_type != 'unknown' and '/' in content_type:
                ext = content_type.split('/')[-1]
                if ext and '.' not in filename:
                    filename = f"{filename}.{ext}"
        
        # Base64 encode the content
        base64_content = base64.b64encode(content).decode('utf-8')
        
        # Return tuple with content dict and files list
        return (
            {
                "success": True,
                "content_type": content_type,
                "file_size": file_size,
                "filename": filename,
                "error": None
            },
            [{
                "content": base64_content,
                "filename": filename,
                "mime_type": content_type,
                "description": f"Downloaded file from {url}",
                "attributes": {
                    "url": url,
                    "file_size": file_size,
                    "content_disposition": content_disposition
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

@weave.op(name="web-fetch_page")
def fetch_page(*, url: str, format: str = "text", headers: Optional[Dict] = None) -> Dict:
    """
    Fetch content from a web page and return it in the specified format.

    Args:
        url (str): The URL to fetch
        format (str): Output format - either 'text' or 'html'
        headers (Dict, optional): Headers to send with the request

    Returns:
        Dict: Contains status code, content, and any error messages
    """
    try:
        html_content = fetch_html(url, headers)
        
        content = extract_text_from_html(html_content) if format == "text" else html_content
        
        return {
            'success': True,
            'status_code': 200,
            'content': content,
            'content_type': format,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'status_code': None,
            'content': None,
            'content_type': None,
            'error': str(e)
        }

TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "web-fetch_page",
                "description": "Fetches content from a web page and returns it in a clean, readable format with preserved structure.  Use the 'text' format any time you are looking for the content of a page, on only use 'html' when you need the raw HTML content of a page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch"
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format - either 'text' or 'html'.  Specify 'text' any time you are looking for the content of a page, on only use 'html' when you need the raw HTML content of a page.",
                            "enum": ["text", "html"],
                            "default": "text"
                        },
                        "headers": {
                            "type": "object",
                            "description": "Optional headers to send with the request"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        "implementation": fetch_page
    },
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "web-download_file",
                "description": "Downloads a file from a URL and returns it as a file object.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL of the file to download"
                        },
                        "headers": {
                            "type": "object",
                            "description": "Optional headers to send with the request"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        "implementation": download_file
    }
]
