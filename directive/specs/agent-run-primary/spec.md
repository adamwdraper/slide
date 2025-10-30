# Spec (per PR)

**Feature name**: Agent `.run()` as Primary API  
**One-line summary**: Replace `.go()` with `.run()` as the primary agent execution method for better discoverability and alignment with Python conventions.

---

## Problem

Users (including AI coding assistants) instinctively try `agent.run()` instead of `agent.go()` when working with Tyler agents. The `.go()` method name is non-standard in the Python ecosystem, causing friction and requiring users to consult documentation. When AI coding agents are asked to use Tyler without being shown the docs, they default to `.run()`, indicating this is the more intuitive choice.

## Goal

Make `agent.run()` the primary, documented method for executing agents, with `.go()` maintained as an undocumented alias for backwards compatibility.

## Success Criteria
- [ ] New users successfully use `agent.run()` without consulting docs (follows Python intuition)
- [ ] All documentation, examples, and guides reference `.run()` exclusively
- [ ] Existing code using `.go()` continues to work without changes (zero breaking changes)
- [ ] AI coding assistants default to `.run()` when generating Tyler code

## User Story

As a Python developer building agents with Tyler, I want to use `agent.run(thread)` to execute my agent, so that the API feels familiar and consistent with standard Python async patterns (`asyncio.run()`, etc.) and I don't need to learn Tyler-specific conventions.

## Flow / States

**Happy Path:**
1. Developer creates an agent: `agent = Agent(...)`
2. Developer creates a thread with a message
3. Developer runs the agent: `result = await agent.run(thread)`
4. Agent executes and returns `AgentResult`

**Edge Case (Backwards Compatibility):**
1. Developer has existing code using `agent.go(thread)`
2. Code continues to work identically (`.go()` is an alias)
3. No migration required, no breaking changes

## UX Links

- Current docs example: `/docs/quickstart.mdx` (uses `.go()`)
- Example files: `/examples/**/*.py` (use `.go()`)
- To update: All docs and examples to use `.run()`

## Requirements

**Must:**
- Make `.run()` the primary documented method
- Keep `.go()` as an undocumented alias (backwards compatibility)
- Update all documentation to use `.run()` exclusively
- Update all example files to use `.run()` exclusively
- Update CLI chat to use `.run()` internally
- Both `.run()` and `.go()` must have identical functionality
- Both `.run()` and `.go()` must work with `.stream()` counterpart
- Rename internal methods for consistency:
  - `_go_complete()` → `_run_complete()`
  - `_go_stream()` → `_stream_events()`
  - `_go_stream_raw()` → `_stream_raw()`

**Must not:**
- Break existing code using `.go()`
- Add deprecation warnings (silent alias, not deprecated)
- Document `.go()` in public-facing materials
- Change any execution behavior or signatures

## Acceptance Criteria

**Positive Cases:**
- Given an agent and thread, when I call `await agent.run(thread)`, then I get an `AgentResult` (identical to current `.go()` behavior)
- Given an agent and thread, when I call `await agent.go(thread)`, then I get an `AgentResult` (backwards compatibility verified)
- Given the quickstart documentation, when a new user reads it, then they see only `agent.run()` examples
- Given all example files, when reviewed, then none reference `.go()` in user-facing code

**Negative Cases:**
- Given existing production code using `.go()`, when Tyler is updated, then the code continues to work without modification
- Given the public documentation, when searched, then `.go()` is not documented or promoted (only exists as alias)

## Non-Goals

**Explicitly out of scope:**
- Changing the `.stream()` method name (it's already standard)
- Adding deprecation warnings for `.go()` (keep it as a silent alias)
- Changing any execution logic, parameters, or return types
- Creating migration tooling (no migration needed - backwards compatible)
- Supporting both names equally in docs (`.run()` is promoted, `.go()` is legacy)
- Renaming internal `._go_complete()` and similar private methods (internal implementation detail)

