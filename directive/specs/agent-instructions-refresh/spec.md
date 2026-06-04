# Spec (per PR)

**Feature name**: Agent Instructions Refresh
**One-line summary**: Keep Tyler agent project instructions current and reliably delivered to model completions.

---

## Problem
Tyler supports AGENTS.md and SKILL.md, but AGENTS.md currently requires explicit opt-in and the CLI can regenerate system messages without the configured project instructions or skill metadata. This makes project guidance easy to miss even when the agent itself is configured correctly.

## Goal
Tyler should auto-discover AGENTS.md by default, keep skills explicit and progressively disclosed, and send the generated instruction prompt consistently through LiteLLM chat-completion calls.

## Success Criteria
- [ ] Default `Agent()` discovers AGENTS.md from the current working directory upward.
- [ ] `agents_md=False` and `agents_md=None` explicitly disable AGENTS.md loading.
- [ ] Tyler chat CLI uses the same generated instruction prompt as core agent execution.
- [ ] Optional `instruction_role` controls whether the instruction message is sent as `system` or `developer`.
- [ ] Existing explicit AGENTS.md paths, skills, tools, streaming, and structured output continue to work.

## User Story
As a Tyler user, I want project-level and skill instructions to be passed to the underlying model consistently, so that agents follow the right workspace guidance without manual prompt wiring.

## Flow / States
An agent is created from Python or config. If AGENTS.md loading is not explicitly disabled, Tyler discovers applicable AGENTS.md files, builds one canonical instruction prompt, and uses that prompt for CLI threads and all model completions. If skills are configured, only skill metadata is included until the model calls `activate_skill`.

Edge case: if a user explicitly passes `agents_md=False` or `agents_md=None`, Tyler does not load any AGENTS.md content.

## UX Links
- Designs: n/a
- Prototype: n/a
- Copy/Content: docs/guides/skills.mdx and tyler config template

## Requirements
- Must auto-discover AGENTS.md by default.
- Must preserve explicit AGENTS.md path/list behavior.
- Must allow explicit disabling with `agents_md=False` or `agents_md=None`.
- Must keep `SKILL.md` as the canonical skill filename.
- Must keep skills explicit and progressively disclosed.
- Must keep LiteLLM chat completions as the default model transport.
- Must make CLI system messages use the same prompt as core execution.

## Acceptance Criteria
- Given an AGENTS.md in the current directory, when `Agent()` is constructed without `agents_md`, then `_system_prompt` includes the AGENTS.md content.
- Given `agents_md=False` or `agents_md=None`, when `Agent()` is constructed, then `_system_prompt` does not include `<project_instructions>`.
- Given a config file with `agents_md: true`, when `Agent.from_config()` is used from another working directory, then discovery starts from the config file directory.
- Given skills are configured, when `activate_skill` is called, then the tool result includes both the skill root path and the skill instructions.
- Given the CLI creates or switches a thread, then its stored system message equals `agent._system_prompt`.
- Given `instruction_role="developer"`, when Tyler builds completion params, then the first message role is `developer`.

## Non-Goals
- Add an OpenAI Responses API transport.
- Auto-discover skills.
- Update A2A server/adapter metadata.
