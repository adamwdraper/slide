# Impact Analysis — Thinking Tokens in Streaming

## Modules/packages likely touched

### Core Changes (High Impact)
- **`packages/tyler/tyler/models/execution.py`** (5-10 lines)
  - Add `EventType.LLM_THINKING_CHUNK` to enum
  - No changes to `ExecutionEvent` dataclass (already flexible with `data: Dict[str, Any]`)

- **`packages/tyler/tyler/models/agent.py`** (30-50 lines)
  - Update `_go_stream()` method to detect and emit thinking chunks
  - Update `_go_stream_raw()` to preserve thinking fields (likely no changes needed)
  - Store `reasoning_content` and `thinking_blocks` in Message metrics after streaming

- **`packages/narrator/narrator/models/message.py`** (Optional, 0-10 lines)
  - Message already has flexible `metrics` dict - no schema change required
  - May add type hints for `reasoning_content` and `thinking_blocks` in metrics
  - Backward compatible - these are optional fields

### Testing (Medium Impact)
- **`packages/tyler/tests/models/test_agent_streaming.py`** (100-150 lines new)
  - Test thinking tokens with Anthropic Claude
  - Test reasoning_content with OpenAI o1
  - Test backward compatibility
  - Test tool calls + thinking together
  - Test non-reasoning models (no thinking events)
  - Mock responses for different providers

### Documentation (Medium Impact)
- **`docs/guides/streaming-responses.mdx`** (50-100 lines)
  - Add section on thinking tokens
  - Add examples for event streaming mode
  - Add examples for raw streaming mode
  - Update event type reference table

- **`docs/api-reference/tyler-eventtype.mdx`** (10-20 lines)
  - Document `LLM_THINKING_CHUNK` event type
  - Add example usage

### Examples (Low Impact)
- **`examples/007_thinking_tokens_streaming.py`** (NEW, ~80 lines)
  - Demonstrate thinking tokens with Anthropic
  - Demonstrate thinking tokens with OpenAI o1
  - Show how to display thinking separately from content

## Contracts to update (APIs, events, schemas, migrations)

### Internal Event Contract (Non-Breaking)
**`EventType` enum extension:**
```python
class EventType(Enum):
    # ... existing events ...
    LLM_THINKING_CHUNK = "llm_thinking_chunk"  # NEW
```

**Event data structure for `LLM_THINKING_CHUNK`:**
```python
{
    "thinking_chunk": str,      # The reasoning/thinking content
    "thinking_type": str        # One of: "reasoning", "thinking", "extended_thinking"
}
```

**Impact:** ✅ Additive only - no breaking changes

### Message Metrics Schema (Non-Breaking)
**New optional fields in `Message.metrics`:**
```python
{
    "reasoning_content": str,              # Complete reasoning text (optional)
    "thinking_blocks": List[Dict],         # Structured thinking blocks (optional, Anthropic only)
    # ... existing fields unchanged ...
}
```

**Impact:** ✅ Backward compatible - optional fields, existing code unaffected

### No External API Changes
- No REST API changes
- No WebSocket protocol changes
- No database schema changes (metrics already stored as JSON)
- No message queue changes
- No A2A protocol changes

## Risks

### Security
**Risk Level:** 🟢 **LOW**

- **Injection/XSS:** Thinking tokens are treated as text content, same as message content
  - Mitigation: Same sanitization as existing content (if any)
  - No new attack vectors introduced
  
- **Data leakage:** Thinking tokens may contain sensitive reasoning
  - Mitigation: Thinking tokens subject to same access controls as messages
  - Already handled by existing thread/message permissions
  
- **PII exposure:** Model reasoning might reference user data
  - Mitigation: No different from regular content - existing PII handling applies
  - Document that thinking tokens should be treated with same sensitivity as content

**Action items:**
- [ ] Document in security guide that thinking tokens contain reasoning and should be treated as sensitive
- [ ] Ensure thinking tokens are included in any content filtering/moderation pipelines

### Performance/Availability
**Risk Level:** 🟢 **LOW**

- **Processing overhead:** One additional `hasattr()` check per streaming chunk
  - Impact: Negligible (~microseconds per chunk)
  - No network calls or heavy computation
  
- **Memory usage:** Storing reasoning_content in Message metrics
  - Impact: Minimal - reasoning is typically 100-500 tokens (similar to content)
  - LiteLLM already buffers this data, we're just preserving it
  
- **Streaming latency:** No impact - thinking chunks streamed as they arrive
  - No buffering or waiting required
  - Pass-through processing only

- **Database impact:** Additional JSON fields in message metrics
  - Impact: Minimal - messages already store variable-size metrics
  - No index changes needed
  - Storage increase: ~10-20% for messages with thinking tokens

**Mitigation:**
- Thinking tokens are optional - only present for reasoning-capable models
- Most existing traffic (non-reasoning models) unaffected
- No performance degradation for existing use cases

**Action items:**
- [ ] Monitor average message size after deployment
- [ ] Track percentage of messages with thinking tokens

### Data Integrity
**Risk Level:** 🟢 **LOW**

- **Missing thinking tokens:** If LiteLLM doesn't provide them
  - Impact: None - optional fields, absence is valid
  - Code already handles missing fields gracefully
  
- **Malformed thinking data:** If LiteLLM returns unexpected format
  - Impact: Low - handled with `hasattr()` checks and try/except
  - Graceful degradation - skip malformed thinking, continue streaming
  
- **Inconsistent thinking across providers:** Different field names or formats
  - Impact: Handled - code checks multiple field names
  - Event includes `thinking_type` to identify source
  
- **Lost thinking tokens:** If error during streaming
  - Impact: Acceptable - thinking is auxiliary data, not critical
  - Final message preserves `reasoning_content` from LiteLLM

**Mitigation:**
- Defensive programming with `hasattr()` checks
- Try/except around thinking extraction
- Log warnings for unexpected formats (debug level)
- Don't fail entire request if thinking parsing fails

**Action items:**
- [ ] Add error handling for malformed thinking data
- [ ] Log warnings (not errors) for unexpected thinking formats
- [ ] Test with mock data of various formats

### Backward Compatibility
**Risk Level:** 🟢 **NONE**

- **Existing streaming code:** Continues to work identically
  - New event type is simply ignored if not handled
  - No changes to existing event types
  
- **Existing messages:** No migration needed
  - New fields are optional
  - Reading old messages works unchanged
  
- **Existing tests:** Should pass without modification
  - New tests added alongside, not replacing
  
**Validation:**
- [ ] Run full test suite before/after changes
- [ ] Verify no changes to existing test behavior
- [ ] Test with real production-like workloads

### Dependencies
**Risk Level:** 🟡 **MEDIUM-LOW**

- **LiteLLM version dependency:** Requires v1.63.0+ for standardized reasoning_content
  - Current Tyler version: [need to check]
  - Action: Verify LiteLLM version, update if needed
  
- **Provider support:** Not all models support thinking tokens
  - Impact: Graceful degradation - no events for unsupported models
  - No breaking changes
  
**Action items:**
- [ ] Check current LiteLLM version in `packages/tyler/pyproject.toml`
- [ ] Update to v1.63.0+ if needed (separate PR or include in this one?)
- [ ] Document supported providers in README

## Observability needs

### Logs
**Debug level:**
- Log when thinking tokens detected in streaming chunk
  - `DEBUG: Thinking chunk detected (type={thinking_type}, length={len})`
- Log when reasoning_content stored in message
  - `DEBUG: Message stored with reasoning_content (length={len})`
- Log when thinking blocks detected (Anthropic)
  - `DEBUG: Thinking blocks detected (count={count})`

**Warning level:**
- Warn if thinking data format is unexpected
  - `WARN: Unexpected thinking data format: {format_details}`
- Warn if LiteLLM version < 1.63.0 and reasoning requested
  - `WARN: LiteLLM version {version} may not support standardized reasoning_content`

**No error logs needed:**
- Missing thinking tokens is not an error (optional feature)
- Should not log errors for unsupported models

**Implementation locations:**
- `packages/tyler/tyler/models/agent.py` - Add debug logs in `_go_stream()`
- Use existing logger: `from tyler.utils.logger import logger`

### Metrics
**Optional - for monitoring adoption:**
- `tyler.thinking_tokens.events_emitted` (counter)
  - Labels: `thinking_type` (reasoning|thinking|extended_thinking)
  - Tracks how often thinking events are emitted
  
- `tyler.thinking_tokens.messages_with_reasoning` (counter)
  - Labels: `provider` (anthropic|deepseek|openai|...)
  - Tracks messages that include reasoning_content
  
- `tyler.thinking_tokens.chunk_size` (histogram)
  - Tracks size of thinking chunks
  - Helps understand reasoning verbosity

**Priority:** 🟡 **OPTIONAL** - Nice to have for understanding usage, not critical for feature

**Implementation:**
- Can be added after initial release
- Use existing metrics infrastructure (if any)
- Document metrics in observability guide

### Alerts
**No alerts needed** - This is a feature addition, not a critical service

**Rationale:**
- Thinking tokens are optional/additive
- Absence of thinking tokens is not a failure
- No SLA or availability requirements
- Developers opt-in by using reasoning-capable models

**Future consideration:**
- If thinking tokens become critical for business logic, add alerts for:
  - Unexpected drop in thinking token presence
  - Spike in thinking parsing errors

### Dashboards
**No dashboard changes required initially**

**Optional future dashboard additions:**
- Panel showing % of messages with thinking tokens
- Panel showing thinking token usage by model/provider
- Panel showing average thinking chunk count per message

**Priority:** 🟡 **OPTIONAL** - Can be added based on demand

## Testing Strategy

### Unit Tests (Required)
- Test EventType enum has new value
- Test thinking chunk detection from various providers
- Test fallback behavior (reasoning_content → thinking → extended_thinking)
- Test graceful handling of missing thinking fields
- Test Message metrics storage
- Test backward compatibility (existing events unchanged)

### Integration Tests (Required)
- Test full streaming flow with thinking tokens
- Test tool calls + thinking tokens together
- Test multiple thinking chunks in single response
- Test thinking_blocks (Anthropic specific)
- Mock LiteLLM responses for deterministic testing

### Provider Tests (Optional - Manual)
- Test with real Anthropic Claude API
- Test with real OpenAI o1 API
- Test with real Deepseek API
- Verify thinking tokens appear as expected

### Regression Tests (Required)
- Run existing streaming tests
- Run existing message tests
- Run existing tool call tests
- Verify no behavioral changes

## Migration/Rollout Plan

### Phase 1: Development & Testing (This PR)
- Implement feature
- Add tests
- Update documentation
- Get PR approval

### Phase 2: Canary Deployment (If applicable)
- Deploy to staging/dev environment
- Monitor for errors
- Test with real API calls
- Verify no performance degradation

### Phase 3: Production Rollout
- **No feature flag needed** - feature is additive and opt-in
- Developers automatically get thinking tokens when using reasoning models
- No action required by existing users
- No database migrations needed

### Rollback Plan
- **Low risk** - can revert PR if issues found
- No data migrations to reverse
- No API contracts broken
- Existing functionality unaffected

## Open Questions

1. **LiteLLM version:** What version is Tyler currently using? Need to verify ≥ v1.63.0
   - Action: Check `packages/tyler/pyproject.toml`
   - If < v1.63.0: Include upgrade in this PR or separate?

2. **Streaming behavior:** Does `delta.reasoning_content` exist in streaming or only in final message?
   - Action: Write test to verify actual behavior
   - Fallback: Handle both delta and final message cases

3. **Metrics storage:** Should reasoning_content be stored separately or in metrics dict?
   - Current approach: Store in metrics dict (flexible, no schema change)
   - Alternative: Add dedicated fields to Message model (more structured)
   - Recommendation: Keep in metrics dict for now (simpler, backward compatible)

4. **Provider testing:** Should we test with real provider APIs or only mocks?
   - Recommendation: Mocks for CI, manual testing with real APIs before release
   - Real API tests are expensive and require credentials

5. **Documentation priority:** Should we update all docs in this PR or follow-up?
   - Recommendation: Core docs in this PR, comprehensive guide in follow-up
   - Must-have: streaming-responses.mdx section
   - Nice-to-have: Detailed thinking token guide (separate doc)

## Dependencies for This Work

### Code Dependencies
- LiteLLM ≥ v1.63.0 (for standardized reasoning_content)
- No other new dependencies

### Documentation Dependencies
- OpenAI o1 documentation (for examples)
- Anthropic extended thinking documentation (for examples)
- LiteLLM reasoning_content docs (reference)

### Review Dependencies
- Need approval from: [Product/Engineering lead]
- Need testing from: [QA team if applicable]
- Need security review: [Only if handling sensitive data differently]

## Success Metrics

**Technical success:**
- [ ] All tests pass (100% coverage for new code)
- [ ] No performance regression (< 1% latency increase)
- [ ] No increase in error rates
- [ ] Backward compatibility verified (existing tests unchanged)

**Feature success:**
- [ ] Thinking tokens captured for Anthropic Claude
- [ ] Thinking tokens captured for OpenAI o1
- [ ] Documentation complete and clear
- [ ] Example code works end-to-end

**Post-deployment success:**
- Monitor for 1 week after deployment
- Track any error increases related to thinking tokens
- Gather developer feedback on API clarity
- Measure adoption (% of messages with thinking tokens)

