#!/usr/bin/env python3
"""
Example: Generate an HR Bot using Space Monkey

This example demonstrates how to use space-monkey programmatically
to generate a complete HR Slack bot following the Perci pattern.
"""

import os
from pathlib import Path
from space_monkey.templates import TemplateManager


def main():
    """Generate an HR bot with comprehensive features."""
    print("🐒 Space Monkey - HR Bot Generator Example")
    print("=" * 50)
    
    # Initialize the template manager
    manager = TemplateManager()
    print("✓ Template manager initialized")
    
    # Generate the main HR agent (like Perci)
    print("\n📝 Generating HR Assistant agent...")
    hr_files = manager.generate_agent(
        agent_name="HRAssistant",
        description="Answering employee HR questions via Slack channels and DMs",
        tools=[
            "notion:notion-search",  # For searching HR documentation
            "slack:send-message"     # For Slack integration
        ],
        sub_agents=[
            "NotionPageReader",      # For reading Notion page content
            "MessageClassifier"      # For classifying message types
        ],
        bot_user_id=True,           # Essential for Slack @mentions
        citations_required=True,     # Important for HR information
        specific_guidelines="Use 'people team' instead of 'HR' in responses"
    )
    
    # Generate the message classifier agent
    print("📝 Generating Message Classifier agent...")
    classifier_files = manager.generate_agent(
        agent_name="MessageClassifier",
        description="Classifying Slack messages to determine if HR assistant should respond with text, emoji, or ignore",
        bot_user_id=True,
        specific_guidelines="Return JSON with response_type, suggested_emoji, confidence, and reasoning"
    )
    
    # Generate the Notion page reader agent
    print("📝 Generating Notion Page Reader agent...")
    notion_files = manager.generate_agent(
        agent_name="NotionPageReader",
        description="Reading and analyzing Notion pages to extract HR policy information",
        tools=["notion:read-page"]
    )
    
    # Create output directory
    output_dir = Path("generated_hr_bot")
    output_dir.mkdir(exist_ok=True)
    print(f"\n📁 Creating agents in: {output_dir.absolute()}")
    
    # Write HR Assistant files
    hr_dir = output_dir / "hr_assistant"
    hr_dir.mkdir(exist_ok=True)
    for filename, content in hr_files.items():
        file_path = hr_dir / filename
        file_path.write_text(content)
        print(f"  ✓ {file_path}")
    
    # Write Message Classifier files
    classifier_dir = output_dir / "message_classifier"
    classifier_dir.mkdir(exist_ok=True)
    for filename, content in classifier_files.items():
        file_path = classifier_dir / filename
        file_path.write_text(content)
        print(f"  ✓ {file_path}")
    
    # Write Notion Page Reader files
    notion_dir = output_dir / "notion_page_reader"
    notion_dir.mkdir(exist_ok=True)
    for filename, content in notion_files.items():
        file_path = notion_dir / filename
        file_path.write_text(content)
        print(f"  ✓ {file_path}")
    
    # Create a main.py integration example
    main_py_content = '''"""
HR Bot Main Application

This is an example of how to integrate the generated agents
into a complete Slack bot application.
"""

import os
import asyncio
from slack_bolt.async_app import AsyncApp
from tyler import ThreadStore, FileStore

# Import your generated agents
from hr_assistant.agent import initialize_hrassistant_agent
from hr_assistant.purpose import purpose_prompt as hr_purpose
from message_classifier.agent import initialize_messageclassifier_agent
from message_classifier.purpose import purpose_prompt as classifier_purpose

async def main():
    """Main application entry point."""
    
    # Initialize stores
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    
    # Get bot user ID (from Slack auth)
    bot_user_id = os.getenv("SLACK_BOT_USER_ID", "your-bot-user-id")
    
    # Initialize agents
    hr_agent = initialize_hrassistant_agent(
        thread_store=thread_store,
        file_store=file_store,
        purpose_prompt=hr_purpose,
        bot_user_id=bot_user_id
    )
    
    classifier_agent = initialize_messageclassifier_agent(
        thread_store=thread_store,
        file_store=file_store,
        purpose_prompt=classifier_purpose,
        bot_user_id=bot_user_id
    )
    
    print("🤖 HR Bot agents initialized successfully!")
    print("📋 Next steps:")
    print("  1. Set up your Slack app tokens")
    print("  2. Configure your database connection")
    print("  3. Deploy to your preferred platform")
    print("  4. Test in your Slack workspace")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    main_file = output_dir / "main.py"
    main_file.write_text(main_py_content)
    print(f"  ✓ {main_file}")
    
    # Create a README for the generated bot
    readme_content = '''# Generated HR Bot

This HR bot was generated using Space Monkey and follows proven patterns from production Slack bots.

## Structure

- `hr_assistant/` - Main HR agent (like Perci)
- `message_classifier/` - Classifies messages to determine response type
- `notion_page_reader/` - Reads Notion pages for HR information
- `main.py` - Example integration

## Features

- **Slack Integration**: Handles @mentions, DMs, threads, and emoji reactions
- **Notion Integration**: Searches and reads HR documentation
- **Message Classification**: Determines when to respond vs. ignore
- **Citation Support**: Provides sources for HR information
- **Multi-Agent System**: Specialized agents for different tasks

## Usage

1. **Install Dependencies**:
   ```bash
   pip install slide-tyler slide-narrator
   ```

2. **Set Environment Variables**:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-your-bot-token"
   export SLACK_APP_TOKEN="xapp-your-app-token"
   export SLACK_BOT_USER_ID="your-bot-user-id"
   ```

3. **Configure Database** (optional):
   ```bash
   export TYLER_DB_TYPE="postgresql"
   export TYLER_DB_HOST="localhost"
   export TYLER_DB_NAME="hr_bot"
   ```

4. **Run the Bot**:
   ```bash
   python main.py
   ```

## Customization

- Edit the `purpose.py` files to customize agent behavior
- Modify tools and sub-agents in `agent.py` files
- Add company-specific guidelines and knowledge

## Integration with Slack Bot Framework

This generated code is designed to integrate with the tyler-slack-bot framework:

```python
# In your Slack bot main.py
from hr_assistant.agent import initialize_hrassistant_agent
from hr_assistant.purpose import purpose_prompt

# Initialize in your bot startup
hr_agent = initialize_hrassistant_agent(
    thread_store=your_thread_store,
    file_store=your_file_store,
    purpose_prompt=purpose_prompt,
    bot_user_id=bot_user_id
)
```

Generated with ❤️ by Space Monkey 🐒
'''
    
    readme_file = output_dir / "README.md"
    readme_file.write_text(readme_content)
    print(f"  ✓ {readme_file}")
    
    print(f"\n🎉 HR Bot generated successfully!")
    print(f"📁 Location: {output_dir.absolute()}")
    print("\n📚 What was generated:")
    print("  • HR Assistant agent with Notion and Slack tools")
    print("  • Message Classifier for intelligent response routing")
    print("  • Notion Page Reader for document analysis")
    print("  • Integration example (main.py)")
    print("  • Complete documentation (README.md)")
    
    print("\n🚀 Next steps:")
    print("  1. Review and customize the generated agents")
    print("  2. Set up your Slack app and tokens")
    print("  3. Configure your Notion integration")
    print("  4. Deploy and test in your Slack workspace")


if __name__ == "__main__":
    main() 