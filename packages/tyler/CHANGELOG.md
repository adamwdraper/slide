## [tyler-v5.2.0] - 2025-11-04

### 🚀 Features

- Replace python-magic with filetype for pure-Python MIME detection
## [tyler-v5.1.1] - 2025-10-31

### 🚀 Features

- *(chat-cli)* Disable ellipsis truncation during streaming

### 🐛 Bug Fixes

- *(chat-cli)* Remove duplicate output in streaming responses
## [tyler-v5.1.0] - 2025-10-30

### 🚀 Features

- Make agent.run() the primary API with .go() as backwards-compatible alias

### 🐛 Bug Fixes

- Address Copilot review comments
- Handle UnboundLocalError in CLI chat cleanup
- Preserve full thinking and response content after Live streaming
- Improve chat CLI error handling and add interactive config creation

### 🚜 Refactor

- Rename internal methods for consistency with .run() API
- Extract duplicate Panel creation logic into helper functions
## [tyler-v5.0.0] - 2025-10-29

### 🚀 Features

- [**breaking**] Split Agent.go() into .go() and .stream() methods
- Update all examples and CLI for .go()/.stream() API

### 🧪 Testing

- Update tests for .go()/.stream() API split
## [tyler-v4.2.0] - 2025-10-25

### 🚀 Features

- Implement tyler.config module for loading agent configs
- Add Agent.from_config() class method
- Export load_config from tyler package

### 🐛 Bug Fixes

- Improve test reliability for missing custom tool files
- Address code review feedback

### 🚜 Refactor

- Migrate CLI to use shared config loading

### 📚 Documentation

- Add Agent.from_config() examples and documentation
- Add prominent documentation links to README

### 🧪 Testing

- Add failing tests for config loading (AC-1 to AC-15)
- Add failing tests for Agent.from_config() (AC-16 to AC-25)
## [tyler-v4.1.0] - 2025-10-24

### 🚀 Features

- Add automatic retry logic and improved error handling for MCP connections
- Add debug logging for MCP tool calls

### 🐛 Bug Fixes

- Handle cleanup errors for failed MCP connections
- Properly detect MCP tools in CLI using tool_runner attributes
- Resolve MCP tool double-namespacing and event loop issues
- Handle CancelledError during stdio connection cleanup

### 🚜 Refactor

- Consolidate MCP examples from 4 to 2

### 📚 Documentation

- Update tyler-chat-config example with recommended fail_silent setting

### ⚙️ Miscellaneous Tasks

- Remove duplicate 301_mcp_connect_existing.py
## [tyler-v4.0.0] - 2025-10-23

### 🚀 Features

- *(mcp-config)* Add Agent MCP support with connect_mcp() (TDD Phase 1)
- *(mcp-config)* Add CLI auto-connect for MCP servers (Phase 2)
- *(mcp-config)* Add streamablehttp transport for Mintlify MCP servers

### 🐛 Bug Fixes

- Add cleanup() to streamablehttp example to prevent asyncio errors

### 🚜 Refactor

- Address copilot review feedback
- Update examples to use Slide MCP server
- Remove unnecessary cleanup() from simple examples

### 📚 Documentation

- *(mcp-config)* Add MCP examples to config templates (Phase 3)
- *(mcp-config)* Rewrite MCP examples with Agent.connect_mcp() (Phase 4)
- *(mcp-config)* Update all docs to show streamablehttp as primary transport

### 🧪 Testing

- *(mcp-config)* Add config_loader tests and implementation (TDD Phase 1)
- *(mcp-config)* Add integration tests and fix CLI tests (Phase 6-7)

### ⚙️ Miscellaneous Tasks

- Upgrade weave from v0.51.59 to v0.52.11
- Update minimum version constraints for litellm and openai
## [tyler-v3.1.2] - 2025-10-15

### 🐛 Bug Fixes

- Add minimum version constraints for narrator dependency
## [tyler-v3.1.0] - 2025-10-15

### 🚀 Features

- *(tyler-cli)* [**breaking**] Make Weave initialization conditional on WANDB_PROJECT env var
- *(tyler-cli)* Add environment variable substitution to config loader
- *(tyler)* Add api_key support to Agent and CompletionHandler

### 🐛 Bug Fixes

- Address code review feedback

### 📚 Documentation

- Remove breaking change warnings (no existing users)

### 🧪 Testing

- *(tyler)* Add comprehensive Agent property validation tests
## [tyler-v3.0.0] - 2025-10-15

### 🚀 Features

- Add LLM_THINKING_CHUNK event type
- Implement thinking tokens detection in streaming
- Add thinking tokens display to tyler chat CLI
- Add reasoning_effort and thinking parameters to Agent
- Add reasoning parameter mapping in CompletionHandler

### 🐛 Bug Fixes

- Address code review feedback
- Update examples to use unified reasoning parameter

### 💼 Other

- Add logging to track thinking token detection

### 🚜 Refactor

- Unify reasoning parameters in Agent
- Store reasoning_content as top-level Message field

### 🎨 Styling

- Change thinking panel color from yellow to gray

### 🧪 Testing

- Add failing tests for thinking tokens support
- Update tests to use new reasoning API

### ⚙️ Miscellaneous Tasks

- Upgrade litellm to >=1.63.0 for reasoning_content support
- Clean up and finalize thinking tokens implementation
## [tyler-v2.2.3] - 2025-10-14

### 🚀 Features

- Standardize Python 3.11+ requirement across all packages
- Implement unified monorepo release process
## [tyler-v2.1.0] - 2025-10-13

### 🚀 Features

- Add ToolCall value object for tool call normalization (Phase 2)
- Add MessageFactory for centralized message creation (Phase 3)
- Add ToolManager and registration strategies (Phase 4a)
- Extract CompletionHandler from Agent (Phase 5)
- Implement raw streaming mode for OpenAI compatibility
- Make raw streaming mode fully agentic with tool execution

### 🐛 Bug Fixes

- Handle dict format for LiteLLM chunk deltas in tests
- Remove weave.op decorator from _go_stream_raw
- Restore weave.op decorator and temporarily skip raw streaming example in CI
- Handle API errors properly in raw streaming mode
- Handle authentication errors gracefully in raw streaming example

### 🚜 Refactor

- Integrate ToolManager into Agent (Phase 4b)
- Use MessageFactory for max iterations messages (Phase 6a)
- Simplify _create_error_message using MessageFactory (Phase 6b)
- Address Copilot PR review feedback
- Address remaining Copilot feedback (round 2)

### 📚 Documentation

- Add comprehensive ARCHITECTURE.md (Phase 8)
- Add raw streaming mode documentation and examples

### 🧪 Testing

- Establish Phase 1 baseline for Tyler refactoring

### ⚙️ Miscellaneous Tasks

- Reorganize benchmark files into benchmarks/ folder
- Remove baseline files from root (moved to benchmarks/)
## [tyler-v2.0.5] - 2025-08-15

### 💼 Other

- Fix CLI system_prompt call on thread switch; robust streaming tool-call arg buffering; make step() error behavior configurable via step_errors_raise (defaults to backward-compatible message return)
- Add tests for step_errors_raise and multi-chunk streaming tool-call argument assembly
- Add streaming tests for dict args and dict-format multi-chunk concatenation
## [tyler-v1.3.0] - 2025-08-08

### 📚 Documentation

- Standardize installation to uv-first across repo
## [space-monkey-v0.2.0] - 2025-07-25
