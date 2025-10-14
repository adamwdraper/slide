# Impact Analysis — Reasoning Content as Top-Level Field

## Modules/packages likely touched

### Narrator Changes (Medium Impact)
- **`packages/narrator/narrator/models/message.py`** (5-10 lines)
  - Add `reasoning_content: Optional[str]` field
  - Remove from metrics default (if needed)

- **`packages/narrator/narrator/database/models.py`** (1-2 lines)
  - Add `reasoning_content = Column(Text, nullable=True)` to MessageRecord

- **`packages/narrator/narrator/database/migrations/`** (NEW, ~20 lines)
  - Create migration to add `reasoning_content` column
  - Optional field, backward compatible

### Tyler Changes (Medium Impact)
- **`packages/tyler/tyler/models/agent.py`** (10-20 lines)
  - Remove `reasoning_effort` and `thinking` fields
  - Add single `reasoning: Optional[Union[str, Dict]]` field
  - Update `_go_stream()` to set `reasoning_content` on Message (not metrics)
  - Update CompletionHandler initialization

- **`packages/tyler/tyler/models/completion_handler.py`** (15-25 lines)
  - Remove `reasoning_effort` and `thinking` from `__init__`
  - Add `reasoning` parameter
  - Add `_map_reasoning_params()` method to convert to provider format
  - Update `_build_completion_params()` to use mapped params

### Testing Changes (High Impact)
- **`packages/tyler/tests/models/test_agent_thinking_tokens.py`** (10-20 lines)
  - Update tests to check `message.reasoning_content` (not metrics)
  - Update tests to use `reasoning="low"` (not `reasoning_effort`)
  - Update assertions

- **`packages/narrator/tests/`** (20-30 lines new)
  - Test reasoning_content field serialization
  - Test database save/load with reasoning
  - Test None/empty reasoning

### Documentation Changes (Low-Medium Impact)
- **`docs/guides/streaming-responses.mdx`** (10-15 lines)
  - Update to show `message.reasoning_content` 
  - Update Agent examples to use `reasoning` parameter

- **`examples/007_thinking_tokens_streaming.py`** (5-10 lines)
  - Update to use `reasoning` parameter
  - Update to access `message.reasoning_content`

### Config Changes (Low Impact)
- **`tyler-chat-config.yaml`** (1 line)
  - Change `reasoning_effort: "low"` to `reasoning: "low"`

- **`tyler-chat-config-wandb.yaml`** (1 line)
  - Same change

## Contracts to update (APIs, events, schemas, migrations)

### Message Model Contract (Breaking - but pre-release)

**Before:**
```python
message.metrics = {
    "reasoning_content": "thinking...",
    "thinking_blocks": [...]
}
```

**After:**
```python
message.reasoning_content = "thinking..."
message.metrics = {
    # reasoning_content removed
}
```

**Impact:** ✅ Breaking but acceptable (pre-release, internal API)

### Agent API Contract (Breaking - but pre-release)

**Before:**
```python
Agent(
    reasoning_effort="low",  # ← Remove
    thinking={"type": "enabled"}  # ← Remove
)
```

**After:**
```python
Agent(
    reasoning="low"  # ← Unified
    # or
    reasoning={"type": "enabled", "budget_tokens": 1024}
)
```

**Impact:** ✅ Breaking but simpler, better DX

### Database Schema Change

**Add column:**
```sql
ALTER TABLE messages ADD COLUMN reasoning_content TEXT;
```

**Migration strategy:**
- New column, nullable
- No existing data to migrate (pre-release)
- Optional field (backward compatible for reads)

### Event Data (No Change)
```python
ExecutionEvent(
    type=EventType.LLM_THINKING_CHUNK,
    data={"thinking_chunk": "...", "thinking_type": "reasoning"}
)
```

**Impact:** ✅ No change - events unchanged

## Risks

### Security
**Risk Level:** 🟢 **NONE**

- No new security concerns
- Reasoning already treated as content
- Same access controls apply

### Performance/Availability
**Risk Level:** 🟢 **LOW**

- **Database:** One additional TEXT column per message
  - Impact: ~10-20% storage for messages with reasoning
  - Negligible performance impact
  
- **Serialization:** No change (same data, different location)
  
- **Query performance:** Better (can query reasoning_content directly vs JSON path)

**Mitigation:** None needed

### Data Integrity
**Risk Level:** 🟢 **NONE**

- **No existing data** - Pre-release refactor
- **New field is optional** - NULL values valid
- **Type safety** - Optional[str] clearly defined

### Backward Compatibility
**Risk Level:** 🟢 **NONE**

- **Haven't released yet** - No external users
- **Internal only** - Can update all code at once
- **Tests** - Update in same PR

## Observability needs

### Logs
**No new logging needed**
- Reasoning field access is transparent
- Use existing logging for database operations

### Metrics
**No new metrics needed**
- Same metrics as before
- Storage location change is internal

### Alerts
**No alerts needed**
- Not a runtime change
- Schema addition only

## Testing Strategy

### Unit Tests
- Test Message with reasoning_content field
- Test Message without reasoning (None)
- Test serialization/deserialization
- Test database save/load

### Integration Tests
- Test full flow: Agent → Message → ThreadStore → Retrieval
- Test with different providers (Anthropic, DeepSeek)
- Test `reasoning` parameter variants (string, dict)

### Migration Tests
- Test schema migration runs successfully
- Test old messages (without reasoning) load correctly
- Test new messages save reasoning_content

## Success Metrics

**Technical:**
- [ ] All tests pass
- [ ] Database migration runs clean
- [ ] No performance regression

**Developer Experience:**
- [ ] One line to access reasoning: `message.reasoning_content`
- [ ] One parameter for all providers: `reasoning="low"`
- [ ] Clear, discoverable API

## Open Questions

1. **Should we keep `thinking_blocks` at all?**
   - Current: In metrics
   - Proposed: Remove entirely, just use `reasoning_content` text
   - Recommendation: Remove - adds complexity, not needed

2. **Reasoning parameter validation?**
   - Valid strings: "low", "medium", "high"
   - Valid dicts: Any dict (provider-specific)
   - Recommendation: Accept any value, let LiteLLM validate

3. **Database migration timing?**
   - Run automatically on ThreadStore init?
   - Manual migration script?
   - Recommendation: Auto-migration (Alembic)

