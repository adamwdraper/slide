"""
Lye - Tools package for Tyler
"""
__version__ = "0.3.0"

import importlib
import sys
import os
import glob
from typing import Dict, List
from lye.utils.logging import get_logger

# Get configured logger
logger = get_logger(__name__)

# Initialize empty tool lists for each module
WEB_TOOLS = []
SLACK_TOOLS = []
COMMAND_LINE_TOOLS = []
NOTION_TOOLS = []
IMAGE_TOOLS = []
AUDIO_TOOLS = []
FILES_TOOLS = []
BROWSER_TOOLS = []
WANDB_TOOLS = []

# Combined tools list
TOOLS = []

# Try to import each tool module
try:
    from . import web
    from . import slack
    from . import command_line
    from . import notion
    from . import image
    from . import audio
    from . import files
    from . import browser
    from . import wandb_workspaces
    
except ImportError as e:
    print(f"Warning: Some tool modules could not be imported: {e}")

# Get tool lists from each module and maintain both individual and combined lists
try:
    module_tools = getattr(web, "TOOLS", [])
    WEB_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load web tools: {e}")

try:
    module_tools = getattr(slack, "TOOLS", [])
    SLACK_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load slack tools: {e}")

try:
    module_tools = getattr(command_line, "TOOLS", [])
    COMMAND_LINE_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load command line tools: {e}")

try:
    module_tools = getattr(notion, "TOOLS", [])
    NOTION_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load notion tools: {e}")

try:
    module_tools = getattr(image, "TOOLS", [])
    IMAGE_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load image tools: {e}")

try:
    module_tools = getattr(audio, "TOOLS", [])
    AUDIO_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load audio tools: {e}")

try:
    module_tools = getattr(files, "TOOLS", [])
    FILES_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load files tools: {e}")

try:
    module_tools = getattr(browser, "TOOLS", [])
    BROWSER_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load browser tools: {e}")

try:
    module_tools = getattr(wandb_workspaces, "TOOLS", [])
    WANDB_TOOLS.extend(module_tools)
    TOOLS.extend(module_tools)
except Exception as e:
    print(f"Warning: Could not load wandb workspace tools: {e}")

    __all__ = [
        # Module-level tool lists
        'TOOLS',
        'WEB_TOOLS',
        'FILES_TOOLS',
        'COMMAND_LINE_TOOLS',
        'AUDIO_TOOLS',
        'IMAGE_TOOLS',
        'BROWSER_TOOLS',
        'SLACK_TOOLS',
        'NOTION_TOOLS',
        'WANDB_TOOLS',
        # Module namespaces for cleaner imports
        'web',
        'files',
        'command_line',
        'audio',
        'image',
        'browser',
        'slack',
        'notion',
        'wandb_workspaces',
    ]

# Map of module names to their tools for dynamic loading
TOOL_MODULES: Dict[str, List] = {
    'web': WEB_TOOLS,
    'slack': SLACK_TOOLS,
    'command_line': COMMAND_LINE_TOOLS,
    'notion': NOTION_TOOLS,
    'image': IMAGE_TOOLS,
    'audio': AUDIO_TOOLS,
    'files': FILES_TOOLS,
    'browser': BROWSER_TOOLS,
    'wandb_workspaces': WANDB_TOOLS
}
