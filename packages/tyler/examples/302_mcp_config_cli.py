"""Example of loading MCP config from a YAML file (CLI-style).

This example shows how to:
1. Load MCP configuration from a YAML file
2. Create an agent with that config
3. Use environment variable substitution

This is exactly what tyler-chat does internally!
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import yaml
from pathlib import Path
from tyler import Agent, Thread, Message


async def load_and_run_from_yaml():
    """Load agent config from YAML file including MCP settings."""
    
    # Example YAML content
    yaml_content = """
name: "Tyler"
model_name: "gpt-4o-mini"
purpose: "To help with documentation searches"

tools:
  - "web"

mcp:
  servers:
    - name: example_docs
      transport: sse
      url: https://docs.example.com/mcp
      fail_silent: true
      prefix: "docs"
"""
    
    # Parse YAML
    config = yaml.safe_load(yaml_content)
    
    print("Loaded config from YAML:")
    print(f"  Name: {config['name']}")
    print(f"  Model: {config['model_name']}")
    print(f"  Tools: {config['tools']}")
    print(f"  MCP Servers: {len(config.get('mcp', {}).get('servers', []))}")
    
    # Create agent from config
    agent = Agent(**config)
    
    # Connect to MCP servers
    print(f"\nConnecting to MCP servers...")
    try:
        await agent.connect_mcp()
        print(f"✓ Connected!")
        print(f"  Total tools available: {len(agent._processed_tools)}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("  (This is expected if the server doesn't exist)")


async def load_from_actual_file():
    """Load from an actual YAML config file."""
    
    # Check if tyler-chat-config.yaml exists
    config_path = Path("tyler-chat-config.yaml")
    
    if not config_path.exists():
        print("\nNo tyler-chat-config.yaml found in current directory.")
        print("You can create one with 'tyler chat' or copy the template.")
        return
    
    print(f"\nLoading config from: {config_path}")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Create agent
    agent = Agent(**config)
    
    # Connect MCP if configured
    if agent.mcp:
        print(f"MCP config found: {len(agent.mcp['servers'])} server(s)")
        await agent.connect_mcp()
    else:
        print("No MCP config in file")
    
    print(f"Agent created: {agent.name}")
    print(f"Tools: {len(agent._processed_tools)}")


async def main():
    """Run the examples."""
    print("=" * 60)
    print("Example 1: Load from YAML string")
    print("=" * 60)
    await load_and_run_from_yaml()
    
    print("\n" + "=" * 60)
    print("Example 2: Load from actual file")
    print("=" * 60)
    await load_from_actual_file()


if __name__ == "__main__":
    asyncio.run(main())

