"""Advanced MCP features: multiple servers, filtering, custom prefixes.

This example demonstrates advanced MCP configuration patterns:
1. Connecting to multiple MCP servers simultaneously
2. Using custom namespace prefixes
3. Filtering tools with include/exclude
4. Handling different transport types
5. Using authentication headers
6. Graceful failure handling

Run:
    python 301_mcp_advanced.py
"""
from dotenv import load_dotenv
load_dotenv()

from tyler.utils.logging import get_logger
logger = get_logger(__name__)

import asyncio
import os
import weave
from tyler import Agent, Thread, Message

# Initialize weave tracing if available
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("slide")
except Exception:
    pass


async def example_multiple_servers():
    """Example 1: Multiple servers with filtering and custom prefixes."""
    
    print("\n" + "=" * 70)
    print("Example 1: Multiple MCP Servers")
    print("=" * 70)
    
    agent = Agent(
        name="Tyler",
        model_name="gpt-4o-mini",
        purpose="Multi-server agent with docs and GitHub access",
        mcp={
            "servers": [
                # Server 1: Slide docs (streamablehttp)
                {
                    "name": "docs",
                    "transport": "streamablehttp",
                    "url": "https://slide.mintlify.app/mcp",
                    "prefix": "slide",  # Custom prefix: slide_SearchSlideFramework
                    "fail_silent": False
                },
                # Server 2: GitHub (stdio) - will fail silently if no token
                {
                    "name": "github",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
                    "prefix": "gh",  # Custom prefix: gh_search_repos, etc.
                    "fail_silent": True  # Continue even if GitHub unavailable
                }
            ]
        }
    )
    
    # Connect to all servers
    print("\nConnecting to MCP servers...")
    await agent.connect_mcp()
    
    # Show connected tools
    print(f"✓ Agent has {len(agent._processed_tools)} tools total")
    
    # Show MCP tools grouped by server
    slide_tools = [t["function"]["name"] for t in agent._processed_tools if "slide_" in t["function"]["name"]]
    gh_tools = [t["function"]["name"] for t in agent._processed_tools if "gh_" in t["function"]["name"]]
    
    print(f"  Slide docs tools ({len(slide_tools)}): {slide_tools}")
    print(f"  GitHub tools ({len(gh_tools)}): {gh_tools}")
    
    # Use the agent
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Search the Slide docs for information about MCP"
    ))
    
    print("\n💬 User: Search the Slide docs for information about MCP")
    print("🤖 Tyler: ", end="", flush=True)
    
    async for event in agent.stream(thread):
        if event.type.name == "LLM_STREAM_CHUNK":
            print(event.data.get("content_chunk", ""), end="", flush=True)
        elif event.type.name == "EXECUTION_COMPLETE":
            print("\n")
    
    # Cleanup MCP connections (stdio connections may raise CancelledError)
    try:
        await agent.cleanup()
    except asyncio.CancelledError:
        pass  # Expected for stdio connections during cleanup


async def example_tool_filtering():
    """Example 2: Tool filtering with include/exclude."""
    
    print("\n" + "=" * 70)
    print("Example 2: Tool Filtering")
    print("=" * 70)
    print("\nThis example shows how to filter tools from MCP servers.")
    print("(Using mock config - filesystem server not actually running)\n")
    
    # Example config showing filtering (server doesn't need to be running to show pattern)
    config = {
        "servers": [
            {
                "name": "filesystem",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "exclude_tools": ["write_file", "delete_file"],  # Read-only!
                "fail_silent": True
            },
            {
                "name": "api",
                "transport": "sse",
                "url": "https://api.example.com/mcp",
                "include_tools": ["search", "query"],  # Whitelist specific tools
                "fail_silent": True
            }
        ]
    }
    
    print("Tool filtering patterns:")
    print("\n1. Exclude dangerous operations (read-only filesystem):")
    print(f"   exclude_tools: {config['servers'][0]['exclude_tools']}")
    print("\n2. Include only specific tools (whitelist):")
    print(f"   include_tools: {config['servers'][1]['include_tools']}")
    print("\n3. Set fail_silent=True to skip unavailable servers gracefully")


async def example_authentication():
    """Example 3: Using authentication headers."""
    
    print("\n" + "=" * 70)
    print("Example 3: Authentication with Headers")
    print("=" * 70)
    
    # Example pattern for authenticated MCP servers
    config = {
        "servers": [{
            "name": "private_api",
            "transport": "sse",
            "url": "https://api.example.com/mcp",
            "headers": {
                # Always use environment variables for secrets!
                "Authorization": f"Bearer ${os.environ.get('API_TOKEN', 'your-token-here')}",
                "X-API-Key": "${API_KEY}"  # Can also use ${VAR} syntax
            },
            "prefix": "api"
        }]
    }
    
    print("\nAuthentication pattern:")
    print("  - Use 'headers' field for authentication")
    print("  - Always use environment variables for secrets")
    print("  - Supports ${VAR_NAME} syntax for env var substitution")
    print(f"\nExample config: {config}")


async def example_yaml_loading():
    """Example 4: Loading MCP config from YAML (CLI pattern)."""
    
    print("\n" + "=" * 70)
    print("Example 4: YAML Configuration (CLI Pattern)")
    print("=" * 70)
    
    yaml_example = """
# tyler-config.yaml
name: "Tyler"
model_name: "gpt-4o-mini"
purpose: "Multi-capability assistant"

tools:
  - "web"

mcp:
  servers:
    - name: docs
      transport: streamablehttp
      url: https://slide.mintlify.app/mcp
      prefix: "slide"
      fail_silent: false
      
    - name: github
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
      prefix: "gh"
      fail_silent: true
"""
    
    print("\nYAML config pattern (used by tyler-chat):")
    print(yaml_example)
    print("\nLoad and use:")
    print("  import yaml")
    print("  config = yaml.safe_load(open('tyler-config.yaml'))")
    print("  agent = Agent(**config)")
    print("  await agent.connect_mcp()")


async def main():
    """Run all examples."""
    
    print("=" * 70)
    print("Tyler MCP Advanced Features Examples")
    print("=" * 70)
    
    # Example 1: Multiple servers (actually runs)
    await example_multiple_servers()
    
    # Example 2-4: Show patterns (documentation)
    await example_tool_filtering()
    await example_authentication()
    await example_yaml_loading()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("\nKey takeaways:")
    print("  ✓ Use multiple servers for different capabilities")
    print("  ✓ Filter tools with include/exclude for safety")
    print("  ✓ Use custom prefixes to organize tool namespaces")
    print("  ✓ Set fail_silent=True for optional servers")
    print("  ✓ Store secrets in environment variables")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

