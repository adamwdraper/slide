from typing import Optional, Dict
from pathlib import Path
from platformdirs import user_downloads_dir
from urllib.parse import urlparse, unquote

def get_unique_filepath(base_path: Path) -> Path:
    """
    Get a unique file path by adding a number suffix if the file already exists.
    
    Args:
        base_path (Path): The initial file path to check
        
    Returns:
        Path: A unique file path that doesn't exist
    """
    if not base_path.exists():
        return base_path
        
    directory = base_path.parent
    stem = base_path.stem
    suffix = base_path.suffix
    counter = 1
    
    while True:
        new_path = directory / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

def save_to_downloads(*, content: bytes, filename: str = "", content_disposition: Optional[str] = None, url: Optional[str] = None) -> Dict:
    """
    Save content to the user's Downloads directory with proper filename handling.

    Args:
        content (bytes): The content to save
        filename (str): Optional filename to save as
        content_disposition (str, optional): Content-Disposition header value for filename extraction
        url (str, optional): Original URL to extract filename from if not provided

    Returns:
        Dict: Contains file path and filename information
    """
    try:
        # Use standard Downloads directory
        downloads_dir = Path(user_downloads_dir())
        
        # Get filename from different sources in order of priority:
        # 1. Explicitly provided filename
        # 2. Content-Disposition header
        # 3. URL path
        # 4. Default fallback
        if not filename:
            if content_disposition:
                import re
                if match := re.search(r'filename="?([^"]+)"?', content_disposition):
                    filename = match.group(1)
            elif url:
                parsed_url = urlparse(url)
                path = unquote(parsed_url.path)
                if path and '/' in path:
                    filename = path.split('/')[-1]
                    # Remove query parameters if they got included
                    if '?' in filename:
                        filename = filename.split('?')[0]
        
        # Fall back to default if still no filename
        if not filename:
            filename = 'downloaded_file'
        
        # Create full file path and ensure it's unique
        initial_path = downloads_dir / filename
        file_path = get_unique_filepath(initial_path)
        
        # Write the file
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return {
            'success': True,
            'file_path': str(file_path),
            'filename': file_path.name,  # Use the potentially modified filename
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'file_path': None,
            'filename': None,
            'error': str(e)
        } 