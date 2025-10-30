"""Tyler configuration loading module.

This module provides public APIs for loading Tyler agent configuration from
YAML files, enabling the same configs to be used in both CLI and Python code.

Public API:
    - load_config(): Load and process a Tyler config file
    - load_custom_tool(): Load custom tools from a Python file
    - CONFIG_SEARCH_PATHS: Standard locations for config file discovery

Example:
    >>> from tyler.config import load_config
    >>> config = load_config("my-config.yaml")
    >>> agent = Agent(**config)
"""
import os
import re
import sys
import yaml
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Default config template
DEFAULT_CONFIG_TEMPLATE = """# Tyler Chat Configuration
# Save this file as tyler-chat-config.yaml in:
#   - Current directory
#   - ~/.tyler/chat-config.yaml
#   - /etc/tyler/chat-config.yaml
# Or specify location with: tyler chat --config path/to/config.yaml

# Agent Identity
name: "Tyler"
purpose: "To be a helpful AI assistant with access to various tools and capabilities."
notes: |
  - Prefer clear, concise communication
  - Use tools when appropriate to enhance responses
  - Maintain context across conversations

# Model Configuration
model_name: "gpt-4.1"
temperature: 0.7
max_tool_iterations: 10

# Tool Configuration
# List of tools to load. Can be:
#   - Built-in tool module names (e.g., "web", "files")
#   - Paths to Python files containing custom tools:
#     - "./my_tools.py"          # Relative to config file
#     - "~/tools/translate.py"    # User's home directory
#     - "/opt/tools/search.py"    # Absolute path
tools:
  - "web"           # Web search and browsing capabilities
  # - "slack"         # Slack integration tools
  # - "notion"        # Notion integration tools
  # - "command_line"  # System command execution tools
  # - "./my_tools.py"  # Example custom tools (uncomment to use)

# MCP (Model Context Protocol) Server Configuration
# Connect to external documentation, APIs, databases via MCP servers
# Uncomment to enable:
# mcp:
#   servers:
#     # Example: stdio-based server
#     - name: my-server
#       transport: stdio
#       command: npx
#       args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]
"""

# Standard locations for config file auto-discovery (in search order)
# Note: This is a template - actual paths computed at runtime in _get_search_paths()
CONFIG_SEARCH_PATHS: List[str] = [
    "./tyler-chat-config.yaml",      # Current directory
    "~/.tyler/chat-config.yaml",     # User home
    "/etc/tyler/chat-config.yaml"    # System-wide
]


def _get_search_paths() -> List[Path]:
    """Get config search paths (computed at runtime for current cwd/home).
    
    Returns:
        List of Path objects for config file search locations
    """
    return [
        Path.cwd() / "tyler-chat-config.yaml",
        Path.home() / ".tyler" / "chat-config.yaml",
        Path("/etc/tyler/chat-config.yaml")
    ]

# Regex pattern for environment variable substitution: ${VAR_NAME}
ENV_VAR_PATTERN = r'\$\{([^}]+)\}'


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and process a Tyler configuration file.
    
    Loads a YAML config file, performs environment variable substitution,
    and loads any custom tool files referenced in the config.
    
    Args:
        config_path: Path to YAML config file (.yaml or .yml extension).
                    If None, searches standard locations:
                    1. ./tyler-chat-config.yaml (current directory)
                    2. ~/.tyler/chat-config.yaml (user home)
                    3. /etc/tyler/chat-config.yaml (system-wide)
    
    Returns:
        Processed config dict ready for Agent(**config) with:
        - Environment variables substituted (${VAR_NAME} → value)
        - Custom tools loaded from referenced Python files
        - Relative paths resolved to config file directory
    
    Raises:
        FileNotFoundError: If explicit config_path doesn't exist
        ValueError: If no config found in standard locations (when path=None)
                   or if file extension is not .yaml/.yml
        yaml.YAMLError: If YAML syntax is invalid
    
    Example:
        >>> config = load_config("config.yaml")
        >>> config = load_config()  # Auto-discover
    """
    # Resolve config file path
    resolved_path = _resolve_config_path(config_path)
    
    # Validate file extension
    if resolved_path.suffix not in ['.yaml', '.yml']:
        raise ValueError(
            f"Config file must be .yaml or .yml, got {resolved_path.suffix}"
        )
    
    logger.info(f"Loading config from {resolved_path}")
    
    # Load YAML file
    try:
        with open(resolved_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in config file {resolved_path}: {e}")
        raise
    
    # Handle empty config file
    if config is None:
        config = {}
    
    # Substitute environment variables
    config = _substitute_env_vars(config)
    
    # Process tools list (load custom tool files)
    if 'tools' in config and isinstance(config['tools'], list):
        config['tools'] = _process_tools_list(config['tools'], resolved_path.parent)
    
    return config


def load_custom_tool(file_path: str, config_dir: Path) -> List[Dict]:
    """Load custom tools from a Python file.
    
    The Python file should define a TOOLS list containing tool definitions.
    Each tool is a dict with 'definition', 'implementation', and optional
    'attributes' keys.
    
    Args:
        file_path: Path to .py file (may be relative, absolute, or use ~)
        config_dir: Directory containing the config file (for relative path resolution)
    
    Returns:
        List of tool dicts from the TOOLS variable in the file
    
    Raises:
        ImportError: If module can't be loaded
        AttributeError: If TOOLS variable not found in module
    
    Example:
        >>> tools = load_custom_tool("./my_tools.py", Path("/path/to/config"))
    """
    # Resolve path
    tool_path = Path(file_path)
    
    # Handle home directory expansion first
    if file_path.startswith('~'):
        tool_path = tool_path.expanduser()
    # Handle absolute paths
    elif tool_path.is_absolute():
        tool_path = tool_path
    # Otherwise, treat as relative to config_dir
    else:
        tool_path = (config_dir / file_path).resolve()
    
    logger.debug(f"Loading custom tools from {tool_path}")
    
    # Get the module name from the file name
    module_name = tool_path.stem
    
    # Load the module from the file path
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if not spec or not spec.loader:
        raise ImportError(f"Could not load spec for {tool_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    
    # Get the TOOLS list from the module
    if not hasattr(module, 'TOOLS'):
        raise AttributeError(f"Module {module_name} must define a TOOLS list")
    
    tools = module.TOOLS
    logger.info(f"Loaded {len(tools)} custom tools from {tool_path}")
    
    return tools


def _prompt_create_config() -> Optional[Path]:
    """Prompt user to create a default config file.
    
    Returns:
        Path to created config file, or None if user declined
    """
    config_path = Path.cwd() / "tyler-chat-config.yaml"
    
    # Check if we're in an interactive terminal
    if not sys.stdin.isatty():
        logger.debug("Non-interactive terminal, skipping config creation prompt")
        return None
    
    try:
        print(f"\nNo config file found.")
        response = input(f"Create {config_path}? (Y/n): ").strip().lower()
        
        if response in ('', 'y', 'yes'):
            # Create the config file
            config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
            print(f"✓ Created {config_path}")
            print("💡 Remember to set your API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) in your environment")
            print()
            return config_path
        else:
            print("Config creation cancelled.")
            return None
    except (KeyboardInterrupt, EOFError):
        print("\nConfig creation cancelled.")
        return None


def _resolve_config_path(config_path: Optional[str]) -> Path:
    """Resolve config file path.
    
    If config_path provided: validate it exists and return Path
    If None: search standard locations and return first found
    
    Args:
        config_path: Optional explicit path to config file
    
    Returns:
        Resolved Path to config file
    
    Raises:
        FileNotFoundError: If explicit path doesn't exist
        ValueError: If no config found in standard locations
    """
    if config_path:
        # Explicit path provided
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return path
    
    # Auto-discovery: search standard locations (computed at runtime)
    search_paths = _get_search_paths()
    logger.debug(f"Searching for config in: {search_paths}")
    
    for location in search_paths:
        if location.exists():
            logger.debug(f"Found config at {location}")
            return location
        else:
            logger.debug(f"Config not found at {location}")
    
    # No config found - prompt to create one
    created_path = _prompt_create_config()
    if created_path:
        return created_path
    
    # User declined or non-interactive - show error
    searched = ", ".join(str(p) for p in search_paths)
    raise ValueError(
        f"No config file found in standard locations: {searched}"
    )


def _substitute_env_vars(obj: Any) -> Any:
    """Recursively substitute environment variables in config values.
    
    Supports ${VAR_NAME} syntax. Multiple variables in one string are supported.
    Missing variables are left as-is (returns original ${VAR_NAME}).
    
    Args:
        obj: Config object (dict, list, str, or other)
    
    Returns:
        Object with environment variables substituted
    
    Example:
        >>> _substitute_env_vars({"key": "${MY_VAR}"})
        {"key": "value_from_env"}
    """
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Substitute environment variables using ${VAR_NAME} pattern
        def replacer(match):
            var_name = match.group(1)
            value = os.getenv(var_name)
            if value is None:
                logger.warning(f"Environment variable {var_name} not found, using literal value")
                return match.group(0)  # Return original ${VAR_NAME}
            return value
        
        return re.sub(ENV_VAR_PATTERN, replacer, obj)
    
    return obj


def _process_tools_list(tools: List[Any], config_dir: Path) -> List[Any]:
    """Process tools list: load custom files, pass through built-ins.
    
    For each tool in the list:
    - If string with path chars ('/', '.py', '~'): load as custom tool file
    - Otherwise: pass through unchanged (built-in module name or dict)
    
    Args:
        tools: List of tools from config (strings, dicts, etc.)
        config_dir: Directory containing config file (for relative paths)
    
    Returns:
        Processed tools list with custom tools loaded
    
    Example:
        >>> _process_tools_list(["web", "./my_tools.py"], Path("/config"))
        ["web", {...tool_dict...}]
    """
    processed_tools = []
    
    for tool in tools:
        if isinstance(tool, str):
            # Check if it looks like a file path
            if any(c in tool for c in ['/', '.py', '~']):
                # It's a custom tool file - load it
                try:
                    custom_tools = load_custom_tool(tool, config_dir)
                    processed_tools.extend(custom_tools)
                except Exception as e:
                    # Log warning but continue (matches CLI behavior)
                    logger.warning(f"Failed to load custom tool from {tool}: {e}")
            else:
                # It's a built-in tool module name - pass through
                processed_tools.append(tool)
        else:
            # Non-string items (like dicts) pass through unchanged
            processed_tools.append(tool)
    
    return processed_tools

