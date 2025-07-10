"""
Command-line interface for Space Monkey.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .templates import TemplateManager
from .templates.common_patterns import generate_pattern, get_pattern_names


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Space Monkey - Agent orchestration and workflow management for building agentic Slack bots"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version="space-monkey 0.1.0"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show space-monkey status")
    
    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate agent scaffolding")
    generate_subparsers = generate_parser.add_subparsers(dest="generate_type", help="What to generate")
    
    # Generate agent command
    agent_parser = generate_subparsers.add_parser("agent", help="Generate an agent")
    agent_parser.add_argument("name", help="Name of the agent to generate")
    agent_parser.add_argument("--description", help="Description of what the agent does")
    agent_parser.add_argument("--tools", action="append", help="Tools the agent uses (can be specified multiple times)")
    agent_parser.add_argument("--sub-agents", action="append", help="Sub-agents this agent uses (can be specified multiple times)")
    agent_parser.add_argument("--bot-user-id", action="store_true", help="Include bot user ID in the agent")
    agent_parser.add_argument("--citations", action="store_true", help="Require citations in responses")
    agent_parser.add_argument("--guidelines", help="Specific guidelines for the agent")
    agent_parser.add_argument("--output-dir", help="Output directory (default: ./agents/{agent_name})")
    agent_parser.add_argument("--pattern", choices=get_pattern_names(), help="Use a predefined pattern")
    
    args = parser.parse_args()
    
    if args.command == "status":
        handle_status()
    elif args.command == "generate":
        if args.generate_type == "agent":
            handle_generate_agent(args)
        else:
            print("Error: Please specify what to generate (agent)")
            sys.exit(1)
    else:
        parser.print_help()


def handle_status():
    """Handle the status command."""
    print("🐒 Space Monkey Status")
    print("=" * 30)
    print("🟢 Ready for Slack bot agent generation!")
    print("")
    print("Available commands:")
    print("  space-monkey generate agent <name>  - Generate a new Slack bot agent")
    print("  space-monkey status                 - Show this status")
    print("")
    print("Example usage:")
    print("  space-monkey generate agent hr-bot --description 'HR assistant' --tools notion:search")


def handle_generate_agent(args):
    """Handle the generate agent command."""
    agent_name = args.name
    
    # Default output directory
    output_dir = args.output_dir or f"./agents/{agent_name.lower().replace(' ', '_').replace('-', '_')}"
    
    print(f"🐒 Generating agent: {agent_name}")
    print(f"📁 Output directory: {output_dir}")
    
    try:
        # Use pattern if specified
        if args.pattern:
            print(f"🎯 Using pattern: {args.pattern}")
            files = generate_pattern(
                pattern_name=args.pattern,
                agent_name=agent_name,
                description=args.description,
                tools=args.tools,
                sub_agents=args.sub_agents,
                bot_user_id=args.bot_user_id,
                citations_required=args.citations,
                specific_guidelines=args.guidelines
            )
        else:
            # Use template manager directly
            manager = TemplateManager()
            files = manager.generate_agent(
                agent_name=agent_name,
                description=args.description or f"Agent for {agent_name}",
                tools=args.tools,
                sub_agents=args.sub_agents,
                bot_user_id=args.bot_user_id,
                citations_required=args.citations,
                specific_guidelines=args.guidelines
            )
        
        # Write files to output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for filename, content in files.items():
            file_path = output_path / filename
            file_path.write_text(content)
            print(f"  ✅ Created: {file_path}")
        
        print(f"🎉 Agent '{agent_name}' generated successfully!")
        print(f"📁 Files created in: {output_path.absolute()}")
        
        # Show next steps
        print("\n🚀 Next steps:")
        print("  1. Review and customize the generated files")
        print("  2. Add your specific business logic")
        print("  3. Configure your Slack app and tokens")
        print("  4. Deploy and test your bot")
        
    except Exception as e:
        print(f"❌ Error generating agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
