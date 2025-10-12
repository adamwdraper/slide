# Technical Design Review (TDR) — Tyler Code Organization & Maintainability Refactor

**Author**: AI Agent (adamdraper)  
**Date**: 2025-01-11  
**Links**: 
- Spec: `/directive/specs/tyler-code-organization/spec.md`
- Impact: `/directive/specs/tyler-code-organization/impact.md`
- Branch: `refactor/tyler-code-organization`

---

## 1. Summary

We are refactoring the Tyler package's internal architecture to improve maintainability, reduce technical debt, and make the codebase more modular and testable. The Agent class has grown to 1,598 lines with multiple responsibilities, streaming logic is duplicated, and tool registration has complex nested conditionals. This refactor will split these concerns into focused, single-responsibility classes while maintaining 100% backward compatibility.

The refactor will be done in phases, with comprehensive testing after each phase, ensuring no behavior changes or API breaks. This is purely an internal restructuring that will make future development faster and safer, with no impact on Tyler users.

## 2. Decision Drivers & Non‑Goals

### Decision Drivers
- **Maintainability**: Current 1,598-line Agent class is difficult to understand and modify
- **Safety**: Reduce risk of bugs by reducing code duplication and complexity
- **Testability**: Smaller, focused classes are easier to test in isolation
- **Extensibility**: Make it easier to add new tool types and protocol adapters
- **Developer Experience**: Reduce onboarding time for new contributors
- **Code Quality**: Improve metrics (cyclomatic complexity, test coverage)

### Non‑Goals
- **Not changing external behavior**: Zero breaking changes to user-facing APIs
- **Not adding features**: Purely internal refactoring
- **Not optimizing performance**: Maintain current performance (within 5%)
- **Not changing dependencies**: No new external dependencies
- **Not refactoring narrator/lye**: Scope limited to Tyler package
- **Not changing protocols**: MCP and A2A implementations unchanged functionally

## 3. Current State — Codebase Map

### Key Modules

```
tyler/
├── models/
│   ├── agent.py          # 1,598 lines - Main Agent class (TOO LARGE)
│   └── execution.py      # 52 lines - ExecutionEvent, AgentResult models
├── utils/
│   ├── tool_runner.py    # 348 lines - Tool execution and loading
│   ├── logging.py        # 58 lines - Logger configuration
│   └── files.py          # 90 lines - File utilities
├── mcp/
│   ├── adapter.py        # 227 lines - MCP to Tyler adapter
│   └── client.py         # 195 lines - MCP client
├── a2a/
│   ├── adapter.py        # 359 lines - A2A to Tyler adapter
│   ├── client.py         # 386 lines - A2A client
│   └── server.py         # 435 lines - A2A server
└── cli/
    ├── main.py
    ├── chat.py
    └── init.py
```

### Existing Data Models
- **Thread**: From narrator package, stores conversation history
- **Message**: From narrator package, individual messages with attachments
- **AgentResult**: Contains thread, new_messages, content, execution details
- **ExecutionEvent**: Streaming event with type, timestamp, data
- **Attachment**: File attachments with content and metadata

### External Contracts
- **Public Agent API**:
  ```python
  Agent(
      model_name="gpt-4.1",
      purpose="...",
      tools=[...],
      agents=[...],  # Delegation
      thread_store=...,
      file_store=...
  )
  await agent.go(thread, stream=False) -> AgentResult
  await agent.go(thread, stream=True) -> AsyncGenerator[ExecutionEvent]
  ```

- **Tool Registration Formats**:
  - String: `"web"` - Load built-in module
  - String with filters: `"web:download,search"` - Specific tools
  - Module: `lye.web` - Module object
  - Dict: `{"definition": {...}, "implementation": func}` - Custom tool
  - Callable: Direct function reference

### Hotspots & Pain Points
1. **Agent.__init__()**: Lines 181-372 - Complex tool registration logic
2. **Agent._go_complete()**: Lines 772-1057 - 285 lines of non-streaming logic
3. **Agent._go_stream()**: Lines 1060-1455 - 395 lines of streaming logic (70% overlap)
4. **Tool call normalization**: Multiple places handling dict vs object formats
5. **Message creation**: Scattered across Agent class

### Observability Currently Available
- **Weave Integration**: Agent inherits from `weave.Model`
- **Logging**: Via `tyler.utils.logging.get_logger()`
- **Execution Events**: Detailed event stream in `go()` method
- **Metrics**: Token usage, latency, tool execution time

## 4. Proposed Design (High Level)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent (Orchestrator)                  │
│  - Coordinates components                                    │
│  - go() method for execution                                 │
│  - Maintains backward-compatible API                         │
└───────┬─────────────┬─────────────┬──────────────┬──────────┘
        │             │             │              │
        ▼             ▼             ▼              ▼
┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐
│ ToolManager  │ │ MessageFactory│ │Completion│ │StreamingMgr  │
│              │ │              │ │Handler   │ │              │
│ - Register   │ │ - Create msgs│ │          │ │ - Stream     │
│ - Delegate   │ │ - Std source │ │ - LLM    │ │   chunks     │
│ - Load       │ │ - Format     │ │   calls  │ │ - Aggregate  │
└──────┬───────┘ └──────────────┘ └────┬─────┘ └──────────────┘
       │                                 │
       ▼                                 │
┌─────────────────────┐                 │
│  Tool Strategies    │                 │
│                     │                 │
│  - StringStrategy   │                 │
│  - ModuleStrategy   │                 │
│  - DictStrategy     │                 │
│  - CallableStrategy │                 │
└─────────────────────┘                 │
                                        ▼
                              ┌──────────────────┐
                              │   ToolRunner     │
                              │   (Refactored)   │
                              │                  │
                              │ - Registry       │
                              │ - Executor       │
                              │ - Loader         │
                              └──────────────────┘
```

### Component Responsibilities

#### 1. Agent (Orchestrator) - `models/agent.py`
**Responsibilities**:
- Coordinate execution flow
- Implement `go()` method (streaming and non-streaming)
- Manage iteration loops
- Handle max iterations
- Maintain public API

**Key Methods**:
```python
class Agent(Model):
    def __init__(self, ...):
        # Initialize components
        self.tool_manager = ToolManager(self.tools, tool_runner)
        self.message_factory = MessageFactory(self.name, self.model_name)
        self.completion_handler = CompletionHandler(...)
        self.streaming_handler = StreamingHandler(...)
    
    async def go(self, thread_or_id, stream=False):
        # Orchestrate execution
    
    async def step(self, thread, stream=False):
        # Delegate to CompletionHandler
```

**Size Target**: ~400 lines (75% reduction)

#### 2. ToolManager - `models/tool_manager.py` (NEW)
**Responsibilities**:
- Register tools from various sources
- Set up agent delegation
- Manage tool lifecycle

**Interface**:
```python
class ToolManager:
    def __init__(self, tools: List, tool_runner: ToolRunner):
        self.tool_runner = tool_runner
        self.registrar = ToolRegistrar()
    
    def register_all(self) -> List[Dict]:
        """Register all tools and return processed definitions"""
        return self.registrar.register_tools(self.tools, self.tool_runner)
    
    def setup_delegation(self, agents: List[Agent]) -> List[Dict]:
        """Create delegation tools for child agents"""
```

#### 3. MessageFactory - `models/message_factory.py` (NEW)
**Responsibilities**:
- Create standardized messages
- Generate source metadata
- Handle attachments

**Interface**:
```python
class MessageFactory:
    def __init__(self, agent_name: str, model_name: str):
        self.agent_name = agent_name
        self.model_name = model_name
    
    def create_assistant_message(self, content: str, tool_calls=None, metrics=None) -> Message:
        """Create assistant message with standard source"""
    
    def create_tool_message(self, tool_name: str, content: str, tool_call_id: str, 
                           attachments=None, metrics=None) -> Message:
        """Create tool message with standard source"""
    
    def create_error_message(self, error_msg: str, source=None) -> Message:
        """Create error message"""
    
    def _create_agent_source(self) -> Dict:
        """Standard source for agent messages"""
    
    def _create_tool_source(self, tool_name: str) -> Dict:
        """Standard source for tool messages"""
```

#### 4. CompletionHandler - `models/completion.py` (NEW)
**Responsibilities**:
- Prepare messages for LLM
- Call LLM API
- Handle streaming/non-streaming

**Interface**:
```python
class CompletionHandler:
    def __init__(self, model_name: str, temperature: float, ...):
        self.model_name = model_name
        self.temperature = temperature
    
    async def get_completion(self, system_prompt: str, thread_messages: List[Dict],
                            tools: List[Dict], stream: bool = False):
        """Get completion from LLM"""
        params = self._build_params(system_prompt, thread_messages, tools, stream)
        return await acompletion(**params)
    
    def _build_params(self, ...) -> Dict:
        """Build completion parameters"""
```

#### 5. StreamingHandler - `models/streaming.py` (NEW)
**Responsibilities**:
- Process streaming chunks
- Aggregate content and tool calls
- Yield execution events

**Interface**:
```python
class StreamingHandler:
    async def process_stream(self, response, thread, message_factory) -> AsyncGenerator:
        """Process streaming response and yield events"""
        async for chunk in response:
            # Process chunk
            yield ExecutionEvent(...)
```

#### 6. ToolCall - `models/tool_call.py` (NEW)
**Responsibilities**:
- Normalize tool call formats
- Provide consistent interface

**Interface**:
```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]
    
    @classmethod
    def from_llm_response(cls, tool_call) -> 'ToolCall':
        """Normalize dict or object format"""
    
    def to_message_format(self) -> Dict:
        """Convert to Message tool_calls format"""
    
    def to_execution_format(self):
        """Convert to tool_runner format"""
```

#### 7. Tool Registration Strategies - `utils/tools/strategies.py` (NEW)
**Responsibilities**:
- Handle each tool type registration

**Interface**:
```python
class ToolRegistrationStrategy(ABC):
    @abstractmethod
    def can_handle(self, tool: Any) -> bool:
        """Check if this strategy handles this tool type"""
    
    @abstractmethod
    def register(self, tool: Any, tool_runner: ToolRunner) -> List[Dict]:
        """Register tool(s) and return definitions"""

class StringToolStrategy(ToolRegistrationStrategy):
    """Handle 'web' or 'web:download,search' format"""

class ModuleToolStrategy(ToolRegistrationStrategy):
    """Handle module objects like lye.web"""

class DictToolStrategy(ToolRegistrationStrategy):
    """Handle {'definition': ..., 'implementation': ...}"""

class CallableToolStrategy(ToolRegistrationStrategy):
    """Handle direct function references"""
```

### Shared Logic Extraction

Current duplication in `_go_complete()` and `_go_stream()`:
- Event recording logic
- Tool execution logic
- Message processing logic
- Error handling logic

**Solution**: Extract to shared methods:
```python
class Agent:
    async def _execute_tools_parallel(self, tool_calls, thread, message_factory, 
                                     event_recorder) -> List[Tuple[Message, bool]]:
        """Execute tools in parallel and return messages with break flags"""
        # Shared by both streaming and non-streaming
    
    def _record_tool_events(self, tool_calls, event_recorder):
        """Record TOOL_SELECTED events"""
        # Shared event recording
    
    async def _handle_iteration(self, thread, message_factory, stream, event_recorder):
        """Handle one iteration of the execution loop"""
        # Core iteration logic shared between modes
```

### Error Handling, Idempotency, Retries

**Error Handling**:
- Maintain existing error handling behavior
- Errors bubble up through component boundaries
- Each component has clear error contracts
- Tool execution errors captured in tool messages (existing behavior)

**Idempotency**:
- Thread operations idempotent (managed by narrator)
- Tool registrations idempotent (cache prevents double-registration)
- Component initialization idempotent

**Retries**:
- LLM retries handled by litellm (existing)
- No change to retry logic

### Performance Expectations

**Targets**:
- Agent initialization: <5ms overhead
- Message creation: <1ms per message
- Tool registration: <10ms total
- Overall execution: Within 5% of current performance

**Back-pressure**:
- Streaming: Same behavior (async generator naturally handles back-pressure)
- Tool execution: Parallel execution maintained (asyncio.gather)

## 5. Alternatives Considered

### Option A: Big Bang Refactor
**Approach**: Refactor everything at once in one large PR

**Pros**:
- Single review cycle
- All changes visible together
- Faster to complete

**Cons**:
- High risk of bugs
- Difficult to review
- Hard to isolate issues
- All-or-nothing merge

**Decision**: ❌ Rejected - Too risky

### Option B: Phased Refactor (CHOSEN)
**Approach**: Split into multiple phases, each independently tested and merged

**Pros**:
- Lower risk per phase
- Easier to review
- Can rollback individual phases
- Tests pass at each step
- Progressive improvement

**Cons**:
- More PRs to manage
- Longer total timeline
- Temporary mixed architecture

**Decision**: ✅ Chosen - Safest approach

### Option C: Create New Package
**Approach**: Build tyler-v2 alongside existing tyler

**Pros**:
- Zero risk to existing code
- Can take time to get right
- Users can migrate gradually

**Cons**:
- Maintenance burden of two packages
- User confusion
- Migration complexity
- Doesn't solve the root problem

**Decision**: ❌ Rejected - Unnecessary complexity

### Option D: Incremental with Feature Flags
**Approach**: Add new code paths with feature flags, gradually migrate

**Pros**:
- Can test in production
- Easy rollback
- Gradual migration

**Cons**:
- Complexity of dual code paths
- Feature flag management
- Eventually need to remove old code
- Not needed for internal refactor

**Decision**: ❌ Rejected - Overkill for internal refactor

## 6. Data Model & Contract Changes

### No Database Changes
- Thread schema unchanged (managed by narrator)
- Message format unchanged
- No migrations needed

### API Contract Changes
**Public API**: ✅ NO CHANGES
- `Agent.__init__()` signature unchanged
- `Agent.go()` signature unchanged
- `Agent.step()` signature unchanged
- All return types unchanged
- Tool registration formats all supported

**Internal Interfaces**: ✅ NEW (but not breaking)
```python
# NEW: Internal component interfaces
from tyler.models.message_factory import MessageFactory  # Internal use only
from tyler.models.tool_manager import ToolManager  # Internal use only
from tyler.models.tool_call import ToolCall  # Internal use only

# EXISTING: Public API unchanged
from tyler import Agent, AgentResult, ExecutionEvent, EventType  # Still works
```

### Backward Compatibility
All existing code continues to work:
```python
# Existing user code - NO CHANGES NEEDED
from tyler import Agent, Thread, Message

agent = Agent(
    model_name="gpt-4.1",
    purpose="Helper",
    tools=["web", lye.files, custom_tool_dict]
)

result = await agent.go(thread)  # Works identically
```

### Deprecation Plan
**None needed** - This is internal refactoring only

## 7. Security, Privacy, Compliance

### AuthN/AuthZ
- ✅ No changes to authentication or authorization
- Tool execution permissions unchanged
- Agent delegation security unchanged

### Secrets Management
- ✅ No changes to API key handling
- Environment variable usage unchanged
- LiteLLM integration unchanged

### PII Handling
- ✅ No changes to data handling
- Message content handling unchanged
- Thread storage unchanged

### Threat Model
- ✅ No new attack surfaces introduced
- Tool execution sandbox unchanged (if any)
- No new external communication

## 8. Observability & Operations

### Logs to Add
```python
# In new components, add debug-level logs
logger.debug(f"MessageFactory: Creating assistant message")
logger.debug(f"ToolManager: Registered {len(tools)} tools")
logger.debug(f"ToolCall: Normalized {tool_call.name}")
logger.debug(f"CompletionHandler: Building params for {model_name}")
```

### Metrics to Add
**Performance Benchmarks** (for comparison):
- `agent_init_time_ms` - Agent initialization
- `tool_registration_time_ms` - Tool registration
- `message_creation_time_μs` - Per message creation
- `tool_call_normalization_time_μs` - ToolCall creation

**Comparison Metrics**:
- Before/after execution time for standard workflows
- Memory usage before/after
- Test suite execution time

### Dashboards
- ✅ No new dashboards needed (internal refactor)
- Maintain existing Weave dashboard

### Alerts
**CI Alerts**:
- Test failures
- Coverage drops
- Performance regression >5%
- Linting failures

### Runbooks
**If Performance Regression Detected**:
1. Compare benchmarks before/after
2. Profile with cProfile
3. Identify bottleneck component
4. Optimize or revert change

**If Tests Fail After Refactor**:
1. Check if test needs updating (internal mocks)
2. If behavior changed, revert refactor
3. Add missing test coverage
4. Re-attempt refactor

## 9. Rollout & Migration

### Feature Flags
- ✅ Not needed - Internal refactor
- Tests ensure behavior unchanged

### Data Migration
- ✅ Not needed - No data model changes

### Rollout Phases

**Phase 1: Foundation & Safety** (Week 1)
1. Set up performance benchmarks
2. Run full test suite, document baseline
3. Add any missing tests discovered during review
4. Create architecture diagrams

**Phase 2: Message Factory** (Week 1-2)
1. Extract `MessageFactory` class
2. Update Agent to use MessageFactory
3. Run tests - must pass 100%
4. Run benchmarks - must be within 5%
5. Code review
6. Merge to main

**Phase 3: ToolCall Normalization** (Week 2)
1. Create `ToolCall` value object
2. Update all tool call handling
3. Run tests - must pass 100%
4. Merge to main

**Phase 4: Tool Manager** (Week 2-3)
1. Extract `ToolManager` and strategies
2. Update Agent to use ToolManager
3. Run tests - must pass 100%
4. Run benchmarks
5. Merge to main

**Phase 5: Completion Handler** (Week 3)
1. Extract `CompletionHandler`
2. Update Agent.step() to use it
3. Run tests
4. Merge to main

**Phase 6: Streaming Consolidation** (Week 3-4)
1. Extract `StreamingHandler`
2. Consolidate _go_complete and _go_stream logic
3. EXTENSIVE testing (highest risk)
4. Run benchmarks
5. Code review
6. Merge to main

**Phase 7: ToolRunner Restructure** (Week 4)
1. Split ToolRunner into focused modules
2. Update imports
3. Run tests
4. Merge to main

**Phase 8: Documentation & Cleanup** (Week 4-5)
1. Update architecture documentation
2. Create migration guide for contributors
3. Update docstrings
4. Final review

### Revert Plan
- Each phase is independently revertible
- Git provides easy rollback
- If major issue discovered:
  1. Revert specific commit(s)
  2. Or revert entire merge
  3. Analyze issue
  4. Fix and re-attempt

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment

**Process**:
1. ✅ **Before refactoring**: Ensure all existing tests pass
2. ✅ **During refactoring**: Run tests after EVERY commit
3. ✅ **Test-driven**: If adding functionality, write test first
4. ✅ **Coverage**: Maintain ≥80% coverage
5. ✅ **No skips**: All tests must pass, no skipping

### Test Categories

#### Unit Tests (Primary Focus)
**New Unit Tests** (to add):
```python
# tests/models/test_message_factory.py
def test_create_assistant_message()
def test_create_tool_message()
def test_create_error_message()
def test_message_source_formatting()

# tests/models/test_tool_manager.py
def test_register_string_tool()
def test_register_module_tool()
def test_register_dict_tool()
def test_register_callable_tool()
def test_setup_delegation()

# tests/models/test_tool_call.py
def test_normalize_dict_format()
def test_normalize_object_format()
def test_to_message_format()
def test_empty_arguments_handling()

# tests/models/test_completion.py
def test_build_params_basic()
def test_build_params_with_tools()
def test_build_params_streaming()
def test_api_base_override()

# tests/utils/tools/test_strategies.py
def test_string_strategy()
def test_module_strategy()
def test_dict_strategy()
def test_callable_strategy()
def test_strategy_selection()
```

**Existing Unit Tests** (must pass unchanged):
- `tests/models/test_agent.py` - Agent core functionality
- `tests/models/test_agent_tools.py` - Tool execution
- `tests/models/test_agent_delegation.py` - Agent delegation
- `tests/utils/test_tool_runner.py` - Tool runner

#### Integration Tests
**Existing** (must pass unchanged):
- `tests/integration/test_agent_delegation_integration.py`
- `tests/integration/test_direct_imports_integration.py`
- `tests/models/test_agent_observability.py`
- `tests/models/test_agent_streaming.py`

**New** (to add if gaps found):
- End-to-end workflow with real tools
- Multi-iteration tool calling
- Streaming with tool calls
- Error recovery scenarios

#### Contract Tests
- Test that Agent.__init__ accepts all documented parameters
- Test that Agent.go() returns AgentResult with expected fields
- Test that streaming yields ExecutionEvent objects
- Test tool registration with all supported formats

### Spec→Test Mapping

| Spec Acceptance Criterion | Test ID(s) |
|---------------------------|------------|
| All tests pass after each refactor step | `CI pipeline` + manual verification |
| Coverage remains ≥80% | `pytest-cov` report |
| Agent class <500 lines | Line count check |
| Tool type handlers in strategy classes | `test_strategies.py` |
| Message creation in MessageFactory | `test_message_factory.py` |
| Streaming duplication reduced >50% | Code analysis |
| No changes to public APIs | `test_agent.py` (unchanged tests) |
| No behavior changes | All existing tests pass |
| Performance within 5% | Benchmark suite |

### Negative & Edge Cases

```python
# Edge cases to explicitly test
def test_malformed_tool_call_dict():
    """Tool call missing 'id' field"""

def test_empty_tool_arguments():
    """Tool call with empty or null arguments"""

def test_invalid_json_in_arguments():
    """Tool call with malformed JSON arguments"""

def test_concurrent_tool_execution():
    """Multiple tools executing in parallel"""

def test_streaming_connection_lost():
    """Streaming interrupted mid-response"""

def test_tool_raises_exception():
    """Tool execution fails with exception"""

def test_max_iterations_reached():
    """Agent hits iteration limit"""

def test_empty_llm_response():
    """LLM returns empty response"""

def test_tool_returns_large_content():
    """Tool returns very large string"""
```

### Performance Tests

```python
# benchmarks/test_performance.py
@pytest.mark.benchmark
def test_agent_initialization_time():
    """Measure Agent.__init__ performance"""
    # Target: <50ms

@pytest.mark.benchmark
def test_message_factory_performance():
    """Create 1000 messages and measure time"""
    # Target: <1ms per message

@pytest.mark.benchmark  
def test_tool_registration_time():
    """Register 50 tools and measure time"""
    # Target: <100ms total

@pytest.mark.benchmark
def test_end_to_end_execution():
    """Full agent.go() execution with tools"""
    # Target: Within 5% of baseline
```

### CI Requirements
- ✅ All tests run on every commit
- ✅ Coverage report generated
- ✅ Performance benchmarks run
- ✅ Linting (ruff, mypy)
- ✅ Block merge if any test fails
- ✅ Block merge if coverage drops

## 11. Risks & Open Questions

### Known Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Behavior change during refactor | HIGH | Comprehensive tests, phased approach | Mitigated |
| Performance regression | MEDIUM | Benchmarks, profiling | Monitored |
| Missed edge cases | MEDIUM | Review existing tests, add coverage | In progress |
| Tool call format variations | MEDIUM | ToolCall normalization, comprehensive tests | Planned |
| Streaming logic bugs | HIGH | Extensive streaming tests, careful review | Phased approach |
| Import path changes | LOW | Backward-compatible exports | Planned |

### Open Questions

**Q1**: Should we maintain 100% line-for-line coverage in refactored code?
- **Proposed**: Aim for ≥80% but focus on critical paths
- **Decision needed**: Week 1

**Q2**: Should MessageFactory be used by narrator package too?
- **Proposed**: No - narrator is separate concern, don't create coupling
- **Decision**: Keep Tyler-specific

**Q3**: Should we add type checking (mypy) as part of this refactor?
- **Proposed**: Yes - add types to new code, gradually to refactored code
- **Decision needed**: Week 1

**Q4**: How to handle internal imports during transition?
- **Proposed**: Use absolute imports, maintain backward compatibility in __init__.py
- **Decision**: Proceed with this approach

**Q5**: Should we extract CompletionHandler to separate package for reuse?
- **Proposed**: No - YAGNI, keep it simple for now
- **Decision**: Keep internal

## 12. Milestones / Plan (Post-Approval)

### Phase 1: Foundation (Days 1-2)
**Tasks**:
- [ ] Set up performance benchmark suite
- [ ] Run baseline tests and capture metrics
- [ ] Review existing test coverage
- [ ] Document current test failures (if any)
- [ ] Create architecture diagram
- [ ] Set up branch protections for test requirements

**DoD**:
- Benchmark suite runs successfully
- Baseline metrics documented
- Test coverage report generated (≥80%)
- Architecture diagram approved

### Phase 2: ToolCall Normalization (Days 3-4)
**Tasks**:
- [ ] Create `models/tool_call.py` with ToolCall class
- [ ] Write tests for ToolCall (dict format, object format, edge cases)
- [ ] Update Agent to use ToolCall internally
- [ ] Run full test suite
- [ ] Run performance benchmarks
- [ ] Code review

**DoD**:
- All tests pass (100%)
- ToolCall tests achieve >90% coverage
- Performance within 5% of baseline
- Code reviewed and approved
- Merged to main

### Phase 3: MessageFactory Extraction (Days 5-7)
**Tasks**:
- [ ] Create `models/message_factory.py`
- [ ] Write tests for MessageFactory
- [ ] Extract message creation from Agent to MessageFactory
- [ ] Update Agent to use MessageFactory
- [ ] Update any affected tests (internal only)
- [ ] Run full test suite
- [ ] Run performance benchmarks
- [ ] Code review

**DoD**:
- All tests pass (100%)
- MessageFactory tests achieve >90% coverage
- Agent class reduced by ~100 lines
- Performance within 5% of baseline
- Merged to main

### Phase 4: Tool Registration Strategies (Days 8-11)
**Tasks**:
- [ ] Create `utils/tools/strategies.py`
- [ ] Implement strategy classes (String, Module, Dict, Callable)
- [ ] Write tests for each strategy
- [ ] Create `models/tool_manager.py`
- [ ] Write tests for ToolManager
- [ ] Refactor Agent.__init__ to use ToolManager
- [ ] Run full test suite
- [ ] Run performance benchmarks
- [ ] Code review

**DoD**:
- All tests pass (100%)
- Strategy tests achieve >90% coverage
- ToolManager tests achieve >90% coverage
- Agent.__init__ reduced by ~150 lines
- Tool registration time within 5% of baseline
- Merged to main

### Phase 5: CompletionHandler Extraction (Days 12-14)
**Tasks**:
- [ ] Create `models/completion.py`
- [ ] Implement CompletionHandler
- [ ] Write tests for CompletionHandler
- [ ] Refactor Agent.step() to use CompletionHandler
- [ ] Run full test suite
- [ ] Run performance benchmarks
- [ ] Code review

**DoD**:
- All tests pass (100%)
- CompletionHandler tests achieve >90% coverage
- Agent class reduced by ~80 lines
- LLM call performance unchanged
- Merged to main

### Phase 6: Streaming Consolidation (Days 15-19)
⚠️ **HIGH RISK PHASE** - Extra care needed

**Tasks**:
- [ ] Create `models/streaming.py`
- [ ] Implement StreamingHandler
- [ ] Write comprehensive streaming tests
- [ ] Identify shared logic between _go_complete and _go_stream
- [ ] Extract shared logic to common methods
- [ ] Refactor _go_stream to use StreamingHandler
- [ ] Run streaming tests extensively
- [ ] Run full test suite
- [ ] Run performance benchmarks
- [ ] Extended code review

**DoD**:
- All tests pass (100%)
- Streaming tests achieve >95% coverage
- Code duplication reduced by >50%
- Agent class reduced by ~200 lines
- Streaming performance within 5% of baseline
- Manual testing of streaming with real LLM
- Two reviewers approve
- Merged to main

### Phase 7: ToolRunner Restructure (Days 20-22)
**Tasks**:
- [ ] Create `utils/tools/registry.py`
- [ ] Create `utils/tools/executor.py`
- [ ] Create `utils/tools/loader.py`
- [ ] Refactor ToolRunner to use new modules
- [ ] Update tests
- [ ] Run full test suite
- [ ] Run performance benchmarks
- [ ] Code review

**DoD**:
- All tests pass (100%)
- Tool execution time unchanged
- Code organization improved
- Merged to main

### Phase 8: Final Polish (Days 23-25)
**Tasks**:
- [ ] Update architecture documentation
- [ ] Add docstrings to all new classes
- [ ] Create contributor migration guide
- [ ] Run final full test suite
- [ ] Run final performance benchmarks
- [ ] Generate coverage report
- [ ] Final review of all changes

**DoD**:
- All documentation updated
- All tests pass (100%)
- Coverage ≥80%
- Performance within 5% of baseline
- README updated
- Architecture diagram accurate
- Migration guide complete

### Dependencies
- **No blockers**: All work can proceed independently
- **Sequential phases**: Each phase builds on previous
- **Parallel work possible**: Documentation can happen during development

---

## Approval Gate

**This TDR must be reviewed and approved before coding begins.**

**Review Checklist**:
- [ ] Spec reviewed and approved
- [ ] Impact analysis reviewed and approved
- [ ] TDR reviewed and approved
- [ ] Test strategy is sound
- [ ] Phased approach agreed upon
- [ ] Performance targets agreed upon
- [ ] Timeline is reasonable

**Approvers**: @adamwdraper

**Status**: 🟡 Awaiting Review

