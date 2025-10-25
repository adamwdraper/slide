"""
Example: Creating Tyler Agents from Config Files

This example demonstrates how to use Agent.from_config() to create agents
from YAML configuration files, enabling the same config to be used in both
CLI and Python code.

Features demonstrated:
- Auto-discovery of config files
- Explicit config paths
- Parameter overrides
- Advanced config manipulation

Run this example:
    python examples/003_agent_from_config.py
"""
import asyncio
import tempfile
import yaml
from pathlib import Path
from tyler import Agent, Thread, Message, load_config


async def example_basic():
    """Basic usage: Create agent from config file."""
    print("=" * 60)
    print("Example 1: Basic Agent.from_config()")
    print("=" * 60)
    
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "name": "ConfigAgent",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "purpose": "Demonstrate config-based agent creation",
            "notes": "This agent was created from a YAML config file",
            "tools": ["web"]
        }
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        # Create agent from config
        agent = Agent.from_config(config_path)
        
        print(f"✅ Created agent: {agent.name}")
        print(f"   Model: {agent.model_name}")
        print(f"   Temperature: {agent.temperature}")
        print(f"   Purpose: {agent.purpose}")
        
        # Use the agent
        thread = Thread()
        thread.add_message(Message(
            role="user",
            content="What is Tyler?"
        ))
        
        print("\n🤖 Agent response:")
        result = await agent.go(thread)
        print(f"   {result.new_messages[-1].content[:200]}...")
        
    finally:
        # Cleanup
        Path(config_path).unlink()


async def example_with_overrides():
    """Using parameter overrides to customize config values."""
    print("\n" + "=" * 60)
    print("Example 2: Config with Parameter Overrides")
    print("=" * 60)
    
    # Create config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "name": "BaseAgent",
            "model_name": "gpt-4o",
            "temperature": 0.5,
            "purpose": "Base configuration"
        }
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        # Override specific parameters
        agent = Agent.from_config(
            config_path,
            temperature=0.9,          # Override temperature
            model_name="gpt-4o-mini",  # Override model
            notes="Custom notes added via override"
        )
        
        print(f"✅ Created agent with overrides:")
        print(f"   Name: {agent.name} (from config)")
        print(f"   Model: {agent.model_name} (overridden)")
        print(f"   Temperature: {agent.temperature} (overridden)")
        print(f"   Notes: {agent.notes} (overridden)")
        
    finally:
        Path(config_path).unlink()


async def example_auto_discovery():
    """Auto-discovery: Find config in standard locations."""
    print("\n" + "=" * 60)
    print("Example 3: Auto-Discovery of Config Files")
    print("=" * 60)
    
    # Create config in current directory
    config_file = Path.cwd() / "tyler-chat-config.yaml"
    config_existed = config_file.exists()
    
    if not config_existed:
        config = {
            "name": "AutoDiscoveredAgent",
            "model_name": "gpt-4o-mini",
            "purpose": "Testing auto-discovery"
        }
        config_file.write_text(yaml.dump(config))
    
    try:
        # No path specified - will search:
        # 1. ./tyler-chat-config.yaml (found!)
        # 2. ~/.tyler/chat-config.yaml
        # 3. /etc/tyler/chat-config.yaml
        agent = Agent.from_config()
        
        print(f"✅ Auto-discovered config and created: {agent.name}")
        print(f"   Searched locations:")
        print(f"     1. ./tyler-chat-config.yaml ✓")
        print(f"     2. ~/.tyler/chat-config.yaml")
        print(f"     3. /etc/tyler/chat-config.yaml")
        
    finally:
        if not config_existed and config_file.exists():
            config_file.unlink()


async def example_advanced_manipulation():
    """Advanced: Load config, modify, then create agent."""
    print("\n" + "=" * 60)
    print("Example 4: Advanced Config Manipulation")
    print("=" * 60)
    
    # Create config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "name": "BaseAgent",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "tools": ["web"]
        }
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        # Load config into dict for inspection/modification
        config = load_config(config_path)
        
        print("📋 Original config:")
        print(f"   Name: {config['name']}")
        print(f"   Model: {config['model_name']}")
        print(f"   Tools: {config['tools']}")
        
        # Modify config programmatically
        config['name'] = "CustomizedAgent"
        config['temperature'] = 0.9
        config['notes'] = "Modified programmatically"
        
        # Create agent from modified config
        agent = Agent(**config)
        
        print("\n✅ Created agent from modified config:")
        print(f"   Name: {agent.name}")
        print(f"   Temperature: {agent.temperature}")
        print(f"   Notes: {agent.notes}")
        
    finally:
        Path(config_path).unlink()


async def example_with_env_vars():
    """Using environment variables in config."""
    print("\n" + "=" * 60)
    print("Example 5: Environment Variable Substitution")
    print("=" * 60)
    
    import os
    
    # Set environment variable
    os.environ['TYLER_EXAMPLE_MODEL'] = 'gpt-4o-mini'
    os.environ['TYLER_EXAMPLE_TEMP'] = '0.8'
    
    # Create config with env var references
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "name": "EnvVarAgent",
            "model_name": "${TYLER_EXAMPLE_MODEL}",  # Will be substituted
            "notes": "Using temperature: ${TYLER_EXAMPLE_TEMP}"
        }
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        agent = Agent.from_config(config_path)
        
        print(f"✅ Environment variables substituted:")
        print(f"   Model: {agent.model_name} (from $TYLER_EXAMPLE_MODEL)")
        print(f"   Notes: {agent.notes}")
        
    finally:
        Path(config_path).unlink()
        del os.environ['TYLER_EXAMPLE_MODEL']
        del os.environ['TYLER_EXAMPLE_TEMP']


async def main():
    """Run all examples."""
    print("\n" + "🚀 " * 20)
    print("Tyler Agent.from_config() Examples")
    print("🚀 " * 20 + "\n")
    
    await example_basic()
    await example_with_overrides()
    await example_auto_discovery()
    await example_advanced_manipulation()
    await example_with_env_vars()
    
    print("\n" + "=" * 60)
    print("✅ All examples complete!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("  • Use Agent.from_config() for quick setup")
    print("  • Override parameters as needed")
    print("  • Auto-discovery works with standard locations")
    print("  • load_config() for advanced manipulation")
    print("  • Environment variables keep secrets safe")
    print()


if __name__ == "__main__":
    asyncio.run(main())

