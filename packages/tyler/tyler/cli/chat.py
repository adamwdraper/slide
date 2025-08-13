"""Command line interface for Tyler chat"""
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import os
import sys
import warnings
from contextlib import contextmanager, redirect_stderr
import io

# Suppress all Python warnings
warnings.filterwarnings('ignore')

# Set environment variables to suppress various library outputs
os.environ['WANDB_SILENT'] = 'true'
os.environ['WANDB_MODE'] = 'disabled'
os.environ['WEAVE_SILENCE_WARNINGS'] = 'true'
os.environ['LITELLM_LOG'] = 'ERROR'
os.environ['HTTPX_LOG_LEVEL'] = 'ERROR'

@contextmanager
def suppress_output():
    """Suppress stdout and stderr, filtering out library messages"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    class FilteredOutput:
        def __init__(self, original_stream):
            self.original = original_stream
            self.suppressed_prefixes = ['weave:', 'LiteLLM:', 'wandb:', 'ERROR:', 'WARNING:']
            self.suppressed_patterns = [
                'weave.trace.op -',  # Weave trace messages
                'litellm_logging.py',  # LiteLLM logging messages
                'Traceback (most recent',  # Python tracebacks
                'ModuleNotFoundError:',  # Module errors
                'ImportError:',  # Import errors
                'narrator.database',  # Narrator database messages
                'tyler.models.agent -',  # Tyler agent logs
                'weave.trace.init_message -',  # Weave init messages
            ]
            
        def write(self, text):
            # Only write if it's not from a suppressed source
            stripped = text.strip()
            if stripped and not any(prefix in stripped for prefix in self.suppressed_prefixes + self.suppressed_patterns):
                # Also filter lines that look like timestamps (e.g., "11:27:20 -")
                if not (len(stripped) > 10 and stripped[2] == ':' and stripped[5] == ':' and ' - ' in stripped[:15]):
                    self.original.write(text)
                
        def flush(self):
            self.original.flush()
            
        def __getattr__(self, attr):
            return getattr(self.original, attr)
    
    try:
        sys.stdout = FilteredOutput(old_stdout)
        sys.stderr = FilteredOutput(old_stderr)
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
import click
import asyncio
from typing import Optional, Dict, Any, Union, List
from pathlib import Path
import json
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.live import Live
from rich.layout import Layout
from rich.table import Table
from rich import box
import yaml
from datetime import datetime
import urllib3
import logging

# Set up a global connection pool with larger size
pool = urllib3.PoolManager(maxsize=100)
urllib3.disable_warnings()

# Suppress errors during imports
with suppress_output():
    import weave
import importlib.util

# Configure logging - suppress all warnings/errors from external packages
logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s: %(message)s'
)

# Get root logger and set to ERROR level
root_logger = logging.getLogger()
root_logger.setLevel(logging.ERROR)

# Suppress all third-party package loggers
for name in logging.root.manager.loggerDict:
    if not name.startswith('tyler'):
        logging.getLogger(name).setLevel(logging.CRITICAL)
        logging.getLogger(name).propagate = False

# Specifically silence known noisy libraries
noisy_libraries = [
    'gql', 'urllib3', 'httpx', 'httpcore', 'wandb', 'weave',
    'litellm', 'litellm.utils', 'litellm.llms', 'litellm.litellm_core_utils',
    'litellm.proxy', 'litellm.litellm_logging', 'LiteLLM',
    'openai', 'asyncio', 'filelock', 'pydantic', 'httpx._client'
]

for logger_name in noisy_libraries:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL + 1)  # Higher than CRITICAL to suppress everything
    logger.propagate = False
    logger.handlers = []  # Remove all handlers

# Import Tyler modules with suppressed output
with suppress_output():
    from tyler import Agent, Thread, Message, ThreadStore
    from tyler.models.execution import ExecutionEvent, EventType

# Initialize rich console
console = Console()

class ChatManager:
    def __init__(self):
        self.agent = None
        self.current_thread = None
        self.thread_store = ThreadStore()
        self.thread_count = 0  # Track number of threads created
        # Initialize Weave with suppressed output
        with suppress_output():
            weave.init("tyler-cli")
        
    def initialize_agent(self, config: Dict[str, Any] = None) -> None:
        """Initialize the agent with optional configuration"""
        if config is None:
            config = {}
        
        # Create agent with provided config, suppressing initialization errors
        with suppress_output():
            self.agent = Agent(**config)
        
    async def create_thread(self, 
                          title: Optional[str] = None,
                          attributes: Optional[Dict] = None,
                          source: Optional[Dict] = None) -> Thread:
        """Create a new thread"""
        # Increment thread count for default titles
        self.thread_count += 1
        
        # Generate a default title if none provided
        if not title:
            title = f"Thread {self.thread_count}"
            
        thread = Thread(
            title=title,
            attributes=attributes or {},
            source=source
        )
        
        # Add the agent's system prompt as the first message
        if self.agent:
            system_prompt = self.agent._prompt.system_prompt(
                self.agent.purpose,
                self.agent.name,
                self.agent.model_name,
                tools=self.agent._processed_tools,
                notes=self.agent.notes
            )
            # Add system message if thread is empty
            if not thread.messages:
                system_message = Message(role="system", content=system_prompt)
                thread.add_message(system_message)
            
        await self.thread_store.save(thread)
        self.current_thread = thread
        return thread
        
    async def list_threads(self) -> list:
        """List all threads in reverse chronological order (most recent first)"""
        return await self.thread_store.list(limit=100, offset=0)
        
    async def switch_thread(self, thread_id_or_index: str) -> Optional[Thread]:
        """Switch to a different thread by ID or index.
        
        Args:
            thread_id_or_index: Either a thread ID or a numeric index (1-based)
                               When using index, 1 is the oldest thread, increasing from there
        """
        # Check if it's a numeric index
        try:
            if thread_id_or_index.isdigit():
                index = int(thread_id_or_index)
                threads = await self.list_threads()
                if 1 <= index <= len(threads):
                    # Convert 1-based index to correct position in reverse chronological list
                    thread = threads[len(threads) - index]  # Get from end of list
                    self.current_thread = thread
                    
                    # Ensure thread has correct system prompt
                    if self.agent:
                        system_prompt = self.agent._prompt.system_prompt(
                            self.agent.purpose,
                            self.agent.name,
                            self.agent.notes
                        )
                        thread.ensure_system_prompt(system_prompt)
                        await self.thread_store.save(thread)
                        
                    return thread
                else:
                    raise ValueError(f"Thread index {index} is out of range")
        except ValueError as e:
            # If not a valid index, try as thread ID
            thread = await self.thread_store.get(thread_id_or_index)
            if thread:
                self.current_thread = thread
                
                # Ensure thread has correct system prompt
                if self.agent:
                    system_prompt = self.agent._prompt.system_prompt(
                        self.agent.purpose,
                        self.agent.name,
                        self.agent.notes
                    )
                    thread.ensure_system_prompt(system_prompt)
                    await self.thread_store.save(thread)
                    
            return thread

    def format_message(self, message: Message) -> Union[Panel, List[Panel]]:
        """Format a message for display"""
        if message.role == "system":
            return  # Don't display system messages
            
        # Determine style based on role
        style_map = {
            "user": "green",
            "assistant": "blue",
            "tool": "yellow"
        }
        style = style_map.get(message.role, "white")
        
        # Format content
        if message.role == "tool":
            # For tool messages, show a compact version
            title = f"[{style}]Tool Result: {message.name}[/]"
            content = message.content[:500] + "..." if len(message.content) > 500 else message.content
            return Panel(
                Markdown(content) if content else "",
                title=title,
                border_style=style,
                box=box.ROUNDED
            )
        elif message.role == "assistant" and message.tool_calls:
            # Create a list to hold all panels
            panels = []
            
            # Add main content panel if there is content
            if message.content and message.content.strip():
                panels.append(Panel(
                    Markdown(message.content),
                    title=f"[blue]Agent[/]",
                    border_style="blue",
                    box=box.ROUNDED
                ))
            
            # Add separate panels for each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call["function"]["name"]
                args = json.dumps(json.loads(tool_call["function"]["arguments"]), indent=2)
                panels.append(Panel(
                    Markdown(args),
                    title=f"[yellow]Tool Call: {tool_name}[/]",
                    border_style="yellow",
                    box=box.ROUNDED
                ))
            
            return panels
        else:
            title = f"[{style}]{'Agent' if message.role == 'assistant' else message.role.title()}[/]"
            content = message.content
            return Panel(
                Markdown(content) if content else "",
                title=title,
                border_style=style,
                box=box.ROUNDED
            )

    async def process_command(self, command: str) -> bool:
        """Process a command and return whether to continue the session"""
        cmd_parts = command.split()
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1:]
        
        if cmd == "/help":
            self.show_help()
        elif cmd == "/new":
            title = " ".join(args) if args else None
            await self.create_thread(title=title)
            console.print(f"Created new thread: {self.current_thread.title}")
        elif cmd == "/quit" or cmd == "/exit":
            return False
        elif cmd == "/threads":
            threads = await self.list_threads()
            table = Table(title="Available Threads")
            table.add_column("#", justify="right", style="cyan")  # Add index column
            table.add_column("ID")
            table.add_column("Title")
            table.add_column("Messages")
            table.add_column("Last Updated")
            
            # Display threads with index 1 being the oldest thread
            for i, thread in enumerate(reversed(threads), 1):  # Reverse the list and start index at 1
                table.add_row(
                    str(i),  # Add index
                    thread.id,
                    thread.title,
                    str(len(thread.messages)),
                    thread.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                )
            console.print(table)
        elif cmd == "/switch":
            if not args:
                console.print("[red]Error: Thread ID or index required[/]")
                return True
            thread = await self.switch_thread(args[0])
            if thread:
                console.print(f"Switched to thread: {thread.title}")
                # Display thread history
                for message in thread.messages:
                    panel = self.format_message(message)
                    if panel:
                        console.print(panel)
            else:
                console.print("[red]Error: Thread not found[/]")
        elif cmd == "/clear":
            console.clear()
        else:
            console.print(f"[red]Unknown command: {cmd}[/]")
            
        return True

    def show_help(self):
        """Show help information"""
        help_text = """
Available Commands:
/help     - Show this help message
/new      - Create a new thread
/threads  - List all threads
/switch   - Switch to a different thread (use thread ID or number)
/clear    - Clear the screen
/quit     - Exit the chat

Note: When using /switch, you can either use the thread ID or the thread number
shown in the /threads list. For example:
  /switch 1    - Switch to the first thread
  /switch abc  - Switch to thread with ID 'abc'
"""
        console.print(Panel(help_text, title="Help", border_style="blue"))

async def handle_stream_update(event: ExecutionEvent, chat_manager: ChatManager):
    """Handle streaming updates from the agent"""
    if event.type == EventType.LLM_STREAM_CHUNK:
        # Create/update the panel with the streaming content
        if not hasattr(handle_stream_update, 'live'):
            handle_stream_update.content = []
            handle_stream_update.live = Live(
                Panel(
                    "",
                    title="[blue]Agent[/]",
                    border_style="blue",
                    box=box.ROUNDED
                ),
                console=console,
                refresh_per_second=4
            )
            handle_stream_update.live.start()
        
        handle_stream_update.content.append(event.data.get("content_chunk", ""))
        handle_stream_update.live.update(Panel(
            Markdown(''.join(handle_stream_update.content)),
            title="[blue]Agent[/]",
            border_style="blue",
            box=box.ROUNDED
        ))
    elif event.type == EventType.MESSAGE_CREATED and event.data.get("message", {}).role == "assistant":
        # Stop the live display if it exists
        if hasattr(handle_stream_update, 'live'):
            handle_stream_update.live.stop()
            delattr(handle_stream_update, 'live')
            delattr(handle_stream_update, 'content')
            
        message = event.data.get("message")
        # Only print tool calls if present
        if message and message.tool_calls:
            console.print()  # New line after content chunks
            panels = chat_manager.format_message(message)
            if isinstance(panels, list):
                for panel in panels:
                    console.print(panel)
            elif panels:  # Single panel
                console.print(panels)
    elif event.type == EventType.MESSAGE_CREATED and event.data.get("message", {}).role == "tool":
        panel = chat_manager.format_message(event.data.get("message"))
        if panel:
            console.print(panel)
    elif event.type == EventType.EXECUTION_ERROR:
        console.print(f"[red]Error: {event.data.get('message', 'Unknown error')}[/]")

def load_custom_tool(file_path: str) -> list:
    """Load custom tools from a Python file.
    
    The file should contain a TOOLS list that contains tool definitions.
    Each tool should be a dict with 'definition' and 'implementation' keys.
    """
    try:
        # Get the module name from the file name
        module_name = Path(file_path).stem
        
        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load spec for {file_path}")
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # Get the TOOLS list from the module
        if not hasattr(module, 'TOOLS'):
            raise AttributeError(f"Module {module_name} must define a TOOLS list")
            
        return module.TOOLS
    except Exception as e:
        console.print(f"[red]Error loading custom tools from {file_path}: {str(e)}[/]")
        return []

def load_config(config_file: Optional[str]) -> Dict[str, Any]:
    """Load configuration from file.
    
    Looks for config in the following locations (in order):
    1. Explicitly provided config file path (--config option)
    2. ./tyler-chat-config.yaml in current directory
    3. ~/.tyler/chat-config.yaml in user's home directory
    4. /etc/tyler/chat-config.yaml for system-wide config
    """
    if config_file:
        config_path = Path(config_file)
    else:
        # Check standard locations
        possible_locations = [
            Path.cwd() / "tyler-chat-config.yaml",  # Current directory
            Path.home() / ".tyler" / "chat-config.yaml",  # User's home directory
            Path("/etc/tyler/chat-config.yaml"),  # System-wide
        ]
        
        for loc in possible_locations:
            if loc.exists():
                config_path = loc
                break
        else:
            # No config found, create template in current directory
            template_path = Path.cwd() / "tyler-chat-config.yaml"
            if not template_path.exists():
                template = """# Tyler Chat Configuration
# Save this file as tyler-chat-config.yaml in:
#   - Current directory
#   - ~/.tyler/chat-config.yaml
#   - /etc/tyler/chat-config.yaml
# Or specify location with: tyler-chat --config path/to/config.yaml

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
#   - Built-in tool module names (e.g., "web", "slack")
#   - Paths to Python files containing custom tools:
#     - "./my_tools.py"          # Relative to config file
#     - "~/tools/translate.py"    # User's home directory
#     - "/opt/tools/search.py"    # Absolute path
tools:
  - "web"           # Web search and browsing capabilities
  - "slack"         # Slack integration tools
  - "notion"        # Notion integration tools
  - "command_line"  # System command execution tools
  # - "./my_tools.py"  # Example custom tools (uncomment to use)
"""
                template_path.write_text(template)
                console.print(f"[yellow]Created template config at: {template_path}[/]")
            return {}
            
    try:
        with open(config_path) as f:
            if config_path.suffix in ['.yaml', '.yml']:
                config = yaml.safe_load(f)
            else:
                config = json.load(f)
                
        # Process tools list to load custom tools
        if 'tools' in config and isinstance(config['tools'], list):
            processed_tools = []
            config_dir = config_path.parent
            
            for tool in config['tools']:
                if isinstance(tool, str):
                    if any(c in tool for c in ['/', '.py', '~']):  # Looks like a path
                        # Handle relative paths
                        if tool.startswith('./') or tool.startswith('../'):
                            tool_path = str(config_dir / tool)
                        # Handle home directory
                        elif tool.startswith('~'):
                            tool_path = str(Path(tool).expanduser())
                        else:
                            tool_path = tool
                            
                        # Load custom tools from the file
                        custom_tools = load_custom_tool(tool_path)
                        processed_tools.extend(custom_tools)
                    else:
                        # It's a built-in tool module name
                        processed_tools.append(tool)
                else:
                    # Non-string items (like dicts) pass through unchanged
                    processed_tools.append(tool)
                    
            config['tools'] = processed_tools
                    
        return config
    except Exception as e:
        console.print(f"[yellow]Warning: Error loading config from {config_path}: {str(e)}[/]")
        return {}

def main(config: Optional[str], title: Optional[str]):
    """Tyler Chat CLI main function"""
    # Apply output filtering for the entire session
    with suppress_output():
        _main_inner(config, title)

def _main_inner(config: Optional[str], title: Optional[str]):
    """Inner main function with suppressed output"""
    try:
        # Load configuration
        config_data = load_config(config)
        
        # Initialize chat manager
        chat_manager = ChatManager()
        chat_manager.initialize_agent(config_data)
        
        # Create initial thread
        asyncio.run(chat_manager.create_thread(title=title))
        
        console.print("[bold blue]Welcome to Tyler Chat![/]")
        console.print("Type your message or /help for commands")
        
        # Main chat loop
        while True:
            # Get user input
            user_input = Prompt.ask("\nYou")
            
            # Check if it's a command
            if user_input.startswith('/'):
                should_continue = asyncio.run(chat_manager.process_command(user_input))
                if not should_continue:
                    break
                continue
            
            # Add user message to thread
            chat_manager.current_thread.add_message(Message(role="user", content=user_input))
            
            # Process with agent
            async def process_message():
                async for event in chat_manager.agent.go(chat_manager.current_thread, stream=True):
                    await handle_stream_update(event, chat_manager)
            
            asyncio.run(process_message())
            
    except KeyboardInterrupt:
        console.print("\nGoodbye!")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/]")
        raise

if __name__ == "__main__":
    main() 