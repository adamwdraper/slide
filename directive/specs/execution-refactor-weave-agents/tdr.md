# Technical Design Review (TDR) - Tyler execution refactor with Weave Agents tracing

**Author**: Codex
**Date**: 2026-06-02
**Links**: Spec (`/directive/specs/execution-refactor-weave-agents/spec.md`), Impact (`/directive/specs/execution-refactor-weave-agents/impact.md`)

---

## 1. Summary
This change stabilizes Tyler's execution contract by adding `AgentResult.execution`, moves agent tool execution from the module-global runner to an agent-owned `ToolRunner`, and adds an optional Weave Agents tracing adapter. Existing `@weave.op` spans remain in place.

## 2. Decision Drivers & Non-Goals
- Drivers: stable observability contract, per-agent tool isolation, no-op tracing when Weave Agents APIs are unavailable.
- Non-Goals: docs/examples cleanup, full dependency modernization, tuple-unpacking compatibility.

## 3. Current State - Codebase Map
- `Agent.run()` delegates to `_run_complete()` for non-streaming execution and `stream()` delegates to streaming mode classes.
- `execute_streaming_step()` already centralizes streaming LLM/tool behavior.
- `ToolManager` and `SkillManager` register against `tyler.utils.tool_runner.tool_runner`.
- `AgentResult` currently preserves only thread, new messages, content, and structured output fields.
- Existing tracing uses `@weave.op` on `Agent.run()`, `Agent.step()`, and `Agent.stream()`.

## 4. Proposed Design
- Add `ExecutionDetails` and `ToolCallSummary` dataclasses in `models/execution.py`.
- Build `ExecutionDetails` from collected `ExecutionEvent` objects at every `AgentResult` return point.
- Add `Agent._tool_runner: ToolRunner` and pass it into `ToolManager` and `SkillManager`.
- Update `_handle_tool_execution()` and `_get_tool_attributes()` to use the agent runner.
- Update delegation handlers so `agent.go()` is treated as returning `AgentResult`.
- Add `tyler.tracing.weave_agents.WeaveAgentsTracer` as a narrow adapter that checks API availability and initialization at runtime.
- Integrate the adapter around run/stream sessions, turns, LLM calls, and tool calls without removing existing `@weave.op` tracing.

## 5. Alternatives Considered
- Keep global runner and namespace tool names: rejected because same-name tools should work naturally per agent.
- Build execution summaries from messages only: rejected because event data already contains richer timings and errors.
- Import Weave Agents APIs directly: rejected because Tyler must remain no-op safe on older Weave runtimes.

## 6. Data Model & Contract Changes
- `AgentResult.execution.events`: ordered execution events.
- `AgentResult.execution.duration_ms`: total run duration.
- `AgentResult.execution.total_tokens`: summed LLM response `total_tokens`.
- `AgentResult.execution.tool_calls`: summaries with tool name, call id, arguments, result/error, duration, and success.
- Backward compatibility: existing `content`, `thread`, `new_messages`, and structured output fields remain unchanged.

## 7. Security, Privacy, Compliance
- No new secrets.
- Tracing payloads mirror existing agent messages/tool arguments already available to Tyler.
- Adapter catches tracing errors and does not alter execution.

## 8. Observability & Operations
- Returned execution details become caller-facing telemetry.
- Optional Weave Agents spans cover session, turn, LLM calls, and tool calls.
- Existing logs and `@weave.op` spans remain available.

## 9. Rollout & Migration
- No migration required.
- Users on older/uninitialized Weave get no-op behavior.
- Revert is limited to Tyler package code and the targeted Weave dependency constraint.

## 10. Test Strategy & Spec Coverage (TDD)
- TDD commitment: add focused tests first, confirm failure, implement, then run targeted Tyler tests.
- Spec coverage:
  - `AgentResult.execution` no-tool/tool/error/max-iteration tests.
  - Same-name custom tool isolation test.
  - Skill/delegation/MCP registration against owning runner tests.
  - Weave adapter no-op and mocked API tests.
  - Streaming mode shape regression tests.
- CI: targeted `packages/tyler` tests for this pass; narrator/space-monkey optional for integration fallout.

## 11. Risks & Open Questions
- Some legacy tests patch the module-global runner; affected tests need to patch the agent runner or preserve compatibility paths.
- Weave Agents APIs may evolve; adapter should use dynamic calls and tolerate missing methods.

## 12. Milestones / Plan
- Add directive files and tests.
- Add execution summary models.
- Introduce per-agent runner registration/execution.
- Add tracing adapter.
- Update dependency constraint and lock.
- Run targeted tests.

---

**Approval Gate**: Plan provided by user; implementation proceeds in this workspace.
