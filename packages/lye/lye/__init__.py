"""
Lye - Tools package for Tyler
"""
__version__ = "5.2.1"

import importlib
import sys
import os
import glob
from typing import Dict, List
from lye.utils.logging import get_logger

# Get configured logger
logger = get_logger(__name__)

# Lazy-load tool modules to avoid import errors for optional dependencies
_MODULES_LOADED = {}

# Internal storage for tool lists (populated on first access)
_WEB_TOOLS = []
_SLACK_TOOLS = []
_COMMAND_LINE_TOOLS = []
_NOTION_TOOLS = []
_IMAGE_TOOLS = []
_AUDIO_TOOLS = []
_FILES_TOOLS = []
_BROWSER_TOOLS = []
_WANDB_TOOLS = []

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
    if not _WEB_TOOLS:
        _WEB_TOOLS.extend(_load_module_tools("web"))
    return _WEB_TOOLS

def _get_slack_tools():
    if not _SLACK_TOOLS:
        _SLACK_TOOLS.extend(_load_module_tools("slack"))
    return _SLACK_TOOLS

def _get_command_line_tools():
    if not _COMMAND_LINE_TOOLS:
        _COMMAND_LINE_TOOLS.extend(_load_module_tools("command_line"))
    return _COMMAND_LINE_TOOLS

def _get_notion_tools():
    if not _NOTION_TOOLS:
        _NOTION_TOOLS.extend(_load_module_tools("notion"))
    return _NOTION_TOOLS

def _get_image_tools():
    if not _IMAGE_TOOLS:
        _IMAGE_TOOLS.extend(_load_module_tools("image"))
    return _IMAGE_TOOLS

def _get_audio_tools():
    if not _AUDIO_TOOLS:
        _AUDIO_TOOLS.extend(_load_module_tools("audio"))
    return _AUDIO_TOOLS

def _get_files_tools():
    if not _FILES_TOOLS:
        _FILES_TOOLS.extend(_load_module_tools("files"))
    return _FILES_TOOLS

def _get_browser_tools():
    if not _BROWSER_TOOLS:
        _BROWSER_TOOLS.extend(_load_module_tools("browser"))
    return _BROWSER_TOOLS

def _get_wandb_tools():
    if not _WANDB_TOOLS:
        _WANDB_TOOLS.extend(_load_module_tools("wandb_workspaces"))
    return _WANDB_TOOLS

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

# Module-level __getattr__ to make tool list imports trigger lazy loading
def __getattr__(name):
    """Intercept attribute access to trigger lazy loading for tool lists"""
    if name == 'WEB_TOOLS':
        return _get_web_tools()
    elif name == 'SLACK_TOOLS':
        return _get_slack_tools()
    elif name == 'COMMAND_LINE_TOOLS':
        return _get_command_line_tools()
    elif name == 'NOTION_TOOLS':
        return _get_notion_tools()
    elif name == 'IMAGE_TOOLS':
        return _get_image_tools()
    elif name == 'AUDIO_TOOLS':
        return _get_audio_tools()
    elif name == 'FILES_TOOLS':
        return _get_files_tools()
    elif name == 'BROWSER_TOOLS':
        return _get_browser_tools()
    elif name == 'WANDB_TOOLS':
        return _get_wandb_tools()
    elif name == 'TOOLS':
        # TOOLS is a combined list of all tools - load everything
        all_tools = []
        for getter in [_get_web_tools, _get_files_tools, _get_command_line_tools,
                      _get_audio_tools, _get_image_tools, _get_browser_tools,
                      _get_slack_tools, _get_notion_tools, _get_wandb_tools]:
            all_tools.extend(getter())
        return all_tools
    raise AttributeError(f"module 'lye' has no attribute '{name}'")
