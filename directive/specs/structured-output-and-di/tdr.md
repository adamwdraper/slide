# Technical Design Review (TDR) — Structured Output & Dependency Injection

**Author**: AI Agent  
**Date**: 2024-12-30  
**Links**: [Spec](./spec.md), [Impact](./impact.md)

---

## 1. Summary
This TDR covers three related features to close the gap with Pydantic AI:
1. **Structured Output**: Allow users to specify a Pydantic model as `response_type`, and receive validated structured data from LLM responses
2. **Validation Retry**: Automatically retry when LLM output fails schema validation, feeding error details back to the model
3. **Tool Context Injection**: Allow tools to receive runtime dependencies via a `ctx` parameter

All features are opt-in with zero breaking changes.

## 2. Decision Drivers & Non-Goals
- **Drivers**: Competitive parity with Pydantic AI, developer ergonomics, production reliability
- **Non-Goals**: 
  - Full generic `RunContext[T]` typing (future enhancement)
  - Streaming structured outputs (requires complete response)
  - Agent-level default `response_type` (start with per-run only)

## 3. Current State — Codebase Map

### Key modules
- `tyler/models/agent.py`: Agent class with `run()`, `stream()` methods
- `tyler/models/execution.py`: `AgentResult`, `ExecutionEvent`, `EventType`
- `tyler/utils/tool_runner.py`: `ToolRunner` class for tool execution
- `tyler/models/completion_handler.py`: LLM completion handling

### Existing interfaces
```python
# Current AgentResult
@dataclass
class AgentResult:
    thread: Thread
    new_messages: List[Message]
    content: Optional[str]

# Current run() signature
async def run(self, thread_or_id: Union[Thread, str]) -> AgentResult
```

## 4. Proposed Design

### 4.1 New Models

#### RetryConfig
```python
# tyler/models/retry_config.py
from pydantic import BaseModel, Field

class RetryConfig(BaseModel):
    """Configuration for structured output validation retry."""
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_on_validation_error: bool = Field(default=True)
    backoff_base_seconds: float = Field(default=0.5, ge=0)
```

#### ToolContext (type alias)
```python
# Simple dict-based context for MVP
ToolContext = Dict[str, Any]
```

#### Updated AgentResult
```python
@dataclass
class AgentResult:
    thread: Thread
    new_messages: List[Message]
    content: Optional[str]
    structured_data: Optional[BaseModel] = None  # NEW
    validation_retries: int = 0  # NEW: number of retries needed
```

#### New Exceptions
```python
class StructuredOutputError(Exception):
    """Raised when structured output validation fails after retries."""
    def __init__(self, message: str, validation_errors: List[Dict], last_response: Any):
        super().__init__(message)
        self.validation_errors = validation_errors
        self.last_response = last_response

class ToolContextError(Exception):
    """Raised when a tool requires context but none was provided."""
    pass
```

### 4.2 Agent Changes

#### New Fields
```python
class Agent(BaseModel):
    # ... existing fields ...
    retry_config: Optional[RetryConfig] = Field(
        default=None, 
        description="Configuration for structured output validation retry"
    )
```

#### Updated run() Signature
```python
async def run(
    self,
    thread_or_id: Union[Thread, str],
    response_type: Optional[Type[BaseModel]] = None,  # NEW
    tool_context: Optional[Dict[str, Any]] = None,    # NEW
) -> AgentResult:
```

### 4.3 Structured Output Flow

```python
async def _run_with_structured_output(
    self, 
    thread: Thread, 
    response_type: Type[BaseModel],
    tool_context: Optional[Dict[str, Any]] = None
) -> AgentResult:
    """Run agent expecting structured output."""
    
    # Generate JSON schema from Pydantic model
    schema = response_type.model_json_schema()
    
    # Build messages with schema instruction
    messages = self._build_messages_for_structured_output(thread, schema)
    
    retry_count = 0
    max_retries = self.retry_config.max_retries if self.retry_config else 0
    
    while True:
        # Call LLM with JSON schema response format
        response = await acompletion(
            model=self.model_name,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_type.__name__,
                    "schema": schema,
                    "strict": True
                }
            },
            # ... other params ...
        )
        
        try:
            # Parse and validate
            raw_json = json.loads(response.choices[0].message.content)
            validated = response_type.model_validate(raw_json)
            
            return AgentResult(
                thread=thread,
                new_messages=[...],
                content=response.choices[0].message.content,
                structured_data=validated,
                validation_retries=retry_count
            )
            
        except ValidationError as e:
            retry_count += 1
            
            if retry_count > max_retries:
                raise StructuredOutputError(
                    f"Validation failed after {retry_count} attempts",
                    validation_errors=e.errors(),
                    last_response=raw_json
                )
            
            # Add correction message and retry
            messages.append({
                "role": "user",
                "content": f"Your response did not match the required schema.\n\nErrors:\n{e.json()}\n\nPlease correct and try again."
            })
            
            await asyncio.sleep(self.retry_config.backoff_base_seconds * retry_count)
```

### 4.4 Tool Context Injection

```python
# In tool_runner.py

async def run_tool_async(
    self, 
    tool_name: str, 
    parameters: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None  # NEW
) -> Any:
    """Execute an async tool, optionally injecting context."""
    
    tool = self.tools[tool_name]
    implementation = tool['implementation']
    
    # Check if tool expects context
    sig = inspect.signature(implementation)
    params = list(sig.parameters.keys())
    
    expects_context = params and params[0] in ('ctx', 'context')
    
    if expects_context:
        if context is None:
            raise ToolContextError(
                f"Tool '{tool_name}' requires context but none was provided"
            )
        # Inject context as first argument
        if tool['is_async']:
            return await implementation(context, **parameters)
        else:
            return await asyncio.to_thread(
                lambda: implementation(context, **parameters)
            )
    else:
        # Standard execution without context
        if tool['is_async']:
            return await implementation(**parameters)
        else:
            return await asyncio.to_thread(implementation, **parameters)
```

## 5. Alternatives Considered

### Structured Output
- **Option A (chosen)**: Per-run `response_type` parameter
  - Pros: Flexible, explicit, backward compatible
  - Cons: Must pass on each call
- **Option B**: Agent-level default `response_type`
  - Pros: Less repetition
  - Cons: Less flexible for agents that need different schemas
  - Decision: Can add later, start simple

### Tool Context
- **Option A (chosen)**: Dict-based `tool_context`
  - Pros: Simple, no new types, flexible
  - Cons: No type checking on context contents
- **Option B**: Full generic `RunContext[T]`
  - Pros: Full type safety
  - Cons: Complex, requires TypeVar handling
  - Decision: Start with dict, upgrade later if needed

## 6. Data Model & Contract Changes

### AgentResult
```python
# Before
@dataclass
class AgentResult:
    thread: Thread
    new_messages: List[Message]
    content: Optional[str]

# After
@dataclass
class AgentResult:
    thread: Thread
    new_messages: List[Message]
    content: Optional[str]
    structured_data: Optional[BaseModel] = None
    validation_retries: int = 0
```

### Backward Compatibility
- All new fields have defaults
- Existing code accessing `result.thread`, `result.content` unchanged
- New fields only populated when features are used

## 7. Security, Privacy, Compliance
- No AuthN/AuthZ changes
- Tool context may contain sensitive data (DB connections, API keys)
  - Developers are responsible for what they inject
  - Context is not persisted or logged
- No PII handling changes

## 8. Observability & Operations
- Log structured output mode activation at DEBUG level
- Log validation failures and retry attempts at WARNING level
- Log context injection at DEBUG level
- Existing Weave tracing will capture these automatically

## 9. Rollout & Migration
- No feature flags needed (features are opt-in by design)
- No data migration required
- No breaking changes, can release immediately

## 10. Test Strategy & Spec Coverage (TDD)

### Test Files
- `tests/test_structured_output.py` - Structured output feature
- `tests/test_retry_config.py` - Retry configuration and behavior
- `tests/test_tool_context.py` - Context injection

### Test Cases

| Spec Criterion | Test ID |
|----------------|---------|
| Structured output returns validated model | `test_structured_output_basic` |
| No response_type returns None structured_data | `test_structured_output_disabled_by_default` |
| Validation failure raises StructuredOutputError | `test_validation_failure_raises` |
| Retry on validation failure | `test_retry_on_validation_failure` |
| Max retries exceeded | `test_max_retries_exceeded` |
| Tool with ctx receives context | `test_tool_context_injection` |
| Tool without ctx ignores context | `test_tool_no_context_backward_compat` |
| Missing context raises error | `test_tool_missing_context_error` |

## 11. Risks & Open Questions
- **Risk**: LLM may not support `response_format` with JSON schema
  - Mitigation: Fall back to instruction-based prompting, document model requirements
- **Open Question**: Should we support nested Pydantic models?
  - Resolution: Yes, Pydantic's `model_json_schema()` handles this automatically

## 12. Milestones / Plan

### Phase 1: Core Implementation
1. Add `RetryConfig` model
2. Update `AgentResult` with new fields
3. Add `StructuredOutputError` and `ToolContextError`
4. Update `Agent.run()` with new parameters

### Phase 2: Structured Output
1. Implement `_run_with_structured_output()` method
2. Add retry logic
3. Write tests

### Phase 3: Tool Context
1. Update `ToolRunner.run_tool_async()` with context support
2. Update `Agent` to pass context to tool runner
3. Write tests

### Phase 4: Documentation
1. Update docstrings
2. Add examples
3. Update API reference

---

**Approval Gate**: Ready for implementation.

