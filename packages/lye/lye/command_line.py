import os
import glob
import subprocess
import shutil
from pathlib import Path
import weave
from typing import Dict, Any, List

# Whitelist of safe commands and their descriptions
SAFE_COMMANDS = {
    # Navigation and read operations (unrestricted)
    "ls": "List directory contents",
    "pwd": "Print working directory",
    "cd": "Change directory",
    "cat": "Display file contents",
    "find": "Search for files by name",
    "grep": "Search for patterns in files",
    "tree": "Display directory structure as a tree",
    "wc": "Count lines/words/characters in files",
    "head": "Display first lines of files",
    "tail": "Display last lines of files",
    "diff": "Compare files line by line",
    "sleep": "Pause execution for testing",
    
    # File manipulation operations (restricted to workspace)
    "mkdir": "Create a new directory",
    "touch": "Create a new empty file",
    "rm": "Remove a file or empty directory",
    "cp": "Copy a file",
    "mv": "Move/rename a file",
    "echo": "Write text to a file (using > or >>)",
    "sed": "Edit text in files using pattern matching"
}

# Commands that can modify files (these need path validation)
FILE_MODIFYING_COMMANDS = {
    "mkdir", "touch", "rm", "cp", "mv", "echo", "sed"
}

def is_safe_path(path: str) -> bool:
    """Validates if a path is safe to access by checking if it's within the workspace."""
    try:
        # Handle None or empty path
        if not path or not isinstance(path, str):
            return False
            
        # Handle whitespace-only paths
        if path.strip() == "":
            return False
            
        # Check for null bytes which could be used for path traversal attacks
        if "\0" in path:
            return False
            
        abs_path = os.path.abspath(path)
        workspace_root = os.path.abspath(os.getcwd())
        return abs_path.startswith(workspace_root)
    except Exception:
        return False

def validate_file_operation(command: str, parts: List[str]) -> bool:
    """Additional validation for file manipulation commands."""
    try:
        base_cmd = parts[0]
        
        if base_cmd == "rm":
            # Don't allow recursive removal or force flags
            if any(arg in ["-r", "-rf", "-fr", "--recursive", "-R"] for arg in parts):
                return False
            # Validate target path
            target = parts[-1]
            return is_safe_path(target)
            
        elif base_cmd in ["cp", "mv"]:
            # Validate both source and destination paths
            if len(parts) != 3:
                return False
            return is_safe_path(parts[1]) and is_safe_path(parts[2])
            
        elif base_cmd == "echo":
            # Check for redirection to file
            if ">" in parts:
                redirect_idx = parts.index(">")
                file_path = parts[redirect_idx + 1]
                return is_safe_path(file_path)
            return True
            
        elif base_cmd == "sed":
            # Only allow -i for in-place editing
            if "-i" in parts:
                file_path = parts[-1]
                return is_safe_path(file_path)
            return True
            
        elif base_cmd in ["mkdir", "touch"]:
            # Validate target path
            target = parts[-1]
            return is_safe_path(target)
            
        return True
        
    except Exception:
        return False

def is_safe_command(command: str) -> bool:
    """Validates if a command is in the whitelist and has safe arguments."""
    try:
        # Check for command injection attempts
        if any(char in command for char in ['&&', '||', ';', '|', '`', '$(']):
            return False
            
        # Split command and get base command
        parts = command.split()
        base_cmd = parts[0]
        
        # Check if base command is in whitelist
        if base_cmd not in SAFE_COMMANDS:
            return False
            
        # Only validate paths for file-modifying commands
        if base_cmd in FILE_MODIFYING_COMMANDS:
            if not validate_file_operation(command, parts):
                return False
                
        return True
        
    except Exception:
        return False

@weave.op(name="command_line-run_command")
def run_command(*, command: str, working_dir: str = '.') -> Dict[str, Any]:
    """
    Executes a whitelisted command safely.
    
    Args:
        command: Command to execute (must start with a whitelisted command)
        working_dir: Working directory for the command
        
    Returns:
        Dict containing command output or error message
    """
    try:
        # Validate command
        if not is_safe_command(command):
            return {
                "error": "Command not allowed. Must use one of the whitelisted commands: " + 
                        ", ".join(SAFE_COMMANDS.keys())
            }
            
        # Execute command
        process = subprocess.run(
            command,
            shell=True,  # Required for commands with pipes and redirections
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30  # Timeout after 30 seconds
        )
        
        return {
            "command": command,
            "working_dir": working_dir,
            "output": process.stdout,
            "error": process.stderr if process.stderr else None,
            "exit_code": process.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 30 seconds"}
    except Exception as e:
        return {"error": f"Error executing command: {str(e)}"}
    
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "command_line-run_command",
                "description": f"""Executes whitelisted command line operations safely. Available commands:
                
                Navigation & Read Operations (unrestricted):
                - ls: List directory contents
                - pwd: Print working directory
                - cd: Change directory
                - cat: Display file contents
                - find: Search for files by name
                - grep: Search for patterns in files
                - tree: Display directory structure
                - wc: Count lines/words/characters
                - head/tail: Show start/end of files
                - diff: Compare files
                
                File Operations (restricted to workspace only):
                - mkdir: Create directory
                - touch: Create empty file
                - rm: Remove file/empty dir
                - cp: Copy file
                - mv: Move/rename file
                - echo: Write to file
                - sed: Edit file content""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Command to execute (must start with a whitelisted command)"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "Working directory for the command (defaults to current directory)",
                            "default": "."
                        }
                    },
                    "required": ["command"]
                }
            }
        },
        "implementation": run_command
    }
]