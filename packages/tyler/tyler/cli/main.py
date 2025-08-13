"""Main CLI for Tyler"""
import click

@click.group()
def cli():
    """Tyler CLI - AI agent development toolkit.
    
    Commands:
        chat    Start an interactive chat session with an agent
        init    Create a new agent project
    """
    pass

# Import chat command
try:
    from tyler.cli.chat import main as chat_main
    @cli.command()
    @click.option('--config', '-c', help='Path to config file (YAML or JSON)')
    @click.option('--title', '-t', help='Initial thread title')
    def chat(config, title):
        """Start an interactive chat session with a Tyler agent."""
        # Import here to avoid circular imports and suppress output issues
        from tyler.cli.chat import _main_inner, suppress_output
        with suppress_output():
            _main_inner(config, title)
            
except ImportError:
    # Chat CLI might not be available, continue without it
    pass

# Import init command
try:
    from tyler.cli.init import cli as init_cli
    cli.add_command(init_cli, name="init")
except ImportError:
    # Init CLI might not be available, continue without it
    pass

def main():
    """Entry point for the CLI"""
    cli()

if __name__ == "__main__":
    main() 