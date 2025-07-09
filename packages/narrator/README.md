# The Narrator

Thread and file storage components for conversational AI - the companion to Tyler AI framework.

## Overview

The Narrator provides robust, production-ready storage solutions for conversational AI applications. It includes:

- **ThreadStore**: Persistent storage for conversation threads with support for both in-memory and SQL backends
- **FileStore**: Secure file storage with automatic processing for various file types
- **Models**: Pydantic models for threads, messages, and attachments
- **CLI Tools**: Command-line interface for database management and setup

## Features

### ThreadStore
- **Multiple Backends**: In-memory (development), SQLite (local), PostgreSQL (production)
- **Async/Await Support**: Built for modern Python async applications
- **Message Filtering**: Automatic handling of system vs. user messages
- **Platform Integration**: Support for external platform references (Slack, etc.)
- **Connection Pooling**: Production-ready database connection management

### FileStore
- **Secure Storage**: Automatic file validation and type checking
- **Multiple Formats**: Support for documents, images, audio, and more
- **Content Processing**: Automatic text extraction from PDFs, image analysis
- **Storage Limits**: Configurable file size and total storage limits
- **Sharded Storage**: Efficient file organization to prevent directory bloat

## Installation

```bash
pip install the-narrator
```

## Setup

### Database Setup

For production use with PostgreSQL or SQLite persistence, you'll need to initialize the database tables:

```bash
# Initialize database tables (PostgreSQL)
narrator-db init --database-url "postgresql+asyncpg://user:password@localhost/dbname"

# Initialize database tables (SQLite)
narrator-db init --database-url "sqlite+aiosqlite:///path/to/your/database.db"

# Check database status
narrator-db status --database-url "postgresql+asyncpg://user:password@localhost/dbname"
```

You can also use environment variables instead of passing the database URL:

```bash
# Set environment variable
export NARRATOR_DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"

# Then run without --database-url flag
narrator-db init
narrator-db status
```

### Environment Variables

Configure the narrator using environment variables:

```bash
# Database settings
NARRATOR_DATABASE_URL="postgresql+asyncpg://user:password@localhost/dbname"
NARRATOR_DB_POOL_SIZE=5              # Connection pool size
NARRATOR_DB_MAX_OVERFLOW=10          # Max additional connections
NARRATOR_DB_POOL_TIMEOUT=30          # Connection timeout (seconds)
NARRATOR_DB_POOL_RECYCLE=300         # Connection recycle time (seconds)
NARRATOR_DB_ECHO=false               # Enable SQL logging

# File storage settings
NARRATOR_FILE_STORAGE_PATH=/path/to/files  # Storage directory
NARRATOR_MAX_FILE_SIZE=52428800            # 50MB max file size
NARRATOR_MAX_STORAGE_SIZE=5368709120       # 5GB max total storage
NARRATOR_ALLOWED_MIME_TYPES=image/jpeg,application/pdf  # Allowed file types

# Logging
NARRATOR_LOG_LEVEL=INFO              # Log level
```

## Quick Start

### Basic Thread Storage

```python
import asyncio
from narrator import ThreadStore, Thread, Message

async def main():
    # Create an in-memory store for development
    store = await ThreadStore.create()
    
    # Create a thread
    thread = Thread(title="My Conversation")
    
    # Add messages
    thread.add_message(Message(role="user", content="Hello!"))
    thread.add_message(Message(role="assistant", content="Hi there!"))
    
    # Save the thread
    await store.save(thread)
    
    # Retrieve the thread
    retrieved = await store.get(thread.id)
    print(f"Thread: {retrieved.title}")
    print(f"Messages: {len(retrieved.messages)}")

asyncio.run(main())
```

### File Storage

```python
import asyncio
from narrator import FileStore

async def main():
    # Create a file store
    store = await FileStore.create()
    
    # Save a file
    content = b"Hello, world!"
    metadata = await store.save(content, "hello.txt", "text/plain")
    
    print(f"File ID: {metadata['id']}")
    print(f"Storage path: {metadata['storage_path']}")
    
    # Retrieve the file
    retrieved_content = await store.get(metadata['id'])
    print(f"Content: {retrieved_content.decode()}")

asyncio.run(main())
```

### Database Storage

```python
import asyncio
from narrator import ThreadStore

async def main():
    # Use SQLite for persistent storage
    store = await ThreadStore.create("sqlite+aiosqlite:///conversations.db")
    
    # Use PostgreSQL for production
    # store = await ThreadStore.create("postgresql+asyncpg://user:pass@localhost/dbname")
    
    # The API is the same regardless of backend
    thread = Thread(title="Persistent Conversation")
    await store.save(thread)

asyncio.run(main())
```

## Configuration

### Database Configuration

The Narrator supports multiple database backends:

#### Memory storage (Default)
```python
from narrator import ThreadStore

# Use factory pattern for immediate connection validation
store = await ThreadStore.create()  # Uses memory backend

# Thread operations are immediate
thread = Thread()
await store.save(thread)
```

Key characteristics:
- Fastest possible performance (direct dictionary access)
- No persistence (data is lost when program exits)
- No setup required (works out of the box)
- Perfect for scripts and one-off conversations
- Great for testing and development

#### PostgreSQL storage
```python
from narrator import ThreadStore

# Use factory pattern for immediate connection validation
db_url = "postgresql+asyncpg://user:pass@localhost/dbname"
try:
    store = await ThreadStore.create(db_url)
    print("Connected to database successfully")
except Exception as e:
    print(f"Database connection failed: {e}")
    # Handle connection failure appropriately

# Must save threads and changes to persist
thread = Thread()
await store.save(thread)  # Required
thread.add_message(message)
await store.save(thread)  # Save changes

# Always use thread.id with database storage
result = await store.get(thread.id)
```

Key characteristics:
- Async operations for non-blocking I/O
- Persistent storage (data survives program restarts)
- Cross-session support (can access threads from different processes)
- Production-ready
- Automatic schema management through SQLAlchemy
- Connection validation at startup with factory pattern

#### SQLite storage
```python
from narrator import ThreadStore

# Use factory pattern for immediate connection validation
db_url = "sqlite+aiosqlite:///path/to/db.sqlite"
store = await ThreadStore.create(db_url)

# Or use in-memory SQLite database
store = await ThreadStore.create("sqlite+aiosqlite://")  # In-memory SQLite
```

### File Storage Configuration

```python
from narrator import FileStore

# Create a FileStore instance with factory pattern
file_store = await FileStore.create(
    base_path="/path/to/files",  # Optional custom path
    max_file_size=100 * 1024 * 1024,  # 100MB (optional)
    max_storage_size=10 * 1024 * 1024 * 1024  # 10GB (optional)
)

# Or use default settings from environment variables
file_store = await FileStore.create()
```

## Advanced Usage

### Using ThreadStore and FileStore Together

```python
import asyncio
from narrator import ThreadStore, FileStore, Thread, Message

async def main():
    # Create stores
    thread_store = await ThreadStore.create("sqlite+aiosqlite:///main.db")
    file_store = await FileStore.create("/path/to/files")
    
    # Create a thread with file attachment
    thread = Thread(title="Document Discussion")
    
    # Create a message with an attachment
    message = Message(role="user", content="Here's a document")
    
    # Add file content
    pdf_content = b"..."  # Your PDF content
    message.add_attachment(pdf_content, filename="document.pdf")
    
    thread.add_message(message)
    
    # Save thread (attachments are processed automatically)
    await thread_store.save(thread)
    
    print(f"Thread saved with ID: {thread.id}")

asyncio.run(main())
```

### Message Attachments

Messages can include file attachments that are automatically processed:

```python
import asyncio
from narrator import Thread, Message, Attachment, FileStore

async def main():
    file_store = await FileStore.create()
    
    # Create a message with an attachment
    message = Message(role="user", content="Here's a document")
    
    # Add file content
    pdf_content = b"..."  # Your PDF content
    attachment = Attachment(filename="document.pdf", content=pdf_content)
    message.add_attachment(attachment)
    
    # Process and store the attachment
    await attachment.process_and_store(file_store)
    
    # The attachment now has extracted text and metadata
    print(f"Status: {attachment.status}")
    print(f"File ID: {attachment.file_id}")
    if attachment.attributes:
        print(f"Extracted text: {attachment.attributes.get('text', 'N/A')[:100]}...")

asyncio.run(main())
```

### Platform Integration

Threads can be linked to external platforms:

```python
import asyncio
from narrator import Thread, ThreadStore

async def main():
    store = await ThreadStore.create()
    
    # Create a thread linked to Slack
    thread = Thread(
        title="Support Ticket #123",
        platforms={
            "slack": {
                "channel": "C1234567",
                "thread_ts": "1234567890.123"
            }
        }
    )
    
    await store.save(thread)
    
    # Find threads by platform
    slack_threads = await store.find_by_platform("slack", {"channel": "C1234567"})
    print(f"Found {len(slack_threads)} Slack threads in channel")

asyncio.run(main())
```

## Database CLI

The Narrator includes a CLI tool for database management:

```bash
# Initialize database tables
narrator-db init --database-url "postgresql+asyncpg://user:pass@localhost/dbname"

# Initialize using environment variable
export NARRATOR_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/dbname"
narrator-db init

# Check database status
narrator-db status --database-url "postgresql+asyncpg://user:pass@localhost/dbname"

# Check status using environment variable
narrator-db status
```

Available commands:
- `narrator-db init` - Initialize database tables
- `narrator-db status` - Check database connection and basic statistics

## Migration from Tyler

If you're migrating from the original Tyler package:

1. **Update imports**:
   ```python
   # Before
   from tyler import ThreadStore, FileStore, Thread, Message

   # After
   from narrator import ThreadStore, FileStore, Thread, Message
   ```

2. **Update environment variables**:
   ```bash
   # Before
   TYLER_DB_POOL_SIZE=5
   TYLER_FILE_STORAGE_PATH=/path/to/files

   # After
   NARRATOR_DB_POOL_SIZE=5
   NARRATOR_FILE_STORAGE_PATH=/path/to/files
   ```

3. **Remove registry usage**:
   ```python
   # Before (with registry)
   from tyler.utils.registry import register_thread_store, get_thread_store
   register_thread_store("default", store)
   store = get_thread_store("default")

   # After (direct usage)
   store = await ThreadStore.create("your-database-url")
   # Use store directly
   ```

4. **Database compatibility**: The database schema is fully compatible, so existing data will work without changes.

## API Reference

### ThreadStore

#### Methods

- `await ThreadStore.create(database_url=None)`: Factory method to create and initialize a store
- `await store.save(thread)`: Save a thread to storage
- `await store.get(thread_id)`: Retrieve a thread by ID
- `await store.delete(thread_id)`: Delete a thread
- `await store.list(limit=100, offset=0)`: List threads with pagination
- `await store.find_by_attributes(attributes)`: Find threads by custom attributes
- `await store.find_by_platform(platform_name, properties)`: Find threads by platform
- `await store.list_recent(limit=None)`: List recent threads

### FileStore

#### Methods

- `await FileStore.create(base_path=None, ...)`: Factory method to create and validate a store
- `await store.save(content, filename, mime_type=None)`: Save file content
- `await store.get(file_id, storage_path=None)`: Retrieve file content
- `await store.delete(file_id, storage_path=None)`: Delete a file
- `await store.get_storage_size()`: Get total storage size
- `await store.check_health()`: Check storage health

### Models

#### Thread
- `id`: Unique thread identifier
- `title`: Thread title
- `messages`: List of messages
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `attributes`: Custom attributes dictionary
- `platforms`: Platform-specific metadata

#### Message
- `id`: Unique message identifier
- `role`: Message role (user, assistant, system, tool)
- `content`: Message content
- `attachments`: List of file attachments
- `timestamp`: Message timestamp
- `metrics`: Performance metrics

#### Attachment
- `filename`: Original filename
- `mime_type`: File MIME type
- `file_id`: Storage file ID
- `storage_path`: Path in storage
- `status`: Processing status (pending, stored, failed)
- `attributes`: Processed content and metadata

## Development

### Running Tests

To run the test suite locally:

```bash
# Install development dependencies
uv sync --extra dev

# Run tests with coverage
uv run pytest tests/ --cov=narrator --cov-report=term-missing --cov-branch --cov-report=term --no-cov-on-fail -v

# Run tests without coverage (faster)
uv run pytest tests/ -v
```

### Test Requirements

The test suite requires:
- Python 3.12+
- pytest with async support
- Test coverage reporting
- System dependencies (libmagic for file type detection)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite to ensure everything works
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: [Repository Issues](https://github.com/adamwdraper/the-narrator/issues)
- Documentation: [API Reference](https://github.com/adamwdraper/the-narrator#api-reference) 