# Technical Design Review (TDR) — Thinking Tokens in Streaming

**Author**: AI Agent + Adam Draper  
**Date**: 2025-10-14  
**Links**: 
- Spec: `/directive/specs/thinking-tokens-streaming/spec.md`
- Impact: `/directive/specs/thinking-tokens-streaming/impact.md`
- LiteLLM Docs: https://docs.litellm.ai/docs/reasoning_content

---

## 1. Summary

We are adding support for thinking/reasoning tokens to Tyler's streaming API. Models like OpenAI o1 and Anthropic Claude emit their reasoning process as separate tokens alongside response content. Tyler currently mixes these together in `LLM_STREAM_CHUNK` events, making it impossible for developers to distinguish reasoning from responses.

This feature adds a new `LLM_THINKING_CHUNK` event type that emits thinking tokens separately. The implementation is minimal (~30-50 lines) because LiteLLM v1.63.0+ already standardizes reasoning content across providers into a `reasoning_content` field. Tyler just needs to check for this field and emit events.

**Key benefits:**
- Developers can display thinking/reasoning separately from responses
- Better transparency and debuggability for AI decisions
- Works across all LiteLLM-supported providers (Anthropic, Deepseek, OpenAI, etc.)
- Zero breaking changes - fully backward compatible

## 2. Decision Drivers & Non‑Goals

### Drivers
- **Transparency requirements**: Users want to see how AI models arrive at decisions
- **Debugging needs**: Developers need to trace model reasoning for agent behavior
- **Standard compliance**: LiteLLM v1.63.0+ provides standardized reasoning_content
- **Low implementation cost**: ~30-50 lines of code, leveraging LiteLLM's heavy lifting
- **User demand**: Anthropic Claude 3.7 Sonnet and OpenAI o1 are production-ready with thinking

### Non‑Goals (Explicitly Out of Scope)
- UI components for displaying thinking (frontend concern)
- Thinking token cost tracking/analytics (future feature)
- Custom thinking token formatting beyond LiteLLM (unnecessary complexity)
- Support for LiteLLM < v1.63.0 (requires standardization)
- Agent-to-agent handoff events (separate feature)
- Finish reason events (separate feature)
- `stream_options` parameter (separate feature, but note it's needed for usage)
- Event categorization/hierarchy (separate feature)

## 3. Current State — Codebase Map

### Key Modules Relevant to This Feature

**Tyler Core (`packages/tyler/`)**
```
tyler/
├── models/
│   ├── agent.py           # Main Agent class with go() and streaming logic
│   │   ├── _go_stream()   # Event streaming implementation (lines ~890-1280)
│   │   ├── _go_stream_raw()  # Raw chunk streaming (lines ~1388-1624)
│   │   └── step()         # LiteLLM completion wrapper (lines ~1720-1850)
│   ├── execution.py       # EventType enum and ExecutionEvent dataclass
│   └── thread.py          # Thread and Message models
└── tests/
    └── models/
        └── test_agent_streaming.py  # Streaming tests
```

**Narrator (`packages/narrator/`)**
```
narrator/
└── models/
    └── message.py         # Message model with flexible metrics dict
```

### Current Streaming Flow

1. **User calls** `agent.go(thread, stream=True)`
2. **Agent._go_stream()** is invoked
3. **Agent.step()** calls LiteLLM's `completion()` with `stream=True`
4. **LiteLLM returns** async generator of chunks
5. **Tyler iterates** chunks, extracts `delta.content` and `delta.tool_calls`
6. **Tyler emits** `ExecutionEvent` objects:
   - `LLM_REQUEST` → `LLM_STREAM_CHUNK` (content) → `LLM_RESPONSE` → `MESSAGE_CREATED`
   - If tool calls: `TOOL_SELECTED` → `TOOL_RESULT` → loop back to step 3
7. **User receives** async generator of events

### Existing Data Models

**ExecutionEvent (packages/tyler/tyler/models/execution.py)**
```python
@dataclass
class ExecutionEvent:
    type: EventType                    # Enum of event types
    timestamp: datetime                # When event occurred
    data: Dict[str, Any]              # Flexible event data
    attributes: Optional[Dict] = None  # Optional metadata
```

**EventType (packages/tyler/tyler/models/execution.py)**
```python
class EventType(Enum):
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_STREAM_CHUNK = "llm_stream_chunk"    # Content chunks
    TOOL_SELECTED = "tool_selected"
    TOOL_RESULT = "tool_result"
    MESSAGE_CREATED = "message_created"
    EXECUTION_COMPLETE = "execution_complete"
    # ... others
```

**Message (packages/narrator/narrator/models/message.py)**
```python
class Message(BaseModel):
    role: str                          # "user", "assistant", "tool"
    content: Optional[str]             # Message content
    tool_calls: Optional[List[Dict]]   # Tool calls if any
    metrics: Optional[Dict] = {}       # Flexible metadata (usage, timing, etc.)
    # ... other fields
```

### External Contracts in Scope

**LiteLLM Streaming Interface:**
```python
# Input
response = litellm.completion(
    model="anthropic/claude-3-7-sonnet-20250219",
    messages=[...],
    reasoning_effort="low",
    stream=True
)

# Output (chunks)
async for chunk in response:
    chunk.choices[0].delta.content           # Regular content
    chunk.choices[0].delta.reasoning_content # NEW: Thinking tokens (LiteLLM v1.63.0+)
    chunk.choices[0].delta.tool_calls        # Tool calls
```

**LiteLLM Non-Streaming Interface (for reference):**
```python
response.choices[0].message.reasoning_content  # Complete reasoning (standardized)
response.choices[0].message.thinking_blocks    # Structured blocks (Anthropic only)
```

### Observability Currently Available

**Logging:**
- Tyler uses standard Python `logging` module
- Logger instance: `from tyler.utils.logger import logger`
- Current log levels: DEBUG, INFO, WARNING, ERROR

**Metrics:**
- No existing metrics infrastructure visible in code
- Metrics stored in `Message.metrics` dict per message (usage, timing)

**Tests:**
- Comprehensive streaming tests in `test_agent_streaming.py`
- Mocked LiteLLM responses for deterministic testing
- AsyncIO-based test fixtures

## 4. Proposed Design (High Level)

### Overall Approach

**Minimal implementation leveraging LiteLLM standardization:**

1. **Add EventType** - Single new enum value `LLM_THINKING_CHUNK`
2. **Check field in streaming** - Look for `delta.reasoning_content` during chunk processing
3. **Emit event** - Yield new event type when thinking detected
4. **Store in message** - Preserve reasoning_content in Message.metrics after streaming
5. **Pass through raw** - No changes to raw streaming (already passes everything through)

**Why this approach:**
- ✅ LiteLLM does all heavy lifting (provider standardization)
- ✅ Tyler just wraps in events (minimal code)
- ✅ Backward compatible (additive only)
- ✅ No new dependencies
- ✅ Follows existing patterns

### Component Responsibilities

**LiteLLM (external dependency):**
- Call provider APIs (Anthropic, OpenAI, etc.)
- Standardize `reasoning_content` across providers
- Stream chunks with unified format
- Handle provider-specific quirks

**Tyler Agent._go_stream():**
- Iterate LiteLLM chunks
- Check for `delta.reasoning_content`
- Emit `LLM_THINKING_CHUNK` events
- Accumulate reasoning for final message

**Tyler Agent._go_stream_raw():**
- Pass through chunks unchanged
- No transformation needed (LiteLLM already standardized)

**Message model:**
- Store `reasoning_content` in metrics dict
- Store `thinking_blocks` if present (Anthropic)

### Interfaces & Data Contracts

**New Event Type:**
```python
class EventType(Enum):
    # ... existing ...
    LLM_THINKING_CHUNK = "llm_thinking_chunk"
```

**Event Data Schema:**
```python
ExecutionEvent(
    type=EventType.LLM_THINKING_CHUNK,
    timestamp=datetime.now(UTC),
    data={
        "thinking_chunk": str,      # The reasoning text
        "thinking_type": str        # "reasoning" (standardized) or "thinking"/"extended_thinking" (fallback)
    }
)
```

**Example Event Flow:**
```
1. LLM_REQUEST
2. LLM_THINKING_CHUNK (chunk 1): "Let me analyze this..."
3. LLM_THINKING_CHUNK (chunk 2): "Step 1: Consider..."
4. LLM_STREAM_CHUNK (chunk 1): "The answer"
5. LLM_STREAM_CHUNK (chunk 2): " is 42"
6. LLM_RESPONSE (complete)
7. MESSAGE_CREATED (with reasoning_content in metrics)
8. EXECUTION_COMPLETE
```

**Message Metrics Extension:**
```python
message.metrics = {
    "usage": {...},              # Existing
    "timing": {...},             # Existing
    "reasoning_content": str,    # NEW - complete reasoning text
    "thinking_blocks": List[Dict] # NEW - structured blocks (Anthropic only)
}
```

### Error Handling

**Missing reasoning_content:**
- Not an error (optional field)
- No event emitted, execution continues normally

**Malformed reasoning data:**
```python
try:
    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
        yield ExecutionEvent(...)
except Exception as e:
    logger.debug(f"Failed to process thinking tokens: {e}")
    # Continue processing other chunks
```

**LiteLLM errors:**
- Already handled by existing error handling
- No new error cases introduced

### Idempotency

Not applicable - streaming is inherently non-idempotent (real-time event generation)

### Performance Expectations

- **Latency impact**: < 1ms per chunk (single hasattr check)
- **Memory impact**: Negligible (reasoning text already buffered by LiteLLM)
- **Throughput**: No impact (pass-through processing)
- **Back-pressure**: Handled by existing async iteration

## 5. Alternatives Considered

### Option A: Check Provider-Specific Fields Only (NOT CHOSEN)

**Approach:** Check `delta.thinking` (Anthropic), `delta.reasoning_content` (OpenAI), etc.

**Pros:**
- Works with older LiteLLM versions
- More explicit provider handling

**Cons:**
- ❌ More complex code (multiple field checks)
- ❌ Need to update when new providers added
- ❌ Doesn't leverage LiteLLM standardization
- ❌ Inconsistent event data across providers

**Why not chosen:** LiteLLM v1.63.0+ provides standardization - we should use it

### Option B: Wait for Final Message Only (NOT CHOSEN)

**Approach:** Don't emit thinking chunks during streaming, only store in final message

**Pros:**
- Even simpler implementation
- No real-time event processing

**Cons:**
- ❌ Defeats purpose of streaming (no real-time thinking visibility)
- ❌ Poor UX (can't show reasoning as it happens)
- ❌ Doesn't meet user requirement for transparency

**Why not chosen:** Users explicitly want real-time thinking visibility

### Option C: Chosen Approach - LiteLLM Standardized Field + Fallback

**Approach:** 
1. Check `delta.reasoning_content` first (LiteLLM standard)
2. Fall back to provider-specific fields if needed
3. Emit events in real-time

**Pros:**
- ✅ Leverages LiteLLM standardization
- ✅ Future-proof (new providers automatically work)
- ✅ Simple implementation (~30 lines)
- ✅ Real-time streaming
- ✅ Fallback for edge cases

**Cons:**
- Requires LiteLLM ≥ v1.63.0 (acceptable trade-off)

**Why chosen:** Best balance of simplicity, maintainability, and functionality

## 6. Data Model & Contract Changes

### EventType Enum Extension

**File:** `packages/tyler/tyler/models/execution.py`

```python
class EventType(Enum):
    # ... existing events unchanged ...
    
    LLM_THINKING_CHUNK = "llm_thinking_chunk"  # NEW
```

**Impact:** ✅ Additive only, no breaking changes

### Message.metrics Schema Extension

**File:** `packages/narrator/narrator/models/message.py`

**Current:**
```python
metrics: Optional[Dict] = {}  # Flexible dict
```

**Enhanced (no schema change, just documentation):**
```python
# metrics can now include:
{
    "usage": {...},                    # Existing
    "timing": {...},                   # Existing
    "reasoning_content": str,          # NEW - Optional
    "thinking_blocks": List[Dict]      # NEW - Optional (Anthropic)
}
```

**Impact:** ✅ Backward compatible - optional fields in existing dict

### API/Event Changes

**No external API changes:**
- Internal event stream only
- Consumers can ignore new event type
- Existing event types unchanged

### Backward Compatibility

**100% backward compatible:**
- New event type ignored by existing code
- Existing events work identically
- No schema migrations needed
- No deprecations

**Verification:**
- Run full existing test suite
- All tests should pass without modification

### Deprecation Plan

None needed - additive only

## 7. Security, Privacy, Compliance

### AuthN/AuthZ Model

**No changes to authentication/authorization:**
- Thinking tokens part of message content
- Same access controls as regular messages
- Thread-level permissions apply unchanged

### Secrets Management

**No new secrets:**
- Uses existing LiteLLM/provider API keys
- No additional credentials needed

### PII Handling

**Thinking tokens may contain PII:**
- Reasoning may reference user data
- Same sensitivity as message content

**Mitigation:**
- Document that thinking tokens should be treated as sensitive
- Apply same PII filters/redactions as message content
- Include in content moderation pipelines if present

**Action items:**
- [ ] Add note in documentation about thinking token sensitivity
- [ ] Ensure content filtering applies to thinking tokens if implemented

### Threat Model

**No new attack vectors:**
- Thinking tokens are output, not input
- No user-controlled content in event structure
- No injection risks (text treated as opaque)

**Existing mitigations apply:**
- Input validation on message content
- Output encoding for display
- Access controls on threads/messages

## 8. Observability & Operations

### Logs to Add

**Debug level (agent.py):**
```python
logger.debug(
    f"Thinking chunk detected: type={thinking_type}, "
    f"length={len(thinking_content)}"
)
```

**Warning level (agent.py):**
```python
logger.warning(
    f"Unexpected thinking data format: {type(thinking_data)}"
)
```

**Location:** `packages/tyler/tyler/models/agent.py` in `_go_stream()` method

### Metrics to Add (Optional)

**If metrics infrastructure exists:**
```python
# tyler.thinking_tokens.events_emitted (counter)
# Labels: thinking_type

# tyler.thinking_tokens.messages_with_reasoning (counter)  
# Labels: provider

# tyler.thinking_tokens.chunk_size (histogram)
```

**Priority:** Low - Nice to have, not critical

### Dashboards/Alerts

**No alerts needed:**
- Feature is additive/optional
- Absence of thinking is not a failure
- No SLA requirements

**Future dashboard (optional):**
- % of messages with thinking tokens
- Average thinking token count per message
- Thinking token usage by provider

### Runbooks & SLOs

**No new runbooks needed:**
- Feature doesn't introduce new failure modes
- Existing error handling covers edge cases

**No SLOs:**
- Thinking tokens are optional feature
- No availability/latency requirements

## 9. Rollout & Migration

### Feature Flags

**No feature flag needed:**
- Additive feature, opt-in by model choice
- Developers automatically get thinking when using reasoning models
- No behavior change for existing code

**Rationale:**
- Zero risk of breaking existing functionality
- Can be reverted via git if issues found
- Controlled rollout not necessary

### Data Backfill

**No data migration needed:**
- New fields are optional
- Existing messages work unchanged
- No backfill of historical data

### Revert Plan

**Easy revert:**
1. Git revert the PR
2. Redeploy
3. No data cleanup needed
4. No state to reconcile

**Blast radius:** Minimal
- Only affects new messages with reasoning models
- Existing functionality unchanged
- No cascading failures possible

### Rollout Strategy

**Phase 1: Deploy to dev/staging**
- Test with real API calls
- Verify thinking tokens appear
- Check for errors

**Phase 2: Deploy to production**
- Standard deployment (no special process)
- Monitor error rates for 24h
- Gather developer feedback

**Success criteria:**
- No increase in error rates
- Thinking tokens visible for Anthropic/o1 models
- No performance regression

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment

**We will follow strict TDD:**
1. Write failing test first for each acceptance criterion
2. Run test to confirm failure
3. Implement minimal code to pass
4. Refactor while keeping tests green
5. Commit order: `test:` → `feat:` → `refactor:`

### Spec→Test Mapping

| Spec AC | Test ID | Test Description | Priority |
|---------|---------|------------------|----------|
| AC1 | `test_thinking_chunks_emitted_anthropic` | Verify LLM_THINKING_CHUNK events emitted for Claude | P0 |
| AC1 | `test_thinking_chunks_emitted_openai_o1` | Verify LLM_THINKING_CHUNK events emitted for o1 | P0 |
| AC1 | `test_thinking_separated_from_content` | Verify thinking and content in separate events | P0 |
| AC2 | `test_reasoning_stored_in_message_metrics` | Verify reasoning_content in Message.metrics | P0 |
| AC2 | `test_thinking_blocks_stored_anthropic` | Verify thinking_blocks stored for Anthropic | P1 |
| AC2 | `test_reasoning_persisted_to_thread_store` | Verify persistence if thread_store present | P1 |
| AC3 | `test_backward_compatibility_existing_events` | Verify existing events unchanged | P0 |
| AC3 | `test_backward_compatibility_existing_tests` | Run all existing tests unmodified | P0 |
| AC3 | `test_new_event_ignored_by_old_code` | Verify old consumers ignore new event | P1 |
| AC4 | `test_raw_streaming_preserves_reasoning` | Verify raw mode passes reasoning through | P0 |
| AC4 | `test_raw_streaming_no_transformation` | Verify no modification of reasoning fields | P1 |
| AC5 | `test_non_reasoning_model_no_thinking_events` | Verify GPT-4 produces no thinking events | P0 |
| AC5 | `test_non_reasoning_model_unchanged_behavior` | Verify normal streaming works | P0 |
| AC6 | `test_tool_calls_with_thinking` | Verify tools + thinking work together | P0 |
| AC6 | `test_thinking_tool_sequence` | Verify correct event sequence | P1 |
| Negative | `test_malformed_reasoning_graceful_degradation` | Verify graceful handling of bad data | P1 |
| Negative | `test_missing_reasoning_field_no_error` | Verify absence handled gracefully | P1 |

### Test Tiers

**Unit Tests (packages/tyler/tests/models/)**

`test_agent_thinking_tokens.py` (NEW file):
```python
class TestThinkingTokensEventStreaming:
    """Test thinking token support in event streaming mode"""
    
    @pytest.mark.asyncio
    async def test_thinking_chunks_emitted_anthropic(self):
        """AC1: Thinking chunks emitted for Anthropic Claude"""
        # Mock LiteLLM response with reasoning_content
        # Stream with agent.go(stream=True)
        # Assert LLM_THINKING_CHUNK events present
        # Assert event data structure correct
    
    @pytest.mark.asyncio
    async def test_reasoning_stored_in_message_metrics(self):
        """AC2: Reasoning stored in Message.metrics"""
        # Stream complete response
        # Check final message has reasoning_content in metrics
        # Verify content preserved exactly
    
    @pytest.mark.asyncio  
    async def test_backward_compatibility_existing_events(self):
        """AC3: Existing events unchanged"""
        # Use existing test fixtures
        # Verify event types, data structure match expected
        # Assert no regressions
    
    @pytest.mark.asyncio
    async def test_raw_streaming_preserves_reasoning(self):
        """AC4: Raw mode passes reasoning through"""
        # Stream with agent.go(stream="raw")
        # Check chunks have reasoning_content
        # Verify no transformation
    
    @pytest.mark.asyncio
    async def test_non_reasoning_model_no_thinking_events(self):
        """AC5: Non-reasoning models unchanged"""
        # Use GPT-4 (non-reasoning)
        # Verify no LLM_THINKING_CHUNK events
        # Verify normal events work
    
    @pytest.mark.asyncio
    async def test_tool_calls_with_thinking(self):
        """AC6: Tools + thinking work together"""
        # Mock response with both tool_calls and reasoning
        # Verify both event types emitted
        # Check correct sequence
    
    @pytest.mark.asyncio
    async def test_malformed_reasoning_graceful_degradation(self):
        """Negative: Malformed reasoning handled gracefully"""
        # Mock malformed reasoning_content
        # Verify no exception raised
        # Verify streaming continues
        # Check warning logged
```

**Mocking Strategy:**
```python
# Mock LiteLLM chunks with reasoning
mock_chunks = [
    MockChunk(delta={"reasoning_content": "Thinking..."}),
    MockChunk(delta={"content": "Answer"}),
]

with patch('litellm.completion') as mock_completion:
    mock_completion.return_value = mock_chunks
    # Run test
```

**Contract Tests:**
- Verify LiteLLM interface expectations
- Test with multiple LiteLLM response formats
- Validate event schema compliance

**Integration Tests:**
- Full agent.go() flow with mocked LiteLLM
- Thread storage integration
- Tool execution with thinking

**E2E Tests (Manual/Optional):**
- Real Anthropic API call
- Real OpenAI o1 API call  
- Verify actual thinking tokens
- Document in test README

### Negative & Edge Cases

1. **Missing reasoning_content** - No event emitted, no error
2. **Malformed reasoning_content** - Logged warning, streaming continues
3. **Empty reasoning_content** - No event emitted
4. **Very long reasoning** - Stored fully, no truncation
5. **Multiple thinking chunks** - All emitted separately
6. **Thinking + tool calls** - Both processed correctly
7. **Thinking + error** - Error handling unchanged
8. **Old LiteLLM version** - Fallback to provider-specific fields

### Performance Tests

**Targets:**
- Latency increase < 1ms per chunk
- Memory increase < 10% for messages with thinking
- Throughput unchanged

**Harness:**
```python
@pytest.mark.benchmark
async def test_streaming_performance_with_thinking():
    # Benchmark 100 messages with thinking
    # Compare to baseline (without thinking)
    # Assert latency delta < 1ms
```

### CI Requirements

**All tests must:**
- Run in GitHub Actions CI
- Block merge if failing
- Complete in < 5 minutes
- Use mocked external dependencies

**CI Configuration:**
- Add new test file to pytest discovery
- No new CI dependencies needed
- Existing Python 3.11+ setup sufficient

## 11. Risks & Open Questions

### Known Risks & Mitigations

**Risk 1: LiteLLM version compatibility**
- **Risk:** Tyler might use LiteLLM < v1.63.0
- **Mitigation:** Check version, upgrade if needed, fallback to provider-specific fields
- **Action:** Check `packages/tyler/pyproject.toml` for LiteLLM version

**Risk 2: Streaming delta vs final message**
- **Risk:** `reasoning_content` might only be in final message, not delta
- **Mitigation:** Handle both cases - check delta first, fall back to final message
- **Action:** Write test to verify actual behavior

**Risk 3: Performance with long reasoning**
- **Risk:** Very verbose reasoning could impact memory/latency
- **Mitigation:** LiteLLM already buffers this, we're just reading it
- **Action:** Monitor message sizes after deployment

**Risk 4: Provider-specific quirks**
- **Risk:** Providers might have different reasoning formats
- **Mitigation:** LiteLLM standardizes, but we have fallback checks
- **Action:** Test with multiple providers (mocked and real)

### Open Questions

**Q1: What LiteLLM version is Tyler currently using?**
- **Status:** Need to check `pyproject.toml`
- **Proposed path:** Check in next step, upgrade to v1.63.0+ if needed
- **Blocker:** No - can implement with fallback, but preferred to have v1.63.0+

**Q2: Does `delta.reasoning_content` exist during streaming or only in final message?**
- **Status:** Unknown - need empirical testing
- **Proposed path:** 
  1. Write test with real LiteLLM call (manual)
  2. Check if delta contains reasoning_content
  3. Implement accordingly (either delta or final message or both)
- **Blocker:** No - code handles both cases

**Q3: Should thinking_blocks be parsed/validated?**
- **Status:** Unknown structure details
- **Proposed path:** Store as-is from LiteLLM, don't parse
- **Blocker:** No - store opaque, let consumers parse if needed

**Q4: Need approval on test strategy?**
- **Status:** TDD plan defined above
- **Proposed path:** Get reviewer approval on spec→test mapping
- **Blocker:** Yes - need approval before implementation

## 12. Milestones / Plan (Post‑Approval)

### Phase 1: Foundation (Day 1)
**Tasks:**
1. ✅ Check LiteLLM version in `pyproject.toml`
   - **DoD:** Version documented, upgrade PR if needed
2. ✅ Write failing test: `test_thinking_chunks_emitted_anthropic`
   - **DoD:** Test fails with clear message, code committed
3. ✅ Add `EventType.LLM_THINKING_CHUNK` to enum
   - **DoD:** Enum compiles, test now fails at assertion
4. ✅ Implement thinking detection in `_go_stream()`
   - **DoD:** Test passes, code linted, committed

### Phase 2: Core Features (Day 2)
**Tasks:**
5. ✅ Write failing test: `test_reasoning_stored_in_message_metrics`
   - **DoD:** Test fails, committed
6. ✅ Implement metrics storage
   - **DoD:** Test passes, committed
7. ✅ Write failing test: `test_raw_streaming_preserves_reasoning`
   - **DoD:** Test fails (or passes if no changes needed)
8. ✅ Verify raw mode (likely no changes needed)
   - **DoD:** Test passes, documented

### Phase 3: Compatibility (Day 2-3)
**Tasks:**
9. ✅ Write failing test: `test_backward_compatibility_existing_events`
   - **DoD:** Test passes (proves no breaking changes)
10. ✅ Run full existing test suite
    - **DoD:** All tests pass, no modifications needed
11. ✅ Write failing test: `test_non_reasoning_model_no_thinking_events`
    - **DoD:** Test fails, committed
12. ✅ Verify non-reasoning model path
    - **DoD:** Test passes, committed

### Phase 4: Edge Cases (Day 3)
**Tasks:**
13. ✅ Write failing test: `test_tool_calls_with_thinking`
    - **DoD:** Test fails, committed
14. ✅ Verify tool + thinking interaction
    - **DoD:** Test passes (likely already works)
15. ✅ Write failing test: `test_malformed_reasoning_graceful_degradation`
    - **DoD:** Test fails, committed
16. ✅ Add error handling
    - **DoD:** Test passes, error logged, committed

### Phase 5: Documentation (Day 3-4)
**Tasks:**
17. ✅ Update `docs/guides/streaming-responses.mdx`
    - **DoD:** Section added, examples work, reviewed
18. ✅ Update API reference docs
    - **DoD:** EventType documented, examples clear
19. ✅ Create example: `examples/007_thinking_tokens_streaming.py`
    - **DoD:** Example runs, outputs clear, documented
20. ✅ Update CHANGELOG
    - **DoD:** Feature listed under new version

### Phase 6: Review & Ship (Day 4-5)
**Tasks:**
21. ✅ Self-review: Check all acceptance criteria
    - **DoD:** All ACs mapped to passing tests
22. ✅ Performance check
    - **DoD:** No latency regression, benchmarks pass
23. ✅ Create PR with spec, impact, TDR
    - **DoD:** PR description complete, all docs included
24. ✅ Address review feedback
    - **DoD:** All comments resolved, approvals received
25. ✅ Merge and deploy
    - **DoD:** CI passes, merged to main, deployed

### Dependencies
- **Blocker:** TDR approval (this document) before starting Phase 1
- **Blocker:** Spec approval before TDR approval
- **Dependency:** LiteLLM version check before implementation
- **Owner:** AI Agent + Adam Draper

### Estimated Timeline
- **Total:** 4-5 days (assuming no blockers)
- **Critical path:** TDR approval → Implementation → Documentation
- **Buffer:** +1 day for review feedback

---

## Approval Gate

**DO NOT START CODING UNTIL THIS TDR IS REVIEWED AND APPROVED**

**Reviewers should verify:**
- [ ] Codebase map is accurate
- [ ] Design leverages LiteLLM appropriately
- [ ] Test strategy maps to all acceptance criteria
- [ ] Security/privacy considerations addressed
- [ ] Rollout plan is sound
- [ ] All open questions have proposed paths
- [ ] No significant risks unmitigated

**Approver:** _______________ Date: _______________

