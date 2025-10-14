# Technical Design Review (TDR) — Reasoning Content as Top-Level Field

**Author**: AI Agent + Adam Draper  
**Date**: 2025-10-14  
**Links**: 
- Spec: `/directive/specs/reasoning-content-top-level/spec.md`
- Impact: `/directive/specs/reasoning-content-top-level/impact.md`
- Previous PR: #71 (thinking tokens initial implementation)

---

## 1. Summary

Refactor reasoning content from `message.metrics['reasoning_content']` to `message.reasoning_content` (top-level field), and unify `reasoning_effort` + `thinking` parameters into a single `reasoning` parameter.

This is a pre-release architecture fix for the thinking tokens feature (just merged in PR #71). Since we haven't released yet, we can make this breaking change cleanly without affecting external users.

**Benefits:**
- Better developer experience (obvious API)
- Semantically correct (reasoning is content, not metrics)
- Mirrors OpenAI/LiteLLM structure
- Provider-agnostic (one parameter for all)
- Simpler, cleaner codebase

**Effort:** 1-2 days (small refactor, ~50 lines changed)

## 2. Decision Drivers & Non‑Goals

### Drivers
- **Developer experience** - Make reasoning easy to access
- **Semantic correctness** - Content belongs at top level, not in metrics
- **API standards** - Match OpenAI/LiteLLM structure (`message.reasoning_content`)
- **Provider agnosticism** - One parameter works for all models
- **Pre-release window** - No external users yet, can refactor freely

### Non‑Goals
- Structured thinking blocks (keep as plain text)
- Anthropic-specific fields on Message
- Reasoning in chat completion context (still don't send back)
- Cost tracking per reasoning type
- Migration of production data (no data exists yet)

## 3. Current State — Codebase Map

### Relevant Modules

**Narrator (`packages/narrator/`):**
```
narrator/
├── models/
│   └── message.py              # Message model with metrics dict
└── database/
    ├── models.py               # MessageRecord with metrics JSONB column
    └── storage_backend.py      # Save/load logic
```

**Tyler (`packages/tyler/`):**
```
tyler/
├── models/
│   ├── agent.py                # Has reasoning_effort + thinking params
│   └── completion_handler.py  # Passes params to LiteLLM
└── tests/
    └── models/
        └── test_agent_thinking_tokens.py  # Tests check metrics
```

### Current Implementation (PR #71)

**Message storage:**
```python
# Tyler creates message (agent.py line ~1104)
message.metrics["reasoning_content"] = ''.join(map(str, current_thinking))
message.metrics["thinking_blocks"] = final_message.thinking_blocks  # Anthropic
```

**Agent parameters:**
```python
# agent.py lines 162-163
reasoning_effort: Optional[str] = Field(default=None, ...)
thinking: Optional[Dict[str, Any]] = Field(default=None, ...)
```

**LiteLLM call:**
```python
# completion_handler.py lines 147-151
if self.reasoning_effort:
    params["reasoning_effort"] = self.reasoning_effort
if self.thinking:
    params["thinking"] = self.thinking
```

### Database Schema

**Current MessageRecord:**
```python
class MessageRecord(Base):
    # ... fields ...
    metrics = Column(JSONBCompat, nullable=False, default={})  # ← reasoning here
```

## 4. Proposed Design

### Part 1: Message Field

**Add to Narrator Message model:**
```python
class Message(BaseModel):
    # ... existing fields ...
    content: Optional[Union[str, List[Union[TextContent, ImageContent]]]] = None
    
    # NEW: Reasoning content at top level
    reasoning_content: Optional[str] = Field(
        default=None,
        description="Model's reasoning/thinking process (for models that support it)"
    )
```

**Add to MessageRecord:**
```python
class MessageRecord(Base):
    # ... existing columns ...
    reasoning_content = Column(Text, nullable=True)  # NEW
```

**Database migration:**
```sql
-- SQLite and PostgreSQL
ALTER TABLE messages ADD COLUMN reasoning_content TEXT;
```

### Part 2: Unified reasoning Parameter

**Replace two parameters with one:**
```python
class Agent(Model):
    # REMOVE:
    # reasoning_effort: Optional[str] = None
    # thinking: Optional[Dict] = None
    
    # ADD:
    reasoning: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="""
        Enable reasoning/thinking tokens for supported models.
        - String: 'low', 'medium', 'high' (recommended for most use cases)
        - Dict: Provider-specific advanced config (e.g., {'type': 'enabled', 'budget_tokens': 1024})
        """
    )
```

**Update CompletionHandler:**
```python
class CompletionHandler:
    def __init__(self, ..., reasoning: Optional[Union[str, Dict]] = None):
        self.reasoning = reasoning
    
    def _build_completion_params(self, ...):
        # ... existing code ...
        
        # Map reasoning to provider-specific format
        if self.reasoning:
            reasoning_params = self._map_reasoning_params(self.reasoning)
            params.update(reasoning_params)
        
        return params
    
    def _map_reasoning_params(self, reasoning: Union[str, Dict]) -> Dict[str, Any]:
        """Map unified reasoning parameter to provider-specific format."""
        if isinstance(reasoning, str):
            # Simple string format → most providers use reasoning_effort
            return {"reasoning_effort": reasoning}
        
        elif isinstance(reasoning, dict):
            # Dict format - check what it contains
            if "type" in reasoning:
                # Anthropic format: {"type": "enabled", "budget_tokens": 1024}
                return {"thinking": reasoning}
            elif "effort" in reasoning:
                # Alternative dict format: {"effort": "low"}
                return {"reasoning_effort": reasoning["effort"]}
            else:
                # Unknown format - pass as reasoning_effort (most compatible)
                return {"reasoning": reasoning}
        
        return {}
```

### Part 3: Tyler Integration

**Update _go_stream() to use top-level field:**
```python
# Current (line ~1104):
if current_thinking:
    metrics["reasoning_content"] = ''.join(map(str, current_thinking))

# New:
# (Remove from metrics entirely)
reasoning_content = ''.join(map(str, current_thinking)) if current_thinking else None

# Later when creating message:
assistant_message = Message(
    role="assistant",
    content=content,
    reasoning_content=reasoning_content,  # ← Top-level!
    tool_calls=current_tool_calls,
    metrics=metrics  # No reasoning here
)
```

## 5. Alternatives Considered

### Option A: Property Accessors (NOT CHOSEN)
```python
@property
def reasoning_content(self):
    return self.metrics.get('reasoning_content')
```

**Pros:** No schema change  
**Cons:** ❌ Still in wrong place semantically, ❌ Hidden implementation

### Option B: Separate Messages (NOT CHOSEN)
```python
Message(role="reasoning", content="thinking...")
Message(role="assistant", content="answer")
```

**Pros:** Chronological  
**Cons:** ❌ Clutters thread, ❌ Non-standard role, ❌ Complex filtering

### Option C: Chosen - Top-Level Field
**Pros:** ✅ Semantic, ✅ Discoverable, ✅ Matches standards  
**Cons:** Schema change (acceptable pre-release)

## 6. Data Model & Contract Changes

### Message Model

**Add fields:**
```python
reasoning_content: Optional[str] = None
```

**Remove from metrics default:**
```python
# Current default includes reasoning - remove it
metrics: Dict[str, Any] = Field(default_factory=lambda: {
    "model": None,
    "timing": {...},
    "usage": {...}
    # NO reasoning_content here
})
```

### Database Schema

**Migration:**
```sql
-- messages table
ALTER TABLE messages ADD COLUMN reasoning_content TEXT;
```

**Impact:**
- ✅ Backward compatible (nullable column)
- ✅ No data migration needed (pre-release)
- ✅ Index not needed (rarely queried directly)

### Agent API

**Parameter change:**
```python
# Before
reasoning_effort: Optional[str] = None
thinking: Optional[Dict[str, Any]] = None

# After  
reasoning: Optional[Union[str, Dict[str, Any]]] = None
```

## 7. Security, Privacy, Compliance

**No security changes:**
- Same data, different field location
- Same access controls apply
- No new PII concerns

## 8. Observability & Operations

**No observability changes needed:**
- Reasoning field transparent
- Existing metrics unchanged (just don't include reasoning)
- No new monitoring required

## 9. Rollout & Migration

### Rollout Strategy

**Single PR approach:**
1. Update Narrator Message + schema
2. Update Tyler Agent + CompletionHandler
3. Update all tests
4. Update documentation
5. Deploy together (atomic)

**No feature flag needed** - Pre-release refactor

### Migration

**Database:**
- Auto-migration on first ThreadStore init
- Add column if not exists
- No data transformation needed

**Code:**
- All changes in one PR
- Update all references atomically
- Tests verify correctness

## 10. Test Strategy & Spec Coverage

### Spec→Test Mapping

| Spec AC | Test | Priority |
|---------|------|----------|
| AC1 | `test_message_reasoning_content_top_level` | P0 |
| AC2 | `test_database_stores_reasoning_content` | P0 |
| AC3 | `test_agent_reasoning_parameter_string` | P0 |
| AC4 | `test_agent_reasoning_parameter_dict_anthropic` | P0 |
| AC5 | `test_reasoning_provider_agnostic_storage` | P1 |
| AC6 | `test_old_messages_without_reasoning` | P0 |
| Negative | `test_invalid_reasoning_format` | P1 |

### Test Implementation

**Narrator tests:**
```python
def test_message_reasoning_content_field():
    """Test reasoning_content as top-level field"""
    msg = Message(
        role="assistant",
        content="Answer",
        reasoning_content="Thinking..."
    )
    assert msg.reasoning_content == "Thinking..."
    assert "reasoning_content" not in msg.metrics

async def test_database_saves_reasoning():
    """Test reasoning persists to database"""
    store = await ThreadStore.create("sqlite+aiosqlite:///:memory:")
    thread = Thread()
    thread.add_message(Message(
        role="assistant",
        content="42",
        reasoning_content="2+2=4, so 40+2=42"
    ))
    
    await store.save(thread)
    loaded = await store.get(thread.id)
    
    assert loaded.messages[-1].reasoning_content == "2+2=4, so 40+2=42"
```

**Tyler tests:**
```python
async def test_reasoning_parameter_unified():
    """Test single reasoning parameter"""
    # String format
    agent1 = Agent(name="test", reasoning="low")
    # Should pass reasoning_effort to LiteLLM
    
    # Dict format (Anthropic)
    agent2 = Agent(name="test", reasoning={"type": "enabled"})
    # Should pass thinking to LiteLLM
```

### CI Requirements
- All existing tests must pass
- New tests must pass
- Database migration must succeed in CI

## 11. Risks & Open Questions

### Known Risks

**Risk 1: Database migration in CI**
- **Mitigation:** Use in-memory SQLite for tests
- **Action:** Test migration separately before PR

**Risk 2: Breaking existing code in examples**
- **Mitigation:** Update all examples in same PR
- **Action:** Grep for `reasoning_effort` and update

### Open Questions

**Q1: Remove `thinking_blocks` entirely?**
- **Status:** Recommend YES - adds complexity, text is enough
- **Proposed:** Only store `reasoning_content` (plain text)

**Q2: Validate `reasoning` parameter values?**
- **Status:** Let LiteLLM handle validation
- **Proposed:** Accept any value, let downstream error

**Q3: Keep metrics for reasoning at all?**
- **Status:** NO - move entirely to top-level field
- **Proposed:** Clean separation: content fields vs system metrics

## 12. Milestones / Plan

### Phase 1: Narrator Changes (Day 1)
1. ✅ Add `reasoning_content` field to Message
2. ✅ Add column to MessageRecord  
3. ✅ Create database migration
4. ✅ Update serialization (model_dump)
5. ✅ Write Narrator tests

### Phase 2: Tyler Changes (Day 1-2)
6. ✅ Remove `reasoning_effort` and `thinking` from Agent
7. ✅ Add `reasoning` parameter
8. ✅ Update CompletionHandler with mapping logic
9. ✅ Update `_go_stream()` to set top-level field
10. ✅ Update Tyler tests

### Phase 3: Documentation & Examples (Day 2)
11. ✅ Update streaming guide
12. ✅ Update examples (007_thinking_tokens_streaming.py)
13. ✅ Update configs (tyler-chat-config.yaml)
14. ✅ Update README

### Phase 4: Validation (Day 2)
15. ✅ Run full test suite
16. ✅ Test database migration
17. ✅ Manual test with real API
18. ✅ Create PR

**Total: 1-2 days**

---

## Approval Gate

**DO NOT START CODING UNTIL THIS TDR IS REVIEWED AND APPROVED**

**Approver:** _______________ Date: _______________

