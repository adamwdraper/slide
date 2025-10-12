# Phase 6: Streaming Consolidation - Approach

## Analysis

**Methods to consolidate**:
- `_go_complete()`: 288 lines (non-streaming)
- `_go_stream()`: 397 lines (streaming)
- **Total**: 685 lines

**Duplication estimate**: ~60-70%

## Conservative Approach (RECOMMENDED)

Given HIGH RISK nature, take incremental approach:

### Step 1: Extract Helper Methods ✅ (Safest)
Extract duplicated logic into shared methods:
- `_handle_max_iterations()` - Already exists, use in both
- Replace inline Message() calls with MessageFactory
- Extract tool execution recording logic
- Extract error handling patterns

**Benefit**: 50-100 line reduction with low risk

### Step 2: Share Event Recording (Medium Risk)
Both methods record similar events - could share helper:
- record_llm_request()
- record_llm_response()  
- record_tool_events()

**Benefit**: 30-50 line reduction

### Step 3: Full Streaming Merger (HIGH RISK - Skip for now)
Complete merger would be complex and risky.

**Decision**: Do Steps 1-2, skip Step 3 for this phase.

## Implementation Plan

### Phase 6a: Use MessageFactory
- Replace Message() calls with message_factory methods
- Low risk, immediate benefit
- Est: 20-30 line reduction

### Phase 6b: Extract Event Helpers  
- Create event recording helpers
- Share between streaming and non-streaming
- Est: 30-50 line reduction

### Phase 6c: Extract Tool Processing
- Share tool execution logic
- Create helper for parallel tool execution
- Est: 40-60 line reduction

**Total Expected**: 90-140 line reduction  
**Risk**: LOW-MEDIUM (vs HIGH for full merger)

## Success Criteria

- ✅ All tests passing
- ✅ Streaming tests especially thorough
- ✅ Performance maintained
- ✅ 90-140 lines removed
- ✅ Duplication reduced to <40%

## Timeline

**Conservative**: 1-2 hours (vs 2-3 hours for risky approach)  
**Confidence**: HIGH  
**Safety**: MAXIMUM

