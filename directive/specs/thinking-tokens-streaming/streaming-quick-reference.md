# Tyler Streaming API - Quick Reference Card

## Current State: What Works Today

### ✅ Event Streaming (Fully Functional)
```python
from tyler import Agent, Thread, Message, EventType

async for event in agent.go(thread, stream=True):
    match event.type:
        case EventType.LLM_STREAM_CHUNK:
            print(event.data['content_chunk'], end="")
        case EventType.TOOL_SELECTED:
            print(f"\n🔧 {event.data['tool_name']}")
        case EventType.TOOL_RESULT:
            print(f"✅ {event.data['result']}")
```

### ✅ Raw Streaming (Fully Functional)
```python
async for chunk in agent.go(thread, stream="raw"):
    if hasattr(chunk.choices[0].delta, 'content'):
        print(chunk.choices[0].delta.content, end="")
```

---

## ❌ What's Missing

### Thinking Tokens (Event Mode)
```python
# ❌ This doesn't exist yet
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_THINKING_CHUNK:  # Not available
        print(f"[Thinking: {event.data['thinking_chunk']}]")
```

**Workaround TODAY:** Use raw mode
```python
# ✅ This works now!
async for chunk in agent.go(thread, stream="raw"):
    delta = chunk.choices[0].delta
    if hasattr(delta, 'thinking'):  # Anthropic
        print(f"[Thinking: {delta.thinking}]")
    if hasattr(delta, 'reasoning_content'):  # OpenAI o1
        print(f"[Reasoning: {delta.reasoning_content}]")
```

### Stream Options
```python
# ❌ This doesn't exist yet
agent = Agent(
    name="test",
    model_name="gpt-4o",
    stream_options={"include_usage": True}  # Not available
)
```

---

## Model-Specific Thinking Fields

| Provider | Model | Thinking Field | Raw Mode | Event Mode |
|----------|-------|----------------|----------|------------|
| OpenAI | gpt-4.1 | `reasoning_content` | ✅ Works | ❌ Lost |
| OpenAI | o1-preview | `reasoning_content` | ✅ Works | ❌ Lost |
| Anthropic | claude-3-7-sonnet | `thinking` | ✅ Works | ❌ Lost |
| Anthropic | claude-3.5-sonnet | `thinking` | ✅ Works | ❌ Lost |
| Google | gemini-2.0 | TBD | 🟡 Unknown | 🟡 Unknown |

---

## Diff: What Needs to Be Added

### EventType enum
```diff
class EventType(Enum):
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_STREAM_CHUNK = "llm_stream_chunk"
+   LLM_THINKING_CHUNK = "llm_thinking_chunk"  # NEW
+   LLM_FINISH = "llm_finish"                  # NEW
    
    TOOL_SELECTED = "tool_selected"
    TOOL_RESULT = "tool_result"
    
    MESSAGE_CREATED = "message_created"
+   AGENT_UPDATED = "agent_updated"            # NEW
    
    EXECUTION_COMPLETE = "execution_complete"
```

### Agent class
```diff
class Agent(Model):
    name: str
    model_name: str
    purpose: str
    temperature: float = 0.7
+   stream_options: Optional[Dict[str, Any]] = None  # NEW
```

### _go_stream method
```diff
async for chunk in streaming_response:
    delta = chunk.choices[0].delta
    
    # Handle content
    if hasattr(delta, 'content') and delta.content:
        yield ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            data={"content_chunk": delta.content}
        )
    
+   # NEW: Handle thinking
+   thinking = None
+   thinking_type = None
+   
+   if hasattr(delta, 'thinking'):
+       thinking = delta.thinking
+       thinking_type = "thinking"
+   elif hasattr(delta, 'reasoning_content'):
+       thinking = delta.reasoning_content
+       thinking_type = "reasoning"
+   
+   if thinking:
+       yield ExecutionEvent(
+           type=EventType.LLM_THINKING_CHUNK,
+           data={
+               "thinking_chunk": thinking,
+               "thinking_type": thinking_type
+           }
+       )
```

---

## Testing Checklist

### ✅ Already Tested
- [x] Basic streaming with content
- [x] Tool call streaming
- [x] Raw mode passes through chunks
- [x] Usage in final chunk
- [x] Error handling in streams

### ⏳ Need to Add
- [ ] Thinking tokens in event mode (Anthropic)
- [ ] Reasoning content in event mode (OpenAI o1)
- [ ] stream_options parameter
- [ ] Finish reason events
- [ ] Agent updated events (handoffs)
- [ ] Provider-specific field preservation

---

## Example Flows

### Flow 1: Simple Content Streaming (Works Today)
```
User: "Hello"
    ↓
LLM generates: "Hello! How can I help you?"
    ↓
Events:
  - LLM_REQUEST
  - LLM_STREAM_CHUNK("Hello! ")
  - LLM_STREAM_CHUNK("How can ")
  - LLM_STREAM_CHUNK("I help you?")
  - LLM_RESPONSE
  - MESSAGE_CREATED
  - EXECUTION_COMPLETE
```

### Flow 2: Tool Usage (Works Today)
```
User: "What's 5 + 3?"
    ↓
LLM decides: Use calculator tool
    ↓
Events:
  - LLM_REQUEST
  - LLM_RESPONSE (with tool_calls)
  - MESSAGE_CREATED (assistant with tool_calls)
  - TOOL_SELECTED (calculator)
  - TOOL_RESULT (8)
  - MESSAGE_CREATED (tool result)
  - LLM_REQUEST (second turn)
  - LLM_STREAM_CHUNK("The answer is 8")
  - LLM_RESPONSE
  - MESSAGE_CREATED
  - EXECUTION_COMPLETE
```

### Flow 3: Thinking Tokens (Needs Implementation)
```
User: "What's 123 * 456?"
    ↓
LLM thinks: "Let me calculate..." (o1 model)
LLM responds: "The answer is 56,088"
    ↓
Events (CURRENT - missing thinking):
  - LLM_REQUEST
  - LLM_STREAM_CHUNK("Let me calculate...")  ❌ Wrong!
  - LLM_STREAM_CHUNK("The answer is 56,088")
  - LLM_RESPONSE
  - MESSAGE_CREATED
  - EXECUTION_COMPLETE

Events (RECOMMENDED - with thinking):
  - LLM_REQUEST
  - LLM_THINKING_CHUNK("Let me calculate...")  ✅ Separated!
  - LLM_STREAM_CHUNK("The answer is 56,088")
  - LLM_FINISH("stop")                         ✅ New!
  - LLM_RESPONSE
  - MESSAGE_CREATED
  - EXECUTION_COMPLETE
```

---

## Migration: What Changes for Users?

### No Breaking Changes! ✅

**Existing code keeps working:**
```python
# ✅ This code won't break
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data['content_chunk'], end="")
```

**New features are additive:**
```python
# Users can opt-in when ready
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data['content_chunk'], end="")
    elif event.type == EventType.LLM_THINKING_CHUNK:  # NEW
        print(f"💭 {event.data['thinking_chunk']}")
```

---

## Quick Wins

### Win 1: Document Raw Mode Thinking (1 day)
Add to docs:
```markdown
## Using Thinking Tokens Today

Tyler's raw streaming mode already preserves thinking tokens:

```python
async for chunk in agent.go(thread, stream="raw"):
    delta = chunk.choices[0].delta
    
    # Anthropic thinking
    if hasattr(delta, 'thinking'):
        print(f"[Thinking: {delta.thinking}]")
    
    # OpenAI o1 reasoning  
    if hasattr(delta, 'reasoning_content'):
        print(f"[Reasoning: {delta.reasoning_content}]")
```
```

### Win 2: Add Example (1 day)
```python
# examples/006_thinking_tokens.py
"""
Demonstrates thinking token support in raw streaming mode.
Works with OpenAI o1 and Anthropic Claude models.
"""
```

### Win 3: Add Test (1 day)
```python
# tests/models/test_thinking_raw.py
@pytest.mark.asyncio
async def test_raw_mode_preserves_thinking():
    """Raw streaming should preserve thinking tokens"""
    agent = Agent(name="test", model_name="claude-3-7-sonnet-20250219")
    thread = Thread()
    thread.add_message(Message(role="user", content="Solve 2+2"))
    
    thinking_found = False
    async for chunk in agent.go(thread, stream="raw"):
        if hasattr(chunk.choices[0].delta, 'thinking'):
            thinking_found = True
    
    assert thinking_found
```

**Total: 3 days to document existing capability!**

---

## Standards Compliance Matrix

| Standard Feature | Tyler Status | Priority |
|------------------|--------------|----------|
| **OpenAI Agents SDK** | | |
| Raw response events | 🟡 Similar (raw mode) | Medium |
| Run item events | ✅ Yes (MESSAGE_CREATED, TOOL_RESULT) | ✅ Done |
| Agent events | ❌ No | High |
| **LiteLLM** | | |
| Basic streaming | ✅ Yes | ✅ Done |
| stream_options | ❌ No | High |
| Thinking tokens | 🟡 Raw mode only | High |
| Provider compatibility | ✅ Yes | ✅ Done |
| **Our Additions** | | |
| Tool observability | ✅ Better than standards! | ✅ Done |
| Execution events | ✅ Unique to Tyler | ✅ Done |
| Error tracking | ✅ Comprehensive | ✅ Done |

---

## Implementation Roadmap

### Week 1: Thinking Support
- [ ] Add `LLM_THINKING_CHUNK` event type
- [ ] Update `_go_stream` to emit thinking events
- [ ] Add tests for Anthropic and OpenAI o1
- [ ] Document thinking in event mode
- [ ] Document thinking in raw mode (already works!)
- [ ] Add example: `006_thinking_tokens.py`

### Week 2: Stream Control
- [ ] Add `stream_options` parameter to Agent
- [ ] Pass `stream_options` to LiteLLM in `step()`
- [ ] Add `LLM_FINISH` event type
- [ ] Emit finish reason events
- [ ] Test with `include_usage`
- [ ] Add example: `007_stream_options.py`

### Week 3: Agent Events
- [ ] Add `AGENT_UPDATED` event type
- [ ] Emit during handoffs
- [ ] Test multi-agent streaming
- [ ] Add example: `008_agent_handoffs_streaming.py`

### Week 4: Polish
- [ ] Add structured thinking blocks (optional)
- [ ] Add event categories (optional)
- [ ] Comprehensive docs update
- [ ] Blog post: "Tyler Streaming API"

---

## One-Pager Summary

### Problem
Tyler doesn't explicitly support thinking/reasoning tokens that models like OpenAI o1 and Anthropic Claude generate.

### Impact
- Users can't distinguish between reasoning and response
- Missing transparency for decision-making process
- Not aligned with OpenAI Agents SDK and LiteLLM standards

### Solution
Add `LLM_THINKING_CHUNK` event type and `stream_options` parameter.

### Effort
- **Quick win (document raw mode):** 3 days
- **Full implementation:** 2-3 weeks
- **No breaking changes:** ✅ Fully backward compatible

### Example
**Before:**
```python
# Everything mixed together
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data['content_chunk'])  # "Let me think... The answer is 42"
```

**After:**
```python
# Clear separation
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_THINKING_CHUNK:
        print(f"💭 {event.data['thinking_chunk']}")  # "Let me think..."
    elif event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data['content_chunk'])  # "The answer is 42"
```

### Files to Change
1. `tyler/models/execution.py` - Add event types
2. `tyler/models/agent.py` - Add stream_options, update _go_stream
3. `tests/models/test_agent_streaming.py` - Add tests
4. `docs/guides/streaming-responses.mdx` - Update docs
5. `examples/006_thinking_tokens.py` - Add example

### Decision
- ✅ Proceed with implementation?
- ✅ Document raw mode workaround first?
- ✅ Create spec/impact/TDR documents?

