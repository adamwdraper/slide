## [tyler-v6.4.0] - 2026-06-03

### 🚀 Features

- Add execution details and Weave Agents tracing
- Add Agent Skills support for progressive skill disclosure
- Add skills example with sample SKILL.md files
- Add AGENTS.md support for project-level instructions

### 🐛 Bug Fixes

- Preserve AgentResult positional order
- Address AgentResult review findings
- Preserve skills state during connect_mcp() prompt regeneration
- Address code review findings for AGENTS.md support
- Skip oversized AGENTS.md files before reading into memory

### 📚 Documentation

- Make streaming the primary agent example
- Align agent API docs with streaming-first usage
- Add Skills and AGENTS.md documentation
## [tyler-v6.3.0] - 2026-01-22

### 🚀 Features

- *(tracing)* Auto-wrap tools with weave.op() for consistent trace trees
- *(tracing)* Fix weave accumulator for all streaming modes
- *(tracing)* Add step boundary reset for last-step-only output

### 🐛 Bug Fixes

- *(tracing)* Skip weave.op wrapping for MCP tools
- *(examples)* Improve MCP example prompt to ensure tool usage

### 🧪 Testing

- *(tracing)* Add tests for weave.op auto-wrapping
- *(tracing)* Add regression tests for weave.op signature preservation

### ⚙️ Miscellaneous Tasks

- *(dependencies)* Update package versions in lock and project files
- Remove unused pytest import in tests
## [tyler-v6.1.0] - 2026-01-12

### 🚀 Features

- *(streaming)* Add vercel_objects mode for marimo integration

### 🧪 Testing

- *(streaming)* Add tests for vercel_objects mode
## [tyler-v6.0.0] - 2026-01-12

### 🚀 Features

- *(tyler)* Add Vercel AI SDK Data Stream Protocol streaming mode
- *(tyler)* Support step_stream(mode="vercel")

### 🐛 Bug Fixes

- *(streaming)* Add duration_ms tracking to TOOL_RESULT events
- *(examples)* Add dotenv loading to vercel streaming example
- *(streaming)* Restore Weave trace hierarchy
- *(examples)* Add Weave tracing init to vercel streaming example
- *(tyler)* Align invalid mode error message with stream()

### 🚜 Refactor

- *(tyler)* [**breaking**] Rename 'raw' streaming mode to 'openai'
- *(tyler)* Extract streaming modes into unified module
- *(vercel)* Stream via step_stream for single-mode semantics
- *(streaming)* Centralize step execution (LLM + tools)

### 🧪 Testing

- *(tyler)* Add tests for Vercel AI SDK streaming

### ⚙️ Miscellaneous Tasks

- Address PR review comments
- *(streaming)* Remove unused imports after core refactor
## [tyler-v5.6.0] - 2026-01-09

### 🚀 Features

- *(tyler)* Add structured output, retry config, and tool context injection
- *(structured-output)* Add agent-level response_type as default
- *(tyler)* Add retry_history for structured output debugging
- *(tyler)* Implement output-tool pattern for structured output
- Implement tool_choice=required for structured output like Pydantic AI
- *(tyler)* [**breaking**] Add timeout support and rich ToolContext dataclass
- *(mcp)* [**breaking**] Migrate to SDK ClientSessionGroup, remove custom wrappers
- *(mcp)* Add progress callback support for MCP tools
- Update MCP progress callback example with working local server
- *(agent)* Add agent-level tool_context for static dependencies
- *(agent)* Make step include tool execution
- *(agent)* Implement stream accumulator for Weave tracing output
- *(agent)* Enhance tool execution with duration tracking and metrics reporting

### 🐛 Bug Fixes

- *(tyler)* Add missing self.message attribute to StructuredOutputError
- *(tests)* Add context param to mock functions and skip new examples in CI
- *(ci)* Pass OPENAI_API_KEY secret to test steps
- *(tests)* Add async mock for litellm.acompletion in conftest
- *(tests)* Properly mock acompletion at import location
- *(tests)* Return valid JSON mock for structured output requests
- *(tyler)* Code review fixes for structured output
- *(tests)* Update global mock to handle output-tool pattern for structured output
- Address code review findings
- Address Copilot PR review findings
- Address additional Copilot PR review findings
- *(examples)* Standardize weave project name to 'slide'
- *(examples)* Use WANDB_PROJECT env var for weave initialization
- *(mcp)* Address PR review feedback
- *(mcp)* Prevent tool name collisions when multiple servers have same-named tools
- *(mcp)* Remove websocket transport (not supported by SDK's ClientSessionGroup)
- Handle optional context in tool runner and prevent progress_callback collision
- Prevent ctx parameter collision and ensure exit_stack cleanup
- Address code review feedback (5 issues)
- Extract progress_callback from tool_context dict
- Composite progress callbacks when both stream and custom exist
- Add __bool__ to ToolContext to prevent falsy evaluation
- Allow MCP tools with ctx/context/progress_callback params
- Address Copilot review comments
- *(agent)* Keep step-inclusive tool execution compatible with tests

### 🚜 Refactor

- *(tool_runner)* Extract shared context injection logic to _execute_implementation
- Centralize reserved MCP params and fix docs
- Remove custom calculator tool and update agent purpose
- *(agent)* Remove dead code and legacy streaming paths

### 📚 Documentation

- Add MCP progress callback example

### 🧪 Testing

- *(tyler)* Skip structured output example from integration tests
- Enable structured output example in integration tests

### ⚙️ Miscellaneous Tasks

- *(weave)* Reduce trace noise; add narrator to_dict
- *(examples)* Weave-op custom tools
- *(weave)* Simplify example tool ops
- Upgrade weave to 0.52.23
## [tyler-v5.5.0] - 2025-12-30

### 🚀 Features

- *(a2a)* Add real-time token streaming support

### 🐛 Bug Fixes

- *(a2a)* Send initial artifact with append=False before streaming chunks
- *(a2a)* Use append=True for final artifact to preserve content
- *(a2a)* Address code review feedback

### 🚜 Refactor

- *(a2a)* Simplify executor to always stream internally

### ⚙️ Miscellaneous Tasks

- Remove broken test-examples.yml workflow
- Remove empty leftover test files
## [tyler-v5.4.0] - 2025-12-30

### 🚀 Features

- *(a2a)* [**breaking**] Add full A2A Protocol v0.3.0 support

### 🐛 Bug Fixes

- *(a2a)* Align field names with A2A Protocol v0.3.0 spec
- *(a2a)* Fix test_close_handler test assertion
- *(a2a)* Correct SDK type conversions to match v0.3.0 spec
- *(a2a)* [**breaking**] Update server to use a2a-sdk v0.3.0 API
- *(a2a)* Update example to use new SDK API
- *(a2a)* Await async enqueue_event calls and use agent.run() API
- Address PR review comments
- *(tests)* Skip A2A examples in CI to prevent hangs
- *(security)* Avoid DNS resolution in webhook URL validation

### 🚜 Refactor

- *(a2a)* Integrate with SDK push notification infrastructure
- Remove custom URL validation, trust SDK/httpx
- Remove unused push notification types
- Rename A2AServer param from tyler_agent to agent

### 📚 Documentation

- *(a2a)* Update documentation for v0.3.0 SDK field names
## [tyler-v5.3.0] - 2025-12-04

### 🚀 Features

- *(tyler)* Migrate Agent from weave.Model to pydantic.BaseModel
## [tyler-v5.2.3] - 2025-12-04

### 🐛 Bug Fixes

- Replace module-level logger and UTC with inline calls for Weave compatibility
## [tyler-v5.2.2] - 2025-12-04

### 🐛 Bug Fixes

- Exclude helper objects from Weave serialization
- Preserve user-provided helper objects during initialization
- Call super().model_post_init() in Agent

### 🚜 Refactor

- Remove redundant helper initialization
## [tyler-v5.2.1] - 2025-11-04

### 🐛 Bug Fixes

- *(tyler)* Allow Weave logging in chat CLI when WANDB_PROJECT is set
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
