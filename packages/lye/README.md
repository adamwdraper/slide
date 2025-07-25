# Lye - Tools Package for Tyler

Lye is a collection of tools that extend Tyler's capabilities, providing integrations with various services and utilities.

## Installation

```bash
pip install slide-lye
```

or with uv:

```bash
uv add slide-lye
```

## Available Tools

### Web Tools
- `fetch_page`: Fetch and extract content from web pages
- `download_file`: Download files from URLs
- `extract_text_from_html`: Extract text content from HTML
- `fetch_html`: Fetch raw HTML content

### Slack Tools  
- `post_message`: Post messages to Slack channels
- `get_channel_history`: Get message history from channels
- `get_users`: Get list of users in workspace
- `search_messages`: Search for messages
- `upload_file`: Upload files to Slack
- `summarize_channel`: Get AI summary of channel activity

### Command Line Tools
- `execute_command`: Execute shell commands safely
- `list_directory`: List directory contents
- `search_files`: Search for files by pattern

### Notion Tools
- `search_pages`: Search Notion pages
- `create_page`: Create new Notion pages
- `update_page`: Update existing pages
- `get_page`: Get page content
- `delete_page`: Delete pages
- `list_databases`: List available databases
- `query_database`: Query database contents
- `create_database_item`: Create database entries
- `update_database_item`: Update database entries

### Image Tools
- `generate_image`: Generate images using AI
- `analyze_image`: Analyze image content

### Audio Tools
- `text_to_speech`: Convert text to speech
- `speech_to_text`: Convert speech to text

### File Tools
- `read_file`: Read various file formats
- `write_file`: Write content to files
- `read_pdf`: Extract text from PDFs
- `process_csv`: Read and analyze CSV files
- `read_json`: Read JSON files
- `write_json`: Write JSON files

### Browser Tools
- `browser_automate`: Automate browser interactions
- `browser_screenshot`: Take screenshots of web pages

## Usage with Tyler

```python
from tyler import Agent

# Use all tools from a module
agent = Agent(tools=["web", "slack"])

# Use specific tools
agent = Agent(tools=["web:fetch_page,download_file"])

# Import tools directly
from lye import WEB_TOOLS, SLACK_TOOLS
agent = Agent(tools=WEB_TOOLS + SLACK_TOOLS)
```

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_web.py
```

## License

MIT License - see LICENSE file for details. 