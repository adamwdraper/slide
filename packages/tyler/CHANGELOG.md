## [tyler-v3.0.0] - 2025-10-15

### 🚀 Features

- Add LLM_THINKING_CHUNK event type
- Implement thinking tokens detection in streaming
- Add thinking tokens display to tyler chat CLI
- Add reasoning_effort and thinking parameters to Agent
- Add reasoning parameter mapping in CompletionHandler

### 💥 BREAKING CHANGES

- **Tyler Chat CLI**: Weave initialization is now conditional on `WANDB_PROJECT` environment variable
  - **Before**: CLI automatically initialized Weave with project "tyler-cli" on every startup
  - **After**: CLI only initializes Weave when `WANDB_PROJECT` environment variable is set
  - **Migration**: Set `WANDB_PROJECT=tyler-cli` (or your preferred project name) to restore previous behavior
  - **Example**: Add to your `.env` file: `WANDB_PROJECT=tyler-cli`
  - **Benefit**: Reduced overhead and faster startup when tracking is not needed, plus users can customize project names

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
- Add comprehensive tests for conditional Weave initialization

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
