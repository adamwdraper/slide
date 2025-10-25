# Spec (per PR)

**Feature name**: Agent.from_config()  
**One-line summary**: Enable programmatic Agent instantiation from YAML/JSON config files, allowing the same configuration to be used in both CLI and Python code.

---

## Problem

Currently, Tyler supports rich YAML configuration files for the `tyler-chat` CLI (via `tyler-chat-config.yaml`), but Python users must manually translate these configs into `Agent()` constructor parameters. This creates:

1. **Configuration drift** - Teams maintaining separate configs for CLI vs Python usage
2. **Duplication** - Same configuration logic exists in CLI code but isn't reusable
3. **Poor DX** - Python users can't leverage the full power of YAML configs (env var substitution, custom tool loading, standard search paths)
4. **Inconsistent behavior** - CLI and Python code may behave differently even with "matching" configs

Why now: The CLI config system is mature and working well. Users are increasingly asking to use the same configs programmatically in their Python scripts and applications.

## Goal

Python users can instantiate Tyler agents from the same YAML/JSON config files used by the CLI, with full feature parity including:
- Environment variable substitution
- Custom tool file loading
- MCP server configuration
- Standard config search paths
- Parameter overrides

## Success Criteria

- [ ] Python users can create agents using `Agent.from_config("config.yaml")` with identical behavior to CLI
- [ ] Existing `tyler-chat-config.yaml` files work without modification in Python code
- [ ] Teams can maintain a single config file for both CLI and programmatic usage
- [ ] Developer satisfaction: Python API feels natural and Pythonic

## User Story

**As a** Tyler developer building a production agent,  
**I want** to load my agent configuration from a YAML file,  
**so that** I can maintain consistent configuration across CLI testing, Python scripts, and deployed applications without duplicating config logic.

## Flow / States

### Happy Path
1. Developer creates/reuses a `tyler-chat-config.yaml` with agent settings
2. In Python code: `agent = Agent.from_config("tyler-chat-config.yaml")`
3. Agent is instantiated with all config values (name, model, tools, MCP servers, etc.)
4. Developer can optionally override specific values: `Agent.from_config("config.yaml", temperature=0.9)`
5. Agent works identically to CLI-loaded agent

### Edge Case: Auto-discovery
1. Developer has `tyler-chat-config.yaml` in current directory
2. In Python code: `agent = Agent.from_config()` (no path specified)
3. System searches standard locations (current dir, ~/.tyler/, /etc/tyler/)
4. Loads first config found
5. Clear error message if no config found in standard locations

## UX Links

**Example configs:**
- Current CLI config: `/packages/tyler/tyler-chat-config.yaml`
- Config with MCP: `/packages/tyler/tyler-chat-config-wandb.yaml`

**Related documentation:**
- CLI config docs will be updated to mention Python usage
- New section in "Your First Agent" guide showing config-based instantiation

## Requirements

### Must
- Support YAML config formats (.yaml and .yml extensions)
- Provide `Agent.from_config(config_path: Optional[str], **overrides)` class method
- Process all config features identically to CLI:
  - Environment variable substitution (`${ENV_VAR}` syntax)
  - Custom tool file loading (relative/absolute/home paths)
  - MCP server configuration (stored but not auto-connected)
- Support config auto-discovery when path is None (search standard locations)
- Allow parameter overrides via kwargs
- Export `load_config()` function for advanced use cases
- Provide clear, helpful error messages for missing/invalid configs

### Must not
- Auto-connect to MCP servers (keep initialization synchronous)
- Merge tool lists (config tools are replaced if overridden, like all other parameters)
- Break existing `Agent()` constructor behavior
- Require users to change existing config files
- Support JSON config files (YAML-only for simplicity)

### Should
- Validate config against Agent schema before instantiation
- Preserve relative path resolution (relative to config file, not cwd)
- Support the same search order as CLI for consistency

## Acceptance Criteria

### Happy Path
- **Given** a valid `tyler-chat-config.yaml` in the current directory  
  **When** I call `Agent.from_config()`  
  **Then** an Agent is created with all config values applied (name, model, tools, temperature, etc.)

- **Given** a config file at a specific path  
  **When** I call `Agent.from_config("/path/to/config.yaml")`  
  **Then** the Agent is created using that specific config file

- **Given** a config file with environment variable references like `${API_KEY}`  
  **When** I call `Agent.from_config("config.yaml")` with that env var set  
  **Then** the Agent receives the substituted env var value

- **Given** a config file with custom tool file paths  
  **When** I call `Agent.from_config("config.yaml")`  
  **Then** the custom tools are loaded and available to the agent

- **Given** a config file with MCP server definitions  
  **When** I call `Agent.from_config("config.yaml")`  
  **Then** the Agent has `mcp` configuration set but is not auto-connected (user must call `await agent.connect_mcp()`)

- **Given** a config file  
  **When** I call `Agent.from_config("config.yaml", temperature=0.9, model_name="gpt-4o")`  
  **Then** the Agent uses overridden values (temperature=0.9, model_name="gpt-4o") and config values for all other parameters

### Edge Cases
- **Given** no config file at the specified path  
  **When** I call `Agent.from_config("/nonexistent/config.yaml")`  
  **Then** a clear error message is raised indicating the file was not found

- **Given** no config files in standard locations  
  **When** I call `Agent.from_config()` (no path)  
  **Then** a clear error message lists the searched locations

- **Given** a config file with invalid YAML syntax  
  **When** I call `Agent.from_config("invalid.yaml")`  
  **Then** a clear error message indicates the syntax error

- **Given** a config file with a non-YAML extension (.json, .txt, etc)  
  **When** I call `Agent.from_config("config.json")`  
  **Then** a clear error message indicates only .yaml/.yml files are supported

- **Given** a config file with an environment variable that doesn't exist  
  **When** I call `Agent.from_config("config.yaml")`  
  **Then** the literal `${VAR_NAME}` string is preserved (matching CLI behavior)

### Negative Cases
- **Given** a config file with tool list `["web", "slack"]`  
  **When** I call `Agent.from_config("config.yaml", tools=["notion"])`  
  **Then** the Agent has ONLY `["notion"]` tools (config tools are replaced, not merged)

- **Given** a config with relative tool path `"./my_tools.py"`  
  **When** the config is in a different directory than cwd  
  **Then** the tool path is resolved relative to the config file location (not cwd)

## Non-Goals

- **Auto-connecting to MCP servers** during config load - users must still call `await agent.connect_mcp()` explicitly
- **Merging tool lists** between config and overrides - override parameters always replace
- **JSON config support** - YAML-only for simplicity and consistency
- **Config validation schema** - rely on Pydantic validation in Agent class
- **Config file hot-reloading** - load once at instantiation
- **Supporting config fragments/includes** - single file only for this PR
- **CLI-specific features** like Weave initialization - Python users handle their own setup

