# Spec (per PR)

**Feature name**: Conditional Weave Initialization in Tyler Chat CLI  
**One-line summary**: Make Weave initialization conditional on the `WANDB_PROJECT` environment variable to prevent unnecessary tracking overhead when not needed.

---

## Problem
Currently, the Tyler Chat CLI unconditionally initializes Weave (W&B tracing) for every chat session with the hardcoded project name "tyler-cli". This means:
- Weave tracking is always enabled, even when users don't want it
- Users cannot opt-out of Weave without modifying code
- Weave initialization happens even when W&B credentials aren't configured, potentially causing warnings or unnecessary overhead
- Users who want to track to a specific Weave project (not "tyler-cli") cannot easily customize this

This becomes important as users may want to:
- Run Tyler without any external tracking dependencies
- Track different projects with different Weave project names
- Avoid Weave overhead during local development or testing

## Goal
When this is done, users can control Weave initialization behavior through the `WANDB_PROJECT` environment variable. Weave will only initialize when a project name is explicitly provided by the user.

## Success Criteria
- [ ] Weave does not initialize by default when `WANDB_PROJECT` is not set
- [ ] Users can enable Weave by setting the `WANDB_PROJECT` environment variable
- [ ] Existing users who rely on Weave tracking are notified of the breaking change
- [ ] Documentation clearly explains how to enable Weave tracking

## User Story
As a Tyler CLI user, I want to control whether Weave tracking is enabled via an environment variable, so that I can run Tyler without external dependencies when I don't need observability features, or customize the Weave project name when I do.

## Flow / States

### Happy Path:
1. User sets `WANDB_PROJECT="my-project-name"` environment variable (or in `.env` file)
2. User starts tyler-chat CLI
3. Weave initializes with the specified project name
4. All agent interactions are tracked in Weave under "my-project-name"

### Edge Case (No Weave Config):
1. User has no `WANDB_PROJECT` environment variable set
2. User starts tyler-chat CLI  
3. Weave does NOT initialize
4. Agent works normally without Weave tracking
5. No Weave-related warnings or errors appear

## UX Links
- Designs: N/A (CLI configuration change)
- Prototype: N/A
- Copy/Content: Documentation update needed in tyler-chat CLI docs

## Requirements
- Must only initialize Weave when `WANDB_PROJECT` environment variable is set
- Must not break existing Tyler Chat CLI functionality when Weave is disabled
- Must not show Weave-related errors or warnings when Weave is disabled
- Must update documentation to explain the new behavior and migration path for existing users
- Must be consistent with Space Monkey package behavior (also uses `WANDB_PROJECT`)

## Acceptance Criteria
- Given `WANDB_PROJECT="my-project"` env var, when tyler-chat starts, then Weave initializes with project name "my-project"
- Given no `WANDB_PROJECT` env var, when tyler-chat starts, then Weave does NOT initialize
- Given an empty string for `WANDB_PROJECT`, when tyler-chat starts, then Weave does NOT initialize
- Given Weave is disabled, when user chats with the agent, then all functionality works normally without Weave tracking
- Given Weave is disabled, when agent uses `@weave.op()` decorated methods, then no errors occur

## Non-Goals
- Adding YAML configuration for Weave project (keep it simple with env vars only)
- Configuring other Weave settings (entity, API key, etc.) - users can use environment variables for those
- Adding UI/CLI commands to toggle Weave on/off during a session
- Migrating existing Weave traces to new project names
- Providing automatic migration of existing user configs (breaking change is acceptable)
- Checking for `WANDB_API_KEY` before initializing (Weave can handle missing API key gracefully)

