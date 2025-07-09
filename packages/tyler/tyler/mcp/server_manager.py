"""MCP server manager implementation for Tyler."""

import asyncio
import logging
import os
import signal
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class MCPServerManager:
    """Manager for MCP server processes."""
    
    def __init__(self):
        self.processes = {}  # server_name -> subprocess.Popen
        self.server_configs = {}  # server_name -> config
        
    async def start_server(self, name: str, config: Dict[str, Any]) -> bool:
        """Start an MCP server process.
        
        Args:
            name: The name of the server
            config: Server configuration dictionary
            
        Returns:
            bool: True if server started successfully, False otherwise
        """
        # Check if server is already running
        if name in self.processes and self.processes[name].poll() is None:
            logger.info(f"MCP server {name} is already running")
            return True
            
        # Get command and args
        command = config.get("command")
        args = config.get("args", [])
        
        if not command:
            logger.error(f"command is required for MCP server {name}")
            return False
            
        if "args" not in config:
            logger.error(f"args is required for MCP server {name}")
            return False
            
        # Get environment variables
        env_vars = config.get("env", {})
        
        # Merge with current environment
        process_env = os.environ.copy()
        process_env.update(env_vars)
        
        # Start the process
        try:
            logger.info(f"Starting MCP server {name}: {command} {' '.join(args)}")
            process = subprocess.Popen(
                [command] + args,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                bufsize=0,  # Unbuffered
                universal_newlines=False  # Binary mode
            )
            
            # Wait a bit to see if the process starts successfully
            await asyncio.sleep(0.5)
            
            # Check if process is still running
            if process.poll() is not None:
                logger.error(f"MCP server {name} failed to start")
                return False
                
            # Store the process and config
            self.processes[name] = process
            self.server_configs[name] = config
            
            logger.info(f"MCP server {name} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting MCP server {name}: {e}")
            return False
            
    async def stop_server(self, name: str) -> bool:
        """Stop an MCP server process.
        
        Args:
            name: The name of the server
            
        Returns:
            bool: True if server stopped successfully, False otherwise
        """
        if name not in self.processes:
            logger.error(f"MCP server {name} not found")
            return False
            
        process = self.processes[name]
        
        # Check if process is still running
        if process.poll() is None:
            try:
                logger.info(f"Stopping MCP server {name}")
                
                # Send SIGTERM to the process
                process.terminate()
                
                # Wait for the process to terminate
                await asyncio.to_thread(process.wait)
                
            except Exception as e:
                logger.error(f"Error stopping MCP server {name}: {e}")
                return False
                
        # Remove the process and config
        del self.processes[name]
        del self.server_configs[name]
        
        logger.info(f"MCP server {name} stopped successfully")
        return True
        
    async def stop_all_servers(self) -> None:
        """Stop all MCP server processes."""
        server_names = list(self.processes.keys())
        for name in server_names:
            await self.stop_server(name) 