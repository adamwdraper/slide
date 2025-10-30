# Impact Analysis — Agent `.run()` as Primary API

## Modules/packages likely touched

### Core Package
- **`packages/tyler/tyler/models/agent.py`**
  - Add `run()` method (copy of current `go()` implementation)
  - Convert existing `go()` to alias: `go = run`
  - Update docstrings to reference `.run()` as primary
  - Rename internal methods for consistency:
    - `_go_complete()` → `_run_complete()` (called by `run()`)
    - `_go_stream()` → `_stream_events()` (called by `stream()`)
    - `_go_stream_raw()` → `_stream_raw()` (called by `stream(mode='raw')`)
  - Update internal method calls to use new names
  - Lines affected: ~150-200 (method definitions, docstrings, internal calls)

### Documentation (all `.mdx` files)
- **`docs/quickstart.mdx`** - Update code examples from `.go()` to `.run()`
- **`docs/introduction.mdx`** - Update any agent examples
- **`docs/guides/your-first-agent.mdx`** - Update tutorial code
- **`docs/guides/streaming-responses.mdx`** - Update streaming examples (keep `.stream()`, change `.go()`)
- **`docs/guides/patterns.mdx`** - Update pattern examples
- **`docs/guides/a2a-integration.mdx`** - Update agent delegation examples
- **`docs/guides/agent-delegation.mdx`** - Update delegation patterns
- **`docs/guides/conversation-persistence.mdx`** - Update persistence examples
- **`docs/guides/testing-agents.mdx`** - Update test examples
- **`docs/api-reference/tyler-agent.mdx`** - Update API docs (primary emphasis on `.run()`)

### Example Files (all Python files in `/examples`)
- **`examples/getting-started/quickstart.py`** - Core tutorial example
- **`examples/getting-started/basic-persistence.py`** - Persistence example
- **`examples/getting-started/tool-groups.py`** - Tool usage example
- **`examples/integrations/streaming.py`** - Streaming integration
- **`examples/integrations/cross-package.py`** - Cross-package integration
- **`examples/integrations/storage-patterns.py`** - Storage patterns
- **`examples/use-cases/research-assistant/research_agent.py`** - Research assistant
- **`examples/use-cases/slack-bot/slack_bot.py`** - Slack bot example
- **`examples/*.py`** - All root-level examples (8 files)

### Tyler Package Examples
- **`packages/tyler/examples/*.py`** - All 14+ example files in Tyler package
  - `003_docs_quickstart.py`
  - `004_streaming.py`
  - `005_raw_streaming.py`
  - `006_thinking_tokens.py`
  - `101_tools_streaming.py`
  - `300_mcp_basic.py`
  - `301_mcp_advanced.py`
  - `302_execution_observability.py`
  - `402_a2a_basic_client.py`
  - `403_a2a_multi_agent.py`
  - All other examples

### CLI
- **`packages/tyler/tyler/cli/chat.py`** - Update internal usage from `.go()` to `.run()` (though it already uses `.stream()`)

### Tests
- **`packages/tyler/tests/models/test_agent_streaming.py`** - Update ALL tests to use `.run()`
- **`packages/tyler/tests/models/test_agent_observability.py`** - Update ALL tests to use `.run()`
- **`packages/tyler/tests/models/test_agent_thinking_tokens.py`** - Update ALL tests to use `.run()`
- **All other agent tests** - Update ALL tests to use `.run()`
- **Add ONE new test** - `test_go_alias_backwards_compatibility()` to verify `.go()` still works

### Other Packages (may use Tyler)
- **`packages/space-monkey/`** - Check if it uses `agent.go()` in examples or code
- **`packages/narrator/`** - Verify no direct agent usage

## Contracts to update (APIs, events, schemas, migrations)

### Public API Changes
**No breaking changes** - This is purely additive with backwards compatibility:

1. **New Method (Primary)**:
   ```python
   async def run(self, thread_or_id: Union[Thread, str]) -> AgentResult
   ```
   - Identical signature and behavior to current `.go()`
   - This becomes the documented, primary method

2. **Existing Method (Alias)**:
   ```python
   go = run  # Backwards compatibility alias (undocumented)
   ```
   - Keeps all existing code working
   - No deprecation warnings
   - Not documented publicly

### Documentation Contract
- **Primary method**: `.run()` - featured in all docs, examples, guides
- **Legacy alias**: `.go()` - exists but not documented
- **Unchanged**: `.stream()` - remains as-is for streaming use cases

### Type Signatures
No changes to type signatures - both `.run()` and `.go()` have identical signatures:
```python
async def run(self, thread_or_id: Union[Thread, str]) -> AgentResult
```

### Events/Observability
- **No changes** to `ExecutionEvent` or `AgentResult` structures
- **Weave tracing**: Both `run` and `go` will have `@weave.op()` decorator
- **Event types**: No new event types needed

## Risks

### Security
**Risk Level: None**

- No security implications
- No changes to authentication, authorization, or data access patterns
- Same execution flow, just different method name

### Performance/Availability
**Risk Level: None**

- No performance impact (alias has zero overhead)
- No changes to async execution model
- No additional I/O or computation
- Same code path, just different entry point

### Data integrity
**Risk Level: None**

- No database schema changes
- No data migration needed
- No changes to how threads, messages, or results are stored
- Thread persistence unchanged

### Backwards Compatibility
**Risk Level: Low (Mitigated)**

**Risk**: Users may have existing code using `.go()`

**Mitigation**:
- `.go()` remains as a fully functional alias
- No deprecation warnings
- No breaking changes
- All existing code continues to work identically
- Tests verify both methods work

**Impact**: Zero breaking changes for existing users

### Documentation Confusion
**Risk Level: Low (Mitigated)**

**Risk**: Users may find old code examples or blog posts using `.go()`

**Mitigation**:
- Both methods work identically (copy-paste old examples still work)
- Clear migration is natural (`.go()` → `.run()` is self-explanatory)
- Search engines will index new docs over time

**Impact**: Minimal - old examples still work, new examples are clearer

### AI Coding Assistant Assumptions
**Risk Level: Low (Positive)**

**Risk**: AI assistants may generate `.run()` before seeing updated docs

**Benefit**: This is actually the desired outcome - `.run()` is the intuitive choice
- Validates our decision to make this change
- Reduces friction for AI-assisted development

## Observability needs

### Logs
**No new logging needed**:
- Existing agent execution logs continue unchanged
- Both `.run()` and `.go()` trace the same execution path
- Method name visible in stack traces (helps identify usage patterns)

### Metrics
**Optional enhancements** (not required for this change):
- Could track usage of `.run()` vs `.go()` to measure adoption
- Could add telemetry to see which method users call
- Not critical - both methods execute identically

### Alerts
**No new alerts needed**:
- Same error conditions as before
- Same failure modes
- Same retry and timeout behaviors

### Weave Tracing
**Automatic tracing** (already handled):
- Both methods decorated with `@weave.op()`
- Weave will track both `agent.run` and `agent.go` operations
- No additional instrumentation needed

## Migration Path (for users)

While not required, users who want to modernize their code can easily migrate:

### Simple Find-Replace
```bash
# In codebase
find . -name "*.py" -exec sed -i 's/\.go(/\.run(/g' {} +
```

### Manual Migration
```python
# Before (still works)
result = await agent.go(thread)

# After (recommended)
result = await agent.run(thread)
```

**Effort**: <1 minute per file (if desired)
**Required**: No - both methods work identically

## Testing Impact

### Test Updates Needed
- **All existing tests**: Update to use `.run()` instead of `.go()`
- **Single new test**: Add `test_go_alias_backwards_compatibility()` to verify `.go()` still works
- **Integration tests**: Update to use `.run()` as primary
- **Example tests**: Verify all updated examples still pass

### Test Strategy
1. Update ALL existing tests to use `.run()` (find-replace `.go(` → `.run(`)
2. Add ONE new test to verify `.go()` alias works (backwards compatibility)
3. Verify all 382+ tests still pass
4. Update example smoke tests to use `.run()`

### Coverage
- No reduction in code coverage (same code paths)
- May increase coverage slightly (tests for both entry points)

## Rollout Considerations

### Version
- Include in **v5.0.0** (current release being prepared)
- Pairs well with `.go()` → `.stream()` split (both are API clarifications)

### Release Notes
```markdown
## New Primary API: `agent.run()`

Tyler now uses `agent.run()` as the primary method for executing agents, 
aligning with Python conventions and improving discoverability.

- **New**: `await agent.run(thread)` - recommended for all new code
- **Backwards Compatible**: `await agent.go(thread)` continues to work

No migration required - both methods are identical. We recommend using 
`.run()` in new code for consistency with Python async patterns.
```

### Documentation Rollout
1. **Phase 1**: Update all docs and examples (this PR)
2. **Phase 2**: Monitor for any community confusion (first 2 weeks)
3. **Phase 3**: Update any external blog posts or tutorials (ongoing)

## Dependencies

### Upstream Dependencies
**None** - This change is self-contained in Tyler

### Downstream Dependencies
**Packages that use Tyler**:
- `space-monkey` - Check if examples use `agent.go()`
- User code - Continues to work (backwards compatible)

### External Documentation
- Blog posts (if any exist) - Will naturally update over time
- Tutorial videos (if any exist) - Old content still works
- Community examples - Old code still works

## Success Metrics

### Adoption Metrics (Optional)
- Percentage of new code using `.run()` vs `.go()`
- Search term frequency ("tyler agent.run" vs "tyler agent.go")
- Community questions about agent execution methods

### Quality Metrics
- Zero regression bugs related to this change
- Zero breaking changes for existing users
- Positive community feedback on API clarity

## Summary

This is a **low-risk, high-value** change that:
- ✅ Improves developer experience significantly
- ✅ Aligns with Python ecosystem conventions
- ✅ Has zero breaking changes
- ✅ Requires minimal code changes (add alias, update docs)
- ✅ Reduces friction for new users and AI assistants

The primary effort is in updating documentation and examples, not in the code change itself (which is trivial). The backwards compatibility guarantee means existing users are unaffected, while new users benefit from a more intuitive API.

