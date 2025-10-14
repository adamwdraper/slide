# Tyler Streaming API Analysis

## Overview
This document analyzes Tyler's current streaming implementation compared to OpenAI Agents SDK and LiteLLM standards, with a focus on raw streaming, thinking tokens, and tool usage.

## Current State: Tyler's Streaming API

### Streaming Modes

Tyler supports three modes via the `stream` parameter in `agent.go()`:

1. **Non-Streaming** (`stream=False`)
   - Returns `AgentResult` after completion
   - Synchronous processing

2. **Event Streaming** (`stream=True` or `stream="events"`)
   - Returns `AsyncGenerator[ExecutionEvent, None]`
   - High-level observability events
   - Transformed/structured data

3. **Raw Streaming** (`stream="raw"`)
   - Returns `AsyncGenerator[Any, None]`
   - Passes through raw LiteLLM chunks
   - OpenAI-compatible format
   - Tools ARE executed (fully agentic)

### Event Types (Event Streaming Mode)

```python
class EventType(Enum):
    # LLM interactions
    LLM_REQUEST = "llm_request"          # {message_count, model, temperature}
    LLM_RESPONSE = "llm_response"        # {content, tool_calls, tokens, latency_ms}
    LLM_STREAM_CHUNK = "llm_stream_chunk" # {content_chunk}
    
    # Tool execution  
    TOOL_SELECTED = "tool_selected"      # {tool_name, arguments, tool_call_id}
    TOOL_EXECUTING = "tool_executing"    # {tool_name, tool_call_id}
    TOOL_RESULT = "tool_result"          # {tool_name, result, duration_ms, tool_call_id}
    TOOL_ERROR = "tool_error"            # {tool_name, error, tool_call_id}
    
    # Message management
    MESSAGE_CREATED = "message_created"  # {message: Message}
    
    # Control flow
    ITERATION_START = "iteration_start"  # {iteration_number, max_iterations}
    ITERATION_LIMIT = "iteration_limit"  # {iterations_used}
    EXECUTION_ERROR = "execution_error"  # {error_type, message, traceback}
    EXECUTION_COMPLETE = "execution_complete" # {duration_ms, total_tokens}
```

### What Tyler Currently Handles in Streaming

**Event Streaming (`_go_stream`):**
```python
# From chunk.choices[0].delta
if hasattr(delta, 'content') and delta.content is not None:
    current_content.append(delta.content)
    yield ExecutionEvent(
        type=EventType.LLM_STREAM_CHUNK,
        timestamp=datetime.now(UTC),
        data={"content_chunk": delta.content}
    )

# Tool calls are accumulated and processed
if hasattr(delta, 'tool_calls') and delta.tool_calls:
    # ... complex tool call accumulation logic
```

**Raw Streaming (`_go_stream_raw`):**
```python
async for chunk in streaming_response:
    # Yield raw chunk unmodified
    yield chunk
    
    # Track content and tool_calls for internal agent iteration
    # but don't transform or add new fields
```

### What Tyler Does NOT Currently Handle

❌ **Thinking Tokens/Blocks**
- No handling of `delta.thinking` (Anthropic)
- No handling of `reasoning_content` (OpenAI o1)
- No handling of `extended_thinking` fields

❌ **Advanced Usage Information**
- No `stream_options={"include_usage": True}` support
- Usage only available in final chunk (if LiteLLM provides it)

❌ **Provider-Specific Fields**
- No handling of `thinking_blocks` from Anthropic
- No handling of reasoning tokens from o1 models
- No handling of other provider-specific delta fields

❌ **Finish Reasons Detail**
- Only tracks final `finish_reason` but doesn't emit events for different finish reasons
- No distinction between `stop`, `tool_calls`, `length`, `content_filter` in events

---

## Standard: OpenAI Agents SDK Streaming

### Streaming Architecture

The OpenAI Agents SDK provides structured streaming with distinct event types:

**1. Raw Response Events** (`RawResponsesStreamEvent`)
```python
async for event in result.stream_events():
    if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
        print(event.data.delta, end="", flush=True)
```

- Raw events passed directly from LLM
- OpenAI Responses API format
- Event types: `response.created`, `response.output_text.delta`, `response.output_text.done`, etc.
- Token-by-token streaming

**2. Run Item Events** (`RunItemStreamEvent`)
```python
if event.type == "run_item_stream_event":
    if event.item.type == "tool_call_item":
        print("-- Tool was called")
    elif event.item.type == "tool_call_output_item":
        print(f"-- Tool output: {event.item.output}")
    elif event.item.type == "message_output_item":
        print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
```

- Higher-level events
- Signify completion of items (messages, tool calls)
- Structured insights into agent operations

**3. Agent Events** (`AgentUpdatedStreamEvent`)
```python
elif event.type == "agent_updated_stream_event":
    print(f"Agent updated: {event.new_agent.name}")
```

- Agent state changes
- Handoff events
- Context switches

### Key Differences from Tyler

| Feature | Tyler | OpenAI Agents SDK |
|---------|-------|-------------------|
| **Raw Events** | Single stream of chunks | Typed raw response events |
| **Event Types** | 12 event types | 3 top-level categories (raw, item, agent) |
| **Item Completion** | MESSAGE_CREATED | run_item_stream_event |
| **Agent Changes** | ❌ Not tracked | agent_updated_stream_event |
| **Response Format** | OpenAI Responses API format | OpenAI Responses API format ✅ |

---

## Standard: LiteLLM Streaming

### LiteLLM's Reasoning Content Standardization

**IMPORTANT:** As of LiteLLM v1.63.0+, LiteLLM **standardizes reasoning/thinking content** across providers!

According to the [official LiteLLM documentation](https://docs.litellm.ai/docs/reasoning_content):

**Non-streaming responses:**
```python
response = completion(
    model="anthropic/claude-3-7-sonnet-20250219",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    reasoning_effort="low"
)

# Standardized fields:
response.choices[0].message.reasoning_content  # String - ALL providers
response.choices[0].message.thinking_blocks    # List[Dict] - Anthropic only
```

**Supported providers:** Deepseek, Anthropic API, Bedrock, Vertex AI, OpenRouter, XAI, Google AI Studio, Perplexity, Mistral AI, Groq

**Streaming behavior:** Need to verify if `delta.reasoning_content` is also standardized in streaming chunks.

### Basic Streaming

```python
response = completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True
)

for chunk in response:
    print(chunk['choices'][0]['delta'].get('content', ''), end="")
```

### Advanced Features

**1. Usage Information**
```python
response = completion(
    model="gpt-4",
    messages=messages,
    stream=True,
    stream_options={"include_usage": True}
)

# Last chunk before [DONE] includes:
# {
#     "usage": {
#         "prompt_tokens": 10,
#         "completion_tokens": 20,
#         "total_tokens": 30
#     }
# }
```

**2. Thinking Tokens (Anthropic)**
```python
# Anthropic's Claude models emit thinking blocks
for chunk in response:
    delta = chunk['choices'][0]['delta']
    
    # Regular content
    if 'content' in delta:
        print(delta['content'], end="")
    
    # Thinking tokens/blocks
    if 'thinking' in delta:
        print(f"[Thinking: {delta['thinking']}]")
    
    # Thinking blocks (structured)
    if 'thinking_blocks' in chunk:
        for block in chunk['thinking_blocks']:
            print(f"[Reasoning: {block['content']}]")
```

**3. Reasoning Content (OpenAI o1)**
```python
# OpenAI o1 models use reasoning_content
for chunk in response:
    delta = chunk['choices'][0]['delta']
    
    # Regular content
    if 'content' in delta:
        print(delta['content'], end="")
    
    # Reasoning tokens
    if 'reasoning_content' in delta:
        print(f"[Reasoning: {delta['reasoning_content']}]")
```

**4. Extended Thinking**
```python
# Some models support extended_thinking
response = completion(
    model="claude-3-7-sonnet-20250219",
    messages=messages,
    stream=True,
    extended_thinking=True  # Enable extended reasoning
)

for chunk in response:
    # Extended thinking appears in delta or separate fields
    if hasattr(chunk.choices[0].delta, 'extended_thinking'):
        print(f"[Extended: {chunk.choices[0].delta.extended_thinking}]")
```

### Key Capabilities

✅ **Multiple Provider Support**
- OpenAI, Anthropic, Google, Azure, etc.
- Unified interface across providers
- Provider-specific features exposed

✅ **Thinking/Reasoning**
- `thinking` field (Anthropic)
- `reasoning_content` field (OpenAI o1)
- `thinking_blocks` (structured reasoning)
- `extended_thinking` parameter

✅ **Tool Usage**
- Full OpenAI tool calling format
- Structured outputs
- Tool call streaming in delta

✅ **Usage Tracking**
- `stream_options={"include_usage": True}`
- Per-request usage statistics
- Available before stream ends

---

## Gap Analysis

### What Tyler is Missing

#### 1. Thinking Tokens Support

**Problem:** Tyler does not capture or emit thinking/reasoning content from models.

**Impact:**
- Users cannot see model's reasoning process
- Important for transparency and debugging
- Missing feature parity with o1 and Claude models

**Example of what's missing:**
```python
# This does NOT work in Tyler currently
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_THINKING_CHUNK:  # ❌ Doesn't exist
        print(f"[Thinking: {event.data['thinking_chunk']}]")
```

#### 2. Raw Stream Provider-Specific Fields

**Problem:** Raw streaming mode yields chunks but doesn't preserve all provider-specific fields.

**Impact:**
- Users building OpenAI-compatible proxies miss provider features
- Cannot distinguish between regular content and reasoning
- No way to access thinking_blocks, reasoning_content, etc.

**Current behavior:**
```python
# Raw mode yields chunks, but thinking fields might be present
async for chunk in agent.go(thread, stream="raw"):
    # chunk has the fields, but no documentation or explicit support
    if hasattr(chunk.choices[0].delta, 'reasoning_content'):
        # This works but is undocumented and untested
        print(chunk.choices[0].delta.reasoning_content)
```

#### 3. Advanced Usage Options

**Problem:** No support for `stream_options` parameter.

**Impact:**
- Cannot request usage info in advance
- Must wait for final chunk
- No control over what additional data is included

**Missing:**
```python
# Tyler doesn't support this
agent = Agent(
    name="test",
    model_name="gpt-4",
    stream_options={"include_usage": True}  # ❌ Not supported
)
```

#### 4. Higher-Level Event Categories

**Problem:** Tyler has flat event types vs. OpenAI's categorized events.

**Impact:**
- Less structured event hierarchy
- Harder to filter and process events
- No distinction between raw and processed events in event mode

**Tyler's flat structure:**
```python
EventType.LLM_STREAM_CHUNK    # Processed content
EventType.LLM_RESPONSE        # Complete response
EventType.TOOL_SELECTED       # Tool event
```

**OpenAI's hierarchical structure:**
```python
# Category: raw_response_event
#   - response.created
#   - response.output_text.delta
#   - response.output_text.done
#
# Category: run_item_stream_event
#   - tool_call_item
#   - tool_call_output_item
#   - message_output_item
#
# Category: agent_updated_stream_event
```

#### 5. Agent State Change Events

**Problem:** No events for agent context switches or handoffs in streaming.

**Impact:**
- Cannot track when agent delegates to another agent in stream
- No visibility into handoff events in real-time
- Have to wait for MESSAGE_CREATED to see handoff results

#### 6. Finish Reason Events

**Problem:** Finish reasons are tracked but not exposed as events.

**Impact:**
- Cannot react to different finish reasons in streaming mode
- No event for length limit, content filter, etc.
- Have to infer from message state

**Missing:**
```python
# This doesn't exist
if event.type == EventType.LLM_FINISH:  # ❌
    reason = event.data['finish_reason']
    if reason == 'length':
        print("Warning: Response truncated")
    elif reason == 'content_filter':
        print("Warning: Content filtered")
```

---

## Recommendations

### Tier 1: Critical for Standard Compliance

#### 1. Add Thinking Token Support in Event Streaming

**IMPORTANT: LiteLLM Reasoning Content Standardization**

As of **LiteLLM v1.63.0+**, LiteLLM standardizes reasoning content in completion responses:
- **Non-streaming:** `response.choices[0].message.reasoning_content` (standardized across ALL providers)
- **Streaming:** Tyler should check if `delta.reasoning_content` is also standardized, OR if streaming still uses provider-specific fields

**Recommended approach:** Check BOTH standardized and provider-specific fields:
1. First check `delta.reasoning_content` (LiteLLM standard)
2. Fallback to provider-specific fields if needed:
   - Anthropic: `delta.thinking`
   - OpenAI o1: `delta.reasoning_content` (same as standard)
   - Extended: `delta.extended_thinking`

**Add new event type:**
```python
class EventType(Enum):
    # ... existing events ...
    LLM_THINKING_CHUNK = "llm_thinking_chunk"  # {thinking_chunk, thinking_type}
```

**Update `_go_stream` to handle thinking:**
```python
async for chunk in streaming_response:
    if not hasattr(chunk, 'choices') or not chunk.choices:
        continue
    
    delta = chunk.choices[0].delta
    
    # Existing content handling
    if hasattr(delta, 'content') and delta.content is not None:
        current_content.append(delta.content)
        yield ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            timestamp=datetime.now(UTC),
            data={"content_chunk": delta.content}
        )
    
    # NEW: Handle thinking/reasoning
    # LiteLLM v1.63.0+ standardizes to 'reasoning_content' in non-streaming
    # Check both standardized and provider-specific fields for streaming
    thinking_content = None
    thinking_type = None
    
    # LiteLLM standardized field (v1.63.0+) - check this first
    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
        thinking_content = delta.reasoning_content
        thinking_type = "reasoning"
    
    # Fallback: Provider-specific fields (for older LiteLLM or if streaming not standardized)
    # Anthropic thinking
    elif hasattr(delta, 'thinking') and delta.thinking is not None:
        thinking_content = delta.thinking
        thinking_type = "thinking"
    
    # Extended thinking (various providers)
    elif hasattr(delta, 'extended_thinking') and delta.extended_thinking is not None:
        thinking_content = delta.extended_thinking
        thinking_type = "extended_thinking"
    
    if thinking_content:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            timestamp=datetime.now(UTC),
            data={
                "thinking_chunk": thinking_content,
                "thinking_type": thinking_type  # Identifies which provider/type
            }
        )
```

**Benefits:**
- Users can display thinking process in real-time
- Full transparency for o1 and Claude reasoning
- Maintains separation between content and thinking

#### 2. Document and Test Raw Streaming with Thinking

**Update documentation:**
```python
# docs/guides/streaming-responses.mdx
"""
### Raw Streaming with Thinking Tokens

When using `stream="raw"`, Tyler passes through all fields from the LLM,
including provider-specific thinking and reasoning content:

```python
async for chunk in agent.go(thread, stream="raw"):
    if hasattr(chunk, 'choices') and chunk.choices:
        delta = chunk.choices[0].delta
        
        # Regular content
        if hasattr(delta, 'content') and delta.content:
            print(delta.content, end="")
        
        # Anthropic thinking
        if hasattr(delta, 'thinking') and delta.thinking:
            print(f"\\n[Thinking: {delta.thinking}]")
        
        # OpenAI o1 reasoning
        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
            print(f"\\n[Reasoning: {delta.reasoning_content}]")
```
"""
```

**Add test:**
```python
# tests/models/test_agent_streaming.py
@pytest.mark.asyncio
async def test_raw_streaming_preserves_thinking_tokens(mock_thinking_response):
    """Test that raw streaming passes through thinking tokens."""
    agent = Agent(
        name="thinking-agent",
        model_name="claude-3-7-sonnet-20250219",
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Solve 2+2"))
    
    chunks = []
    thinking_chunks = []
    
    async for chunk in agent.go(thread, stream="raw"):
        chunks.append(chunk)
        if hasattr(chunk.choices[0].delta, 'thinking'):
            thinking_chunks.append(chunk.choices[0].delta.thinking)
    
    assert len(thinking_chunks) > 0, "Should have thinking tokens"
    assert len(chunks) > len(thinking_chunks), "Should have content and thinking"
```

#### 3. Add stream_options Support

**Update Agent.__init__:**
```python
class Agent(Model):
    # ... existing fields ...
    stream_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Options for streaming responses (e.g., {'include_usage': True})"
    )
```

**Pass to LiteLLM in step():**
```python
async def step(self, thread: Thread, stream: bool = False) -> Tuple[Any, Dict[str, Any]]:
    # ... existing code ...
    
    completion_kwargs = {
        "model": self.model_name,
        "messages": thread.to_openai_messages(),
        "temperature": self.temperature,
        "stream": stream,
    }
    
    # Add stream_options if provided
    if stream and self.stream_options:
        completion_kwargs["stream_options"] = self.stream_options
    
    # ... rest of method ...
```

**Benefits:**
- Control over usage information timing
- Future-proof for new stream options
- Matches OpenAI API surface

### Tier 2: Improve Developer Experience

#### 4. Add Finish Reason Events

**Add new event type:**
```python
class EventType(Enum):
    # ... existing events ...
    LLM_FINISH = "llm_finish"  # {finish_reason}
```

**Emit before LLM_RESPONSE:**
```python
# In _go_stream, after chunk loop
finish_reason = chunk.choices[0].finish_reason if hasattr(chunk.choices[0], 'finish_reason') else None

if finish_reason:
    yield ExecutionEvent(
        type=EventType.LLM_FINISH,
        timestamp=datetime.now(UTC),
        data={"finish_reason": finish_reason}
    )

# Then yield LLM_RESPONSE as before
yield ExecutionEvent(
    type=EventType.LLM_RESPONSE,
    # ...
)
```

**Benefits:**
- React to truncation or filtering
- Better error handling
- Matches OpenAI event granularity

#### 5. Add Agent State Change Events (for handoffs)

**Add new event type:**
```python
class EventType(Enum):
    # ... existing events ...
    AGENT_UPDATED = "agent_updated"  # {previous_agent, new_agent}
```

**Emit during handoffs:**
```python
# When processing handoff tool results
if tool_name == "handoff":
    # Parse handoff result
    new_agent = parse_handoff(result)
    
    yield ExecutionEvent(
        type=EventType.AGENT_UPDATED,
        timestamp=datetime.now(UTC),
        data={
            "previous_agent": self.name,
            "new_agent": new_agent.name,
            "handoff_reason": result.get('reason')
        }
    )
```

**Benefits:**
- Track agent delegation in real-time
- Better observability for multi-agent systems
- Matches OpenAI Agents SDK pattern

#### 6. Categorize Events (Optional)

**Add event categories:**
```python
class EventCategory(Enum):
    RAW_RESPONSE = "raw_response"
    RUN_ITEM = "run_item"
    AGENT_STATE = "agent_state"
    CONTROL = "control"

class EventType(Enum):
    # Category: RAW_RESPONSE
    LLM_STREAM_CHUNK = ("llm_stream_chunk", EventCategory.RAW_RESPONSE)
    LLM_THINKING_CHUNK = ("llm_thinking_chunk", EventCategory.RAW_RESPONSE)
    
    # Category: RUN_ITEM
    MESSAGE_CREATED = ("message_created", EventCategory.RUN_ITEM)
    TOOL_RESULT = ("tool_result", EventCategory.RUN_ITEM)
    
    # Category: AGENT_STATE
    AGENT_UPDATED = ("agent_updated", EventCategory.AGENT_STATE)
    
    # Category: CONTROL
    EXECUTION_COMPLETE = ("execution_complete", EventCategory.CONTROL)
    EXECUTION_ERROR = ("execution_error", EventCategory.CONTROL)
```

**Benefits:**
- Easier event filtering
- Clearer event hierarchy
- Better documentation structure

### Tier 3: Nice to Have

#### 7. Thinking Blocks (Structured Reasoning)

Some providers (like Anthropic) return structured thinking blocks:

```python
# In chunk
{
    "thinking_blocks": [
        {
            "type": "planning",
            "content": "I need to break this down into steps..."
        },
        {
            "type": "analysis",
            "content": "The problem requires..."
        }
    ]
}
```

**Implementation:**
```python
# Add to EventType
LLM_THINKING_BLOCK = "llm_thinking_block"  # {block_type, content, index}

# Emit structured blocks
if hasattr(chunk, 'thinking_blocks'):
    for idx, block in enumerate(chunk.thinking_blocks):
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_BLOCK,
            timestamp=datetime.now(UTC),
            data={
                "block_type": block.get('type', 'unknown'),
                "content": block.get('content', ''),
                "index": idx
            }
        )
```

#### 8. Usage Estimation Events

Emit usage estimates during streaming (before final chunk):

```python
# Track approximate tokens during streaming
estimated_tokens = 0

async for chunk in streaming_response:
    if hasattr(delta, 'content') and delta.content:
        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens += len(delta.content) / 4
        
        # Emit estimate every N chunks
        if chunk_count % 20 == 0:
            yield ExecutionEvent(
                type=EventType.LLM_USAGE_ESTIMATE,
                timestamp=datetime.now(UTC),
                data={
                    "estimated_tokens": int(estimated_tokens),
                    "is_estimate": True
                }
            )
```

---

## Implementation Priority

### Phase 1: Core Thinking Support (Week 1)
1. Add `EventType.LLM_THINKING_CHUNK`
2. Update `_go_stream` to emit thinking chunks
3. Add tests for thinking token handling
4. Document thinking support in raw and event modes

### Phase 2: API Surface (Week 2)
5. Add `stream_options` parameter to Agent
6. Pass `stream_options` to LiteLLM
7. Add finish reason events
8. Test with different providers (Claude, o1, etc.)

### Phase 3: Agent Events (Week 3)
9. Add `EventType.AGENT_UPDATED`
10. Emit during handoffs
11. Add tests for multi-agent streaming
12. Update documentation

### Phase 4: Polish (Week 4)
13. Add structured thinking blocks support
14. Add event categories (optional)
15. Add usage estimation events
16. Comprehensive examples

---

## Example: Updated Streaming with Thinking

### Event Streaming Mode
```python
from tyler import Agent, Thread, Message, EventType

agent = Agent(
    name="reasoning-agent",
    model_name="claude-3-7-sonnet-20250219",  # or gpt-4.1
    purpose="To solve complex problems with reasoning",
    stream_options={"include_usage": True}  # NEW
)

thread = Thread()
thread.add_message(Message(
    role="user",
    content="What's the square root of 12345?"
))

print("🤖 Assistant:")
thinking_buffer = []
content_buffer = []

async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_THINKING_CHUNK:  # NEW
        thinking_buffer.append(event.data['thinking_chunk'])
        print(f"\n[Thinking: {event.data['thinking_chunk']}]", end="")
    
    elif event.type == EventType.LLM_STREAM_CHUNK:
        content_buffer.append(event.data['content_chunk'])
        print(event.data['content_chunk'], end="", flush=True)
    
    elif event.type == EventType.LLM_FINISH:  # NEW
        print(f"\n\n[Finish reason: {event.data['finish_reason']}]")
    
    elif event.type == EventType.TOOL_SELECTED:
        print(f"\n🔧 {event.data['tool_name']}")

print(f"\n\nThinking: {''.join(thinking_buffer)}")
print(f"Response: {''.join(content_buffer)}")
```

### Raw Streaming Mode
```python
# Raw mode automatically includes all fields from LiteLLM
async for chunk in agent.go(thread, stream="raw"):
    if hasattr(chunk, 'choices') and chunk.choices:
        delta = chunk.choices[0].delta
        
        # Regular content
        if hasattr(delta, 'content') and delta.content:
            print(delta.content, end="")
        
        # Thinking (Anthropic)
        if hasattr(delta, 'thinking') and delta.thinking:
            print(f"\n[💭 {delta.thinking}]", end="")
        
        # Reasoning (OpenAI o1)
        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
            print(f"\n[🧠 {delta.reasoning_content}]", end="")
        
        # Tool calls
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            print(f"\n[🔧 Tool call]")
    
    # Usage info (if stream_options enabled)
    if hasattr(chunk, 'usage') and chunk.usage:
        print(f"\n\nTokens: {chunk.usage.total_tokens}")
```

---

## Testing Strategy

### Test Matrix

| Provider | Model | Thinking Field | Test Status |
|----------|-------|----------------|-------------|
| OpenAI | gpt-4.1 | `reasoning_content` | ⏳ To Add |
| OpenAI | gpt-4o | None | ✅ Existing |
| Anthropic | claude-3-7-sonnet | `thinking` | ⏳ To Add |
| Anthropic | claude-3.5-sonnet | `thinking` | ⏳ To Add |
| Google | gemini-2.0 | TBD | ⏳ To Add |

### Test Cases

```python
# Test 1: Thinking tokens in event streaming
@pytest.mark.asyncio
async def test_event_streaming_with_thinking():
    agent = Agent(name="test", model_name="gpt-4.1")
    thread = Thread()
    thread.add_message(Message(role="user", content="Solve 123 * 456"))
    
    thinking_events = []
    content_events = []
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_THINKING_CHUNK:
            thinking_events.append(event)
        elif event.type == EventType.LLM_STREAM_CHUNK:
            content_events.append(event)
    
    assert len(thinking_events) > 0, "Should have thinking chunks"
    assert len(content_events) > 0, "Should have content chunks"

# Test 2: Raw streaming preserves thinking
@pytest.mark.asyncio
async def test_raw_streaming_thinking():
    agent = Agent(name="test", model_name="claude-3-7-sonnet-20250219")
    thread = Thread()
    thread.add_message(Message(role="user", content="Solve 123 * 456"))
    
    thinking_found = False
    
    async for chunk in agent.go(thread, stream="raw"):
        if hasattr(chunk.choices[0].delta, 'thinking'):
            thinking_found = True
            break
    
    assert thinking_found, "Raw mode should preserve thinking field"

# Test 3: stream_options usage
@pytest.mark.asyncio
async def test_stream_options_usage():
    agent = Agent(
        name="test",
        model_name="gpt-4o",
        stream_options={"include_usage": True}
    )
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    usage_found = False
    
    async for chunk in agent.go(thread, stream="raw"):
        if hasattr(chunk, 'usage') and chunk.usage:
            usage_found = True
            assert chunk.usage.total_tokens > 0
            break
    
    assert usage_found, "Should include usage with stream_options"

# Test 4: Finish reason events
@pytest.mark.asyncio
async def test_finish_reason_events():
    agent = Agent(name="test", model_name="gpt-4o", max_tokens=10)
    thread = Thread()
    thread.add_message(Message(role="user", content="Write a long story"))
    
    finish_event = None
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.LLM_FINISH:
            finish_event = event
    
    assert finish_event is not None
    assert finish_event.data['finish_reason'] == 'length'
```

---

## Migration Guide

### For Users: No Breaking Changes

All recommendations are additive:

**Existing code continues to work:**
```python
# This still works exactly as before
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data['content_chunk'], end="")
```

**New features are opt-in:**
```python
# Users can add thinking support when ready
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data['content_chunk'], end="")
    elif event.type == EventType.LLM_THINKING_CHUNK:  # NEW
        print(f"[Thinking: {event.data['thinking_chunk']}]")
```

### For Package Maintainers

1. **Add new EventType values** (backward compatible)
2. **Update _go_stream to emit new events** (additive)
3. **Add stream_options field** (optional, default None)
4. **Update documentation** with examples
5. **Add tests** for new providers/models

---

## Comparison Summary

### Tyler vs OpenAI Agents SDK

| Feature | Tyler Current | Tyler Recommended | OpenAI Agents SDK |
|---------|---------------|-------------------|-------------------|
| **Raw Streaming** | ✅ Yes | ✅ Yes | ✅ Yes (RawResponsesStreamEvent) |
| **Event Streaming** | ✅ Yes (12 types) | ✅ Yes (15+ types) | ✅ Yes (RunItemStreamEvent) |
| **Thinking Tokens** | ❌ No | ✅ Yes (new) | ✅ Yes |
| **Tool Usage Events** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Agent State Events** | ❌ No | ✅ Yes (new) | ✅ Yes (AgentUpdatedStreamEvent) |
| **Finish Reason Events** | ❌ No | ✅ Yes (new) | ✅ Yes |
| **Event Categories** | ❌ No | 🟡 Optional | ✅ Yes (3 categories) |
| **Usage in Stream** | 🟡 Final chunk only | ✅ Yes (stream_options) | ✅ Yes |

### Tyler vs LiteLLM

| Feature | Tyler Current | Tyler Recommended | LiteLLM |
|---------|---------------|-------------------|---------|
| **Basic Streaming** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Provider Compatibility** | ✅ Yes (via LiteLLM) | ✅ Yes | ✅ Yes (15+ providers) |
| **Thinking Tokens** | 🟡 Passed through (raw mode) | ✅ Explicit support | ✅ Yes (thinking, reasoning_content) |
| **Thinking Blocks** | ❌ No | 🟡 Optional | ✅ Yes (Anthropic) |
| **stream_options** | ❌ No | ✅ Yes (new) | ✅ Yes |
| **Extended Thinking** | ❌ No | ✅ Yes (via stream_options) | ✅ Yes |
| **Tool Calls** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Event Abstraction** | ✅ Yes (Tyler-specific) | ✅ Yes | ❌ No (raw chunks only) |

**Key Insight:** Tyler currently sits between LiteLLM (low-level) and OpenAI Agents SDK (high-level), but is missing key features from both:
- Missing **thinking tokens** support (LiteLLM feature)
- Missing **agent state events** (OpenAI Agents SDK feature)

---

## Conclusion

### Current Strengths
- ✅ Good event abstraction with ExecutionEvent
- ✅ Both event and raw streaming modes
- ✅ Comprehensive tool usage tracking
- ✅ OpenAI-compatible raw chunks

### Critical Gaps
- ❌ No thinking/reasoning token support
- ❌ No stream_options support
- ❌ No finish reason events
- ❌ No agent state change events

### Recommended Path Forward

**Phase 1 (Critical):** Add thinking token support
- Add `LLM_THINKING_CHUNK` event type
- Handle `thinking`, `reasoning_content`, `extended_thinking` fields
- Document and test with o1 and Claude models

**Phase 2 (Important):** Enhance streaming control
- Add `stream_options` parameter
- Add `LLM_FINISH` event type
- Support usage information in stream

**Phase 3 (Nice to have):** Improve observability
- Add `AGENT_UPDATED` events for handoffs
- Add structured thinking blocks
- Add event categories

This will bring Tyler to full parity with both OpenAI Agents SDK and LiteLLM standards while maintaining backward compatibility.

