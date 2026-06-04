# Technical Design Review (TDR) — Agent Instructions Refresh

**Author**: Codex
**Date**: 2026-06-03
**Links**: Spec (`/directive/specs/agent-instructions-refresh/spec.md`), Impact (`/directive/specs/agent-instructions-refresh/impact.md`)

---

## 1. Summary
Tyler will load AGENTS.md by default, keep SKILL.md explicit and progressively disclosed, and use one canonical instruction prompt for core execution and CLI threads. LiteLLM chat completions remain the only model transport for this change.

## 2. Decision Drivers & Non-Goals
- Drivers: predictable project instruction delivery, provider-compatible LiteLLM parameters, minimal interface churn.
- Non-Goals: OpenAI Responses API support, automatic skill discovery, A2A metadata updates.

## 3. Current State — Codebase Map
- `Agent` builds `_system_prompt`, calls LiteLLM through `CompletionHandler`, and uses `_system_prompt` in non-streaming, streaming, and structured output paths.
- `agents_md.py` discovers and loads AGENTS.md only when configured.
- `SkillManager` loads explicit skill directories and registers `activate_skill`.
- `ChatManager` currently regenerates system prompts and omits AGENTS.md/skill blocks.
- Tests exist for AGENTS.md, skills, model prompt generation, and CLI thread behavior.

## 4. Proposed Design
- Make `Agent.agents_md` default to auto-discovery while preserving explicit disable with `False` or `None`.
- Add `agents_md_base_dir` and have `Agent.from_config()` set it to the config directory when AGENTS.md discovery is enabled or omitted.
- Add `instruction_role` to `Agent` and `CompletionHandler`; use it when prepending the canonical instruction prompt to completion messages.
- Use `agent._system_prompt` directly in CLI create/switch flows.
- Return activated skill output with skill root path plus instructions so relative files are actionable.

## 5. Alternatives Considered
- Keep explicit opt-in: safer but fails the requested default and leaves project instructions easier to miss.
- Add Responses API support: broader but unnecessary for this pass and riskier across LiteLLM providers.
- Auto-discover skills: convenient but higher security and prompt-budget risk.

## 6. Data Model & Contract Changes
- No persistent data model changes.
- Public Agent fields added: `agents_md_base_dir`, `instruction_role`.
- Public behavior change: default AGENTS.md auto-discovery.
- Backward compatibility: callers can pass `agents_md=False` or `agents_md=None` to restore disabled behavior.

## 7. Security, Privacy, Compliance
- Auto-discovered files are local markdown only and retain existing size limits.
- Secrets must not be placed in AGENTS.md; documentation should keep emphasizing env-var based secret handling.
- No new auth or PII handling.

## 8. Observability & Operations
- Reuse existing logger warnings for skipped files.
- No new dashboards, alerts, or runbooks.

## 9. Rollout & Migration
- Release as a normal Tyler framework behavior change.
- Users who do not want AGENTS.md can set `agents_md: false` in config or `agents_md=False` in code.
- Revert plan: restore default to disabled and keep the new explicit fields harmless.

## 10. Test Strategy & Spec Coverage (TDD)
- TDD commitment: add failing tests for each behavior before implementation.
- Spec coverage:
  - Default discovery: `test_agent_default_auto_discovers_agents_md`.
  - Explicit disable: `test_agent_with_agents_md_none`, `test_agent_with_agents_md_false`.
  - Config base dir: `test_from_config_agents_md_true_uses_config_dir`.
  - Instruction role: `test_step_uses_configured_instruction_role`.
  - Streaming/structured prompt consistency: targeted tests on captured completion messages/system prompts.
  - Skill activation output: `test_activate_skill_returns_path_and_content`.
  - CLI prompt consistency: create/switch thread tests.
- CI: run the focused test command plus `cd packages/tyler && uv run pytest tests/`.

## 11. Risks & Open Questions
- Risk: default auto-discovery changes prompt content for existing callers. Mitigation: explicit disable remains available and documented.
- Risk: `developer` role may not work with every provider. Mitigation: default remains `system`.
- Open questions: none for this implementation.

## 12. Milestones / Plan
- Add directive docs.
- Add failing tests.
- Implement agents_md default/base-dir and instruction_role plumbing.
- Update CLI prompt handling and skill activation output.
- Update docs/config examples.
- Run focused and Tyler package tests.

---

**Approval Gate**: User explicitly requested implementation of this plan.
