# Impact Analysis — Structured Output & Dependency Injection

## Modules/packages likely touched
- `packages/tyler/tyler/models/execution.py` - Add `structured_data` to `AgentResult`, add `StructuredOutputError`
- `packages/tyler/tyler/models/agent.py` - Add `response_type`, `retry_config` fields and `tool_context` parameter
- `packages/tyler/tyler/models/retry_config.py` - New file for `RetryConfig` model
- `packages/tyler/tyler/utils/tool_runner.py` - Add context injection support
- `packages/tyler/tyler/__init__.py` - Export new classes
- `packages/tyler/tests/` - New test files for each feature

## Contracts to update (APIs, events, schemas, migrations)
- `AgentResult` dataclass: Add optional `structured_data: Optional[BaseModel]` field
- `Agent.run()` signature: Add `response_type` and `tool_context` optional parameters
- `Agent.stream()` signature: Add `tool_context` optional parameter (structured output not applicable to streaming)
- `ToolRunner.run_tool_async()`: Add `context` parameter for injection

## Risks
- Security: Low risk - context injection is opt-in and controlled by developer
- Performance/Availability: 
  - Retry adds latency on validation failures (expected, configurable)
  - JSON schema mode may have slightly different latency than regular completion
- Data integrity: 
  - Pydantic validation ensures data integrity
  - Risk of LLM not producing valid JSON (handled by retry)

## Observability needs
- Logs: 
  - Log when structured output mode is active
  - Log validation failures and retry attempts
  - Log when tool context is injected
- Metrics:
  - Count of structured output requests
  - Validation failure rate
  - Retry success rate
- Alerts:
  - None required initially (features are opt-in)

