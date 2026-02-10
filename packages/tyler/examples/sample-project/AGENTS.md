# Project Guidelines

## Code Style
- Use type hints for all function signatures
- Follow PEP 8 naming conventions
- Prefer `async`/`await` over threads for I/O-bound operations

## Error Handling
- Always use specific exception types (never bare `except:`)
- Include meaningful error messages with context
- Use `logging` instead of `print` for diagnostics

## API Conventions
- Use `httpx` for HTTP requests (async-native)
- Always set timeouts on external calls
- Return typed dataclasses or Pydantic models, not raw dicts
