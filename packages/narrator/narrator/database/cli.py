"""Database CLI for Tyler Stores"""
import asyncio
import os
import click
import functools
from .thread_store import ThreadStore
from ..utils.logging import get_logger

logger = get_logger(__name__)

@click.group()
def main():
    """Tyler Stores Database CLI"""
    pass

@main.command()
@click.option('--database-url', help='Database URL for initialization')
def init(database_url):
    """Initialize database tables"""
    async def _init():
        try:
            # Use provided URL or check environment variable
            url = database_url or os.environ.get('NARRATOR_DATABASE_URL')
            
            if url:
                store = await ThreadStore.create(url)
            else:
                # Use in-memory storage
                store = await ThreadStore.create()
            
            logger.info("Database initialized successfully")
            click.echo("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            click.echo(f"Error: Failed to initialize database: {e}")
            raise click.Abort()
    
    asyncio.run(_init())

@main.command()
@click.option('--database-url', help='Database URL')
def status(database_url):
    """Check database status"""
    async def _status():
        try:
            # Use provided URL or check environment variable
            url = database_url or os.environ.get('NARRATOR_DATABASE_URL')
            
            if url:
                store = await ThreadStore.create(url)
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
    
    asyncio.run(_status())

if __name__ == '__main__':
    main() 