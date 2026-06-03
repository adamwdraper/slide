# Spec

**Feature name**: Tyler execution refactor with Weave Agents tracing
**One-line summary**: Tyler returns stable execution telemetry from agent runs, isolates tool execution per agent, and emits optional Weave Agents spans.

---

## Problem
Tyler's agent execution path mixes run-loop logic, tool execution, and tracing concerns in the `Agent` class. The public `AgentResult` contract does not currently expose the execution events and metrics needed by callers that want reliable observability. Tool execution also depends on a module-level runner, which allows same-name tools to leak between agents.

## Goal
`Agent.run()` and `Agent.go()` return an `AgentResult` with a stable `execution` object, each agent executes tools through its own `ToolRunner`, streaming and non-streaming share step/tool behavior where practical, and Tyler can emit Weave Agents session/turn/LLM/tool spans when the active Weave runtime supports them.

## Success Criteria
- [ ] `AgentResult.execution` includes events, duration, total token count, and structured tool call summaries.
- [ ] `Agent.run()` and `Agent.go()` return only `AgentResult`; tuple-unpacking compatibility is not added.
- [ ] Two agents can register different same-name tools without leakage.
- [ ] Skills, delegation tools, and MCP-loaded tools register against the owning agent runner.
- [ ] Weave Agents tracing is a no-op when Weave is absent, uninitialized, or lacks the new APIs.
- [ ] Existing streaming modes keep their external output shapes.

## User Story
As a Tyler application developer, I want each agent run to return structured execution telemetry and use isolated tools, so that I can monitor production behavior without cross-agent tool contamination.

## Flow / States
Happy path: a caller runs an agent, Tyler records request/response/tool/message events, persists the thread, and returns `AgentResult` with final content and execution telemetry.

Edge case: if a tool or LLM call errors, Tyler records error events and returns an `AgentResult` with an error message where existing behavior expects graceful handling.

## UX Links
- Designs: N/A
- Prototype: N/A
- Copy/Content: N/A

## Requirements
- Must keep `Agent.run()` and `Agent.go()` returning `AgentResult` only.
- Must preserve `result.content`, `result.thread`, and `result.new_messages`.
- Must add `result.execution.events`, `result.execution.duration_ms`, `result.execution.total_tokens`, and `result.execution.tool_calls`.
- Must use per-agent tool runners for agent execution.
- Must keep the module-level `tool_runner` available for direct utility use.
- Must keep stream modes `events`, `openai`, `vercel`, and `vercel_objects` externally compatible.
- Must preserve existing `@weave.op` spans while adding optional Weave Agents spans.
- Must not update docs and examples in this pass.

## Acceptance Criteria
- Given a no-tool agent run, when `await agent.run(thread)` completes, then `result.execution.events` contains LLM and completion events and `result.execution.total_tokens` reflects usage.
- Given a tool-using agent run, when the tool completes, then `result.execution.tool_calls` contains tool name, call id, arguments, duration, result/error, and success status.
- Given two agents with same-name custom tools, when each agent executes the tool, then each uses its own implementation.
- Given Weave Agents APIs are unavailable or inactive, when an agent runs, then behavior remains unchanged and no tracing exception escapes.
- Given Weave Agents APIs are mocked as active, when an agent runs with a tool call, then Tyler calls session, turn, LLM, and tool span APIs.

## Non-Goals
- Docs and examples cleanup.
- Repo-level example tests as acceptance.
- Full dependency modernization.
- Tuple-unpacking compatibility for `AgentResult`.
