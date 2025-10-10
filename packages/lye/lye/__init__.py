"""
Lye - Tools package for Tyler
"""
__version__ = "1.0.0"

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

# Lazy-load tool modules to avoid import errors for optional dependencies
_MODULES_LOADED = {}

def _load_module_tools(module_name: str) -> List:
    """Lazy load tools from a module"""
    if module_name in _MODULES_LOADED:
        return _MODULES_LOADED[module_name]
    
    try:
        module = importlib.import_module(f".{module_name}", package="lye")
        tools = getattr(module, "TOOLS", [])
        _MODULES_LOADED[module_name] = tools
        return tools
    except ImportError as e:
        logger.debug(f"Could not import {module_name}: {e}")
        _MODULES_LOADED[module_name] = []
        return []
    except Exception as e:
        logger.debug(f"Could not load tools from {module_name}: {e}")
        _MODULES_LOADED[module_name] = []
        return []

# Lazy-load tools on access
def _get_web_tools():
    if not WEB_TOOLS:
        WEB_TOOLS.extend(_load_module_tools("web"))
    return WEB_TOOLS

def _get_slack_tools():
    if not SLACK_TOOLS:
        SLACK_TOOLS.extend(_load_module_tools("slack"))
    return SLACK_TOOLS

def _get_command_line_tools():
    if not COMMAND_LINE_TOOLS:
        COMMAND_LINE_TOOLS.extend(_load_module_tools("command_line"))
    return COMMAND_LINE_TOOLS

def _get_notion_tools():
    if not NOTION_TOOLS:
        NOTION_TOOLS.extend(_load_module_tools("notion"))
    return NOTION_TOOLS

def _get_image_tools():
    if not IMAGE_TOOLS:
        IMAGE_TOOLS.extend(_load_module_tools("image"))
    return IMAGE_TOOLS

def _get_audio_tools():
    if not AUDIO_TOOLS:
        AUDIO_TOOLS.extend(_load_module_tools("audio"))
    return AUDIO_TOOLS

def _get_files_tools():
    if not FILES_TOOLS:
        FILES_TOOLS.extend(_load_module_tools("files"))
    return FILES_TOOLS

def _get_browser_tools():
    if not BROWSER_TOOLS:
        BROWSER_TOOLS.extend(_load_module_tools("browser"))
    return BROWSER_TOOLS

def _get_wandb_tools():
    if not WANDB_TOOLS:
        WANDB_TOOLS.extend(_load_module_tools("wandb_workspaces"))
    return WANDB_TOOLS

# Custom dict class that lazy loads tools on access
class LazyToolModules(dict):
    """Dictionary that lazy loads tool modules on access"""
    
    _loaders = {
        'web': _get_web_tools,
        'slack': _get_slack_tools,
        'command_line': _get_command_line_tools,
        'notion': _get_notion_tools,
        'image': _get_image_tools,
        'audio': _get_audio_tools,
        'files': _get_files_tools,
        'browser': _get_browser_tools,
        'wandb_workspaces': _get_wandb_tools,
    }
    
    def __getitem__(self, key):
        if key in self._loaders:
            return self._loaders[key]()
        raise KeyError(key)
    
    def items(self):
        """Return all module names and their tools"""
        for key in self._loaders:
            yield key, self[key]
    
    def keys(self):
        """Return all module names"""
        return self._loaders.keys()
    
    def values(self):
        """Return all tool lists"""
        for key in self._loaders:
            yield self[key]
    
    def __contains__(self, key):
        return key in self._loaders
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

# Map of module names to their tools for dynamic loading
TOOL_MODULES = LazyToolModules()

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
    'TOOL_MODULES',
]
