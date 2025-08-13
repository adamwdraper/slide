"""Database CLI for Tyler Stores"""
import asyncio
import os
import click
import functools
import subprocess
import tempfile
import time
from pathlib import Path
from .thread_store import ThreadStore
from ..utils.logging import get_logger

logger = get_logger(__name__)

@click.group()
def main():
    """Narrator CLI - Database management commands"""
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

@main.command()
@click.option('--port', help='Port to expose PostgreSQL on (default: 5432 or NARRATOR_DB_PORT)')
@click.option('--detach/--no-detach', default=True, help='Run container in background (default: True)')
def docker_start(port, detach):
    """Start a PostgreSQL container for Narrator"""
    # Use environment variables with defaults matching docker-compose.yml
    db_name = os.environ.get('NARRATOR_DB_NAME', 'narrator')
    db_user = os.environ.get('NARRATOR_DB_USER', 'narrator')
    db_password = os.environ.get('NARRATOR_DB_PASSWORD', 'narrator_dev')
    db_port = port or os.environ.get('NARRATOR_DB_PORT', '5432')
    
    docker_compose_content = f"""services:
  postgres:
    image: postgres:16
    container_name: narrator-postgres
    environment:
      POSTGRES_DB: {db_name}
      POSTGRES_USER: {db_user}
      POSTGRES_PASSWORD: {db_password}
    ports:
      - "{db_port}:5432"
    volumes:
      - narrator_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {db_user}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  narrator_postgres_data:
"""
    
    # Create a temporary directory for docker-compose.yml
    with tempfile.TemporaryDirectory() as tmpdir:
        compose_file = Path(tmpdir) / "docker-compose.yml"
        compose_file.write_text(docker_compose_content)
        
        # Check if docker is available
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            click.echo("❌ Docker is not installed or not available in PATH")
            raise click.Abort()
        
        # Check if docker-compose or docker compose is available
        compose_cmd = None
        try:
            subprocess.run(["docker", "compose", "version"], capture_output=True, check=True)
            compose_cmd = ["docker", "compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                subprocess.run(["docker-compose", "version"], capture_output=True, check=True)
                compose_cmd = ["docker-compose"]
            except (subprocess.CalledProcessError, FileNotFoundError):
                click.echo("❌ Docker Compose is not installed")
                raise click.Abort()
        
        # Start the container
        click.echo("📦 Starting PostgreSQL container...")
        cmd = compose_cmd + ["up"]
        if detach:
            cmd.append("-d")
        
        result = subprocess.run(cmd, cwd=tmpdir)
        
        if result.returncode != 0:
            click.echo("❌ Failed to start PostgreSQL container")
            raise click.Abort()
        
        if detach:
            # Wait for PostgreSQL to be ready
            click.echo("⏳ Waiting for PostgreSQL to be ready...")
            for i in range(30):
                result = subprocess.run(
                    ["docker", "exec", "narrator-postgres", "pg_isready", "-U", db_user],
                    capture_output=True
                )
                if result.returncode == 0:
                    click.echo("✅ PostgreSQL is ready!")
                    click.echo(f"\n🎉 Database available at:")
                    click.echo(f"   postgresql+asyncpg://{db_user}:{db_password}@localhost:{db_port}/{db_name}")
                    return
                time.sleep(1)
            
            click.echo("❌ PostgreSQL failed to start after 30 seconds")
            raise click.Abort()

@main.command()
@click.option('--remove-volumes', is_flag=True, help='Remove data volumes (destroys all data)')
def docker_stop(remove_volumes):
    """Stop the PostgreSQL container"""
    # Check if docker is available
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("❌ Docker is not installed or not available in PATH")
        raise click.Abort()
    
    # Check if container exists
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )
    
    if "narrator-postgres" not in result.stdout:
        click.echo("ℹ️  No Narrator PostgreSQL container found")
        return
    
    click.echo("🛑 Stopping PostgreSQL container...")
    
    # Stop the container
    subprocess.run(["docker", "stop", "narrator-postgres"], check=False)
    subprocess.run(["docker", "rm", "narrator-postgres"], check=False)
    
    if remove_volumes:
        click.echo("🗑️  Removing data volume...")
        subprocess.run(["docker", "volume", "rm", "narrator_postgres_data"], check=False)
        click.echo("✅ Container and data removed")
    else:
        click.echo("✅ Container stopped (data preserved)")

@main.command()
@click.option('--port', help='Port to expose PostgreSQL on (default: 5432 or NARRATOR_DB_PORT)')
def docker_setup(port):
    """One-command Docker setup: start PostgreSQL and initialize tables"""
    # Start PostgreSQL
    ctx = click.get_current_context()
    ctx.invoke(docker_start, port=port, detach=True)
    
    # Get database configuration from environment or defaults
    db_name = os.environ.get('NARRATOR_DB_NAME', 'narrator')
    db_user = os.environ.get('NARRATOR_DB_USER', 'narrator')
    db_password = os.environ.get('NARRATOR_DB_PASSWORD', 'narrator_dev')
    db_port = port or os.environ.get('NARRATOR_DB_PORT', '5432')
    
    # Set up database URL
    database_url = f"postgresql+asyncpg://{db_user}:{db_password}@localhost:{db_port}/{db_name}"
    os.environ['NARRATOR_DATABASE_URL'] = database_url
    
    # Initialize tables
    click.echo("\n🔧 Initializing database tables...")
    ctx.invoke(init, database_url=database_url)
    
    click.echo("\n🎉 Setup complete! Your database is ready.")
    click.echo("\nTo use in your code:")
    click.echo(f'export NARRATOR_DATABASE_URL="{database_url}"')
    click.echo("\nTo stop the container: narrator docker-stop")
    click.echo("To remove all data: narrator docker-stop --remove-volumes")

if __name__ == '__main__':
    main() 