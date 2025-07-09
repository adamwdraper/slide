"""
Slack blocks utilities for Space Monkey bot framework
"""

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

async def convert_to_slack_blocks(text: str, thread_ts: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert markdown text to Slack blocks format
    
    Args:
        text: The text to convert (may contain markdown)
        thread_ts: Optional thread timestamp for context
        
    Returns:
        Dict containing 'blocks' (for rich formatting) and 'text' (fallback)
    """
    try:
        # For now, implement basic markdown to Slack conversion
        # This is a simplified version - a full implementation would handle more markdown features
        
        blocks = []
        
        # Split text into sections (separated by double newlines)
        sections = text.split('\n\n')
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Check if this is a code block
            if section.startswith('```') and section.endswith('```'):
                # Code block
                code_content = section[3:-3].strip()
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```\n{code_content}\n```"
                    }
                })
            else:
                # Regular text section - convert some basic markdown
                formatted_text = _convert_basic_markdown(section)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": formatted_text
                    }
                })
        
        # If no blocks were created, create a simple text block
        if not blocks:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            })
        
        return {
            "blocks": blocks,
            "text": text  # Fallback text for notifications and accessibility
        }
        
    except Exception as e:
        logger.error(f"Error converting to Slack blocks: {e}")
        # Return fallback format on error
        return {
            "blocks": [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }],
            "text": text
        }

def _convert_basic_markdown(text: str) -> str:
    """
    Convert basic markdown formatting to Slack's mrkdwn format
    
    Args:
        text: Text potentially containing markdown
        
    Returns:
        Text with Slack-compatible formatting
    """
    # Convert **bold** to *bold*
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    
    # Convert _italic_ to _italic_ (already compatible)
    # Convert `code` to `code` (already compatible)
    
    # Convert [link text](url) to <url|link text>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
    
    # Convert ### Header to *Header*
    text = re.sub(r'^### (.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convert ## Header to *Header*
    text = re.sub(r'^## (.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convert # Header to *Header*
    text = re.sub(r'^# (.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convert bullet points (- or *) to Slack format
    text = re.sub(r'^[\-\*] (.+)$', r'• \1', text, flags=re.MULTILINE)
    
    # Convert numbered lists
    text = re.sub(r'^(\d+)\. (.+)$', r'\1. \2', text, flags=re.MULTILINE)
    
    return text

def create_simple_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Create simple Slack blocks from plain text
    
    Args:
        text: Plain text to convert
        
    Returns:
        List of Slack block objects
    """
    return [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text
        }
    }]

def create_error_blocks(error_message: str) -> List[Dict[str, Any]]:
    """
    Create error-formatted Slack blocks
    
    Args:
        error_message: Error message to display
        
    Returns:
        List of Slack block objects formatted for errors
    """
    return [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f":warning: *Error:* {error_message}"
        }
    }]

def create_info_blocks(info_message: str) -> List[Dict[str, Any]]:
    """
    Create info-formatted Slack blocks
    
    Args:
        info_message: Info message to display
        
    Returns:
        List of Slack block objects formatted for info
    """
    return [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f":information_source: {info_message}"
        }
    }] 