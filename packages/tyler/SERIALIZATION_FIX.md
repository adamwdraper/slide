# Agent Serialization Fix

## Problem

When a Tyler `Agent` is serialized to Weave and then deserialized, helper objects like `message_factory` and `completion_handler` were being included in serialization. This could cause issues because:

1. These objects are plain Python classes (not Pydantic models)
2. They may contain references to non-serializable objects
3. After deserialization, they could be in an invalid state or missing entirely

The reported bug indicated that in some cases, even module-level objects like loggers could be inadvertently serialized as strings, leading to errors like:

```python
AttributeError: 'str' object has no attribute 'debug'
```

## Solution

We implemented a fix that follows the same pattern already used for `thread_store` and `file_store`:

### 1. Mark Helper Objects as Excluded

```python
# Helper objects excluded from serialization (recreated on deserialization)
message_factory: Optional[MessageFactory] = Field(default=None, exclude=True, ...)
completion_handler: Optional[CompletionHandler] = Field(default=None, exclude=True, ...)
```

### 2. Extract Initialization Logic

Created a `_initialize_helpers()` method that contains all the initialization logic for helper objects:

```python
def _initialize_helpers(self):
    """Initialize or reinitialize helper objects and internal state."""
    self._prompt = AgentPrompt()
    self._tool_attributes_cache = {}
    self.message_factory = MessageFactory(self.name, self.model_name)
    self.completion_handler = CompletionHandler(...)
    # ... rest of initialization
```

### 3. Add Post-Initialization Hook

Implemented a `model_post_init()` hook that Pydantic v2 calls after deserialization:

```python
def model_post_init(self, __context: Any) -> None:
    """Pydantic v2 hook called after model initialization."""
    # Only reinitialize if helpers are missing (indicates deserialization)
    if self.message_factory is None or self.completion_handler is None:
        logger.debug(f"Reinitializing helper objects for agent {self.name}")
        self._initialize_helpers()
```

## Benefits

1. **Predictable Behavior**: Helper objects are always properly initialized, whether creating a new Agent or deserializing one
2. **No Serialization Bloat**: Helper objects are excluded from serialization, keeping the serialized representation clean
3. **Prevents Errors**: Eliminates AttributeErrors from trying to use string-serialized objects
4. **Maintains Compatibility**: Existing code continues to work without changes

## Test Coverage

Added comprehensive test suite in `test_agent_serialization.py`:

- ✅ Helper objects excluded from `model_dump()`
- ✅ Helper objects excluded from JSON serialization
- ✅ Helper objects recreated after deserialization
- ✅ Deserialized agents can run successfully
- ✅ Multiple serialization cycles work correctly
- ✅ Edge cases (reasoning config, tools, MCP config)
- ✅ Simulated Weave roundtrip scenarios
- ✅ Logger remains module-level (not serialized)

## Usage

No changes required for existing code. The fix is transparent:

```python
# Create an agent
agent = Agent(name="MyAgent", model_name="gpt-4.1")

# Serialize (e.g., Weave does this)
agent_dict = agent.model_dump()

# Deserialize (e.g., Weave does this)
restored_agent = Agent(**agent_dict)

# Helper objects are automatically recreated
assert restored_agent.message_factory is not None
assert restored_agent.completion_handler is not None

# Agent works normally
result = await restored_agent.run(thread)
```

## Related

This fix follows the same pattern as the existing exclusions for:
- `thread_store` (line 177) - excluded because it contains database connections
- `file_store` (line 178) - excluded because it contains file system state

Both of these are recreated in `__init__` if not provided, just like our helper objects.

