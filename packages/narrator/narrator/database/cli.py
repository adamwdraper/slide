"""Database CLI for Tyler Stores"""
import asyncio
import click
from .thread_store import ThreadStore
from ..utils.logging import get_logger

logger = get_logger(__name__)

@click.group()
def main():
    """Tyler Stores Database CLI"""
    pass

@click.command()
@click.option('--database-url', help='Database URL for initialization')
async def init(database_url):
    """Initialize database tables"""
    try:
        if database_url:
            store = await ThreadStore.create(database_url)
        else:
            # Use environment variables or default
            store = await ThreadStore.create()
        
        logger.info("Database initialized successfully")
        click.echo("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        click.echo(f"Error: Failed to initialize database: {e}")
        raise click.Abort()

@click.command()
@click.option('--database-url', help='Database URL')
async def status(database_url):
    """Check database status"""
    try:
        if database_url:
            store = await ThreadStore.create(database_url)
        else:
            store = await ThreadStore.create()
        
        # Get some basic stats
        threads = await store.list_recent(limit=5)
        click.echo(f"Database connection: OK")
        click.echo(f"Recent threads count: {len(threads)}")
        
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        click.echo(f"Error: Database status check failed: {e}")
        raise click.Abort()

# Add async wrapper for commands
def async_command(f):
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# Apply async wrapper to commands
init = click.command()(async_command(init))
status = click.command()(async_command(status))

main.add_command(init)
main.add_command(status)

if __name__ == '__main__':
    main() 