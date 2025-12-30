# Technical Design Review (TDR) — A2A Protocol v0.3.0 Full Support

**Author**: AI Agent  
**Date**: 2025-12-29  
**Links**: [Spec](./spec.md), [Impact](./impact.md), [A2A Protocol](https://a2a-protocol.org/latest/)

---

## 1. Summary

This TDR describes the upgrade of Tyler's A2A (Agent-to-Agent) implementation to fully comply with the A2A Protocol v0.3.0 specification. The upgrade adds support for all Part types (TextPart, FilePart, DataPart), Artifact production and consumption, context-based task grouping, and webhook push notifications for long-running tasks.

The implementation leverages the official `a2a-sdk` Python package (v0.3.0+) as a required dependency, ensuring compatibility with the evolving A2A ecosystem while minimizing maintenance burden for protocol compliance.

## 2. Decision Drivers & Non-Goals

### Drivers
- **Interoperability**: Tyler agents must work with agents built on LangGraph, CrewAI, and other A2A-compliant frameworks
- **Feature completeness**: Current implementation only supports basic text messages; real-world use cases require files and structured data
- **Long-running tasks**: Enterprise workloads need asynchronous task handling with reliable notification delivery
- **Ecosystem alignment**: A2A Protocol is now a Linux Foundation project with growing adoption

### Non-Goals
- Signed Agent Cards (security enhancement for future iteration)
- A2A extensions framework support
- WebSocket transport (HTTP-only for this iteration)
- A2A discovery service integration
- Protocol versions prior to 0.3.0

## 3. Current State — Codebase Map

### Key Modules
```
packages/tyler/tyler/a2a/
├── __init__.py      # Exports A2AAdapter, A2AClient, A2AServer
├── adapter.py       # Converts A2A agents to Tyler delegation tools
├── client.py        # HTTP client for connecting to A2A servers
└── server.py        # HTTP server exposing Tyler agents via A2A
```

### Existing Data Models
- `A2AConnection` (dataclass): Connection info with agent_card reference
- `TylerTaskExecution` (dataclass): Task execution state with Tyler thread/agent references

### External Contracts
- Depends on `a2a-sdk` types: `AgentCard`, `Task`, `Message`, `Part`, `TextPart`, `TaskStatus`
- Uses FastAPI for HTTP server, httpx/aiohttp for HTTP client

### Current Observability
- Python logging at INFO/DEBUG levels
- No metrics or structured tracing

## 4. Proposed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tyler A2A Module                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │   types.py   │    │   client.py  │    │    server.py     │   │
│  │              │    │              │    │                  │   │
│  │ - FilePart   │◄───│ - create_task│    │ - Agent Card     │   │
│  │ - DataPart   │    │ - context_id │    │ - Artifact prod. │   │
│  │ - Artifact   │    │ - artifacts  │    │ - Auth declaration│  │
│  │ - PushConfig │    │ - push notif │    │ - Push notif     │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│         │                   │                    │               │
│         └───────────────────┴────────────────────┘               │
│                              │                                   │
│                    ┌─────────▼─────────┐                         │
│                    │  notifications.py │                         │
│                    │                   │                         │
│                    │ - Webhook sender  │                         │
│                    │ - Event types     │                         │
│                    │ - Retry logic     │                         │
│                    └───────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `types.py` | Type definitions for FilePart, DataPart, Artifact, PushNotificationConfig; conversion helpers between A2A SDK types and Tyler internal types |
| `client.py` | HTTP client for A2A servers; sends messages with any Part type; receives artifacts; subscribes to push notifications |
| `server.py` | HTTP server exposing Tyler agent; produces Artifacts from Tyler results; declares auth requirements; sends push notifications |
| `adapter.py` | Converts A2A agent capabilities to Tyler delegation tools; handles Part type conversion in tool results |
| `notifications.py` | Async webhook sender with retry logic; event serialization; URL validation for SSRF prevention |

### Interfaces & Data Contracts

#### Part Type Handling
```python
# Converting Tyler content to A2A Parts
def tyler_to_a2a_parts(content: Union[str, dict, bytes, Path]) -> List[Part]:
    if isinstance(content, str):
        return [TextPart(text=content)]
    elif isinstance(content, dict):
        return [DataPart(data=content)]
    elif isinstance(content, (bytes, Path)):
        return [FilePart(data=..., name=..., mime_type=...)]

# Converting A2A Parts to Tyler content
def a2a_parts_to_tyler(parts: List[Part]) -> dict:
    return {
        "text": extract_text_parts(parts),
        "files": extract_file_parts(parts),
        "data": extract_data_parts(parts),
    }
```

#### Artifact Structure
```python
@dataclass
class Artifact:
    artifact_id: str  # UUID4
    name: str         # Human-readable name
    parts: List[Part] # Content parts
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
```

#### Push Notification Events
```python
class PushEventType(Enum):
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    ARTIFACT_PRODUCED = "task.artifact"
```

### Error Handling
- **Webhook failures**: Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- **File URI fetch failures**: Return error in task result, don't block processing
- **Invalid Part types**: Log warning and skip unknown parts
- **SSRF attempts**: Reject immediately with 400 error, log security event

### Idempotency
- Task creation is idempotent via `task_id` (client can retry safely)
- Webhook notifications include `event_id` for deduplication
- Artifact production is idempotent via `artifact_id`

## 5. Alternatives Considered

### Option A: Implement A2A Protocol Directly (No SDK)
**Pros:**
- Full control over implementation details
- No external dependency

**Cons:**
- High maintenance burden for protocol updates
- Risk of spec drift as A2A evolves
- Duplicates work already done by official SDK

### Option B: Keep a2a-sdk Optional (Current State)
**Pros:**
- Smaller installation footprint
- No breaking changes for non-A2A users

**Cons:**
- Feature fragmentation (some users have A2A, some don't)
- Harder to test and maintain two code paths
- Confusing user experience

### Option C: Upgrade a2a-sdk as Required Dependency (Chosen)
**Pros:**
- Consistent feature set for all users
- Automatic protocol compliance updates via SDK upgrades
- Simpler codebase with single code path
- Active maintenance by A2A project team

**Cons:**
- Larger installation footprint
- Dependency on external project

**Decision**: Option C chosen because interoperability is a core value proposition of Tyler, and the A2A Protocol is becoming a standard. The SDK is actively maintained by the Linux Foundation project.

## 6. Data Model & Contract Changes

### New Types (types.py)
```python
@dataclass
class FilePart:
    name: str
    mime_type: str
    data: Optional[bytes] = None
    uri: Optional[str] = None

@dataclass
class DataPart:
    data: Dict[str, Any]
    mime_type: str = "application/json"

@dataclass
class Artifact:
    artifact_id: str
    name: str
    parts: List[Union[TextPart, FilePart, DataPart]]
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class PushNotificationConfig:
    webhook_url: str
    events: List[str] = field(default_factory=lambda: ["created", "updated", "completed"])
    headers: Optional[Dict[str, str]] = None
    secret: Optional[str] = None  # For HMAC signing
```

### API Changes

#### A2AClient.create_task (Extended)
```python
async def create_task(
    self,
    agent_name: str,
    content: Union[str, List[Part]],  # Extended to accept Part list
    context_id: Optional[str] = None,  # NEW
    push_notification_config: Optional[PushNotificationConfig] = None,  # NEW
    **kwargs
) -> Optional[str]:
```

#### A2AServer Agent Card (Extended)
```python
card_data = {
    "name": agent_name,
    "version": "1.0.0",
    "description": agent_purpose,
    "protocol_version": "0.3.0",  # Updated
    "capabilities": [...],
    "authentication": {  # NEW
        "schemes": ["bearer"],
        "required": False
    },
    "push_notifications": {  # NEW
        "supported": True,
        "events": ["task.created", "task.updated", "task.completed", "task.artifact"]
    }
}
```

### Backward Compatibility
- All existing API signatures remain valid (new parameters are optional)
- TextPart-only messages continue to work unchanged
- Existing tests should pass without modification

## 7. Security, Privacy, Compliance

### AuthN/AuthZ
- Agent Cards now declare authentication requirements
- No change to actual auth implementation (still header-based)

### Secrets Management
- Webhook secrets stored in PushNotificationConfig, never logged
- HMAC signatures used for webhook verification (optional but recommended)

### Threat Model & Mitigations

| Threat | Risk | Mitigation |
|--------|------|------------|
| SSRF via webhook URL | High | Validate URLs: HTTPS only, block private IPs, block localhost |
| SSRF via FilePart URI | High | Same validation as webhooks |
| Webhook secret exposure | Medium | Never log secrets; use HMAC signing |
| DoS via large files | Medium | Enforce max file size (default 10MB) |
| Replay attacks on webhooks | Low | Include timestamp and event_id; receivers should validate |

### URL Validation Implementation
```python
def validate_webhook_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    try:
        ip = socket.gethostbyname(parsed.hostname)
        if ipaddress.ip_address(ip).is_private:
            return False
    except socket.gaierror:
        return False
    return True
```

## 8. Observability & Operations

### Logs
| Level | Event |
|-------|-------|
| INFO | A2A server started with protocol version X |
| INFO | Task {task_id} created with context_id {context_id} |
| INFO | Artifact {artifact_id} produced for task {task_id} |
| INFO | Push notification sent to {webhook_url} for event {event_type} |
| WARNING | Push notification failed (attempt {n}/{max}): {error} |
| WARNING | FilePart URI fetch failed: {uri} - {error} |
| ERROR | SSRF attempt blocked: {url} |
| DEBUG | Received message with parts: {part_types} |

### Metrics (Optional, via weave/wandb integration)
- `a2a_tasks_total{context_id_present}`
- `a2a_artifacts_total`
- `a2a_push_notifications_total{event_type, status}`
- `a2a_file_parts_total{source: inline|uri}`

### Alerts
- Webhook failure rate > 10% over 5 minutes
- SSRF attempt detected (immediate security alert)

## 9. Rollout & Migration

### Feature Flags
- No feature flags needed; changes are additive and backward-compatible

### Migration Steps
1. Update `pyproject.toml` with new dependencies
2. Run `uv sync` to install a2a-sdk
3. Existing code continues to work unchanged
4. New features available immediately

### Revert Plan
- Revert commit and re-sync dependencies
- No data migration required
- Blast radius: A2A features only (Tyler core unaffected)

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
All tests written before implementation. Order:
1. Write failing test
2. Confirm failure (red)
3. Implement minimal code to pass
4. Refactor with green tests

### Spec → Test Mapping

| Acceptance Criterion | Test ID(s) |
|---------------------|------------|
| AC-1: Protocol Version | `test_server_protocol_version` |
| AC-2: Agent Card Path | `test_agent_card_well_known_path` |
| AC-3: TextPart Support | `test_message_text_part` |
| AC-4: FilePart Inline | `test_message_file_part_inline` |
| AC-5: FilePart URI | `test_message_file_part_uri` |
| AC-6: DataPart Support | `test_message_data_part` |
| AC-7: Artifact Production | `test_artifact_production` |
| AC-8: Context ID Grouping | `test_context_id_grouping` |
| AC-9: Push - Task Created | `test_push_notification_created` |
| AC-10: Push - Task Update | `test_push_notification_update` |
| AC-11: Push - Task Complete | `test_push_notification_complete` |
| AC-12: Auth Declaration | `test_agent_card_authentication` |
| AC-13: Backward Compat | `test_backward_compatibility_text_only` |
| AC-14: Dependency Error | `test_import_error_without_sdk` |

### Test Tiers
- **Unit tests**: Part type conversion, URL validation, artifact creation
- **Integration tests**: Client-server communication, webhook delivery
- **E2E tests**: Full task flow with artifacts and notifications

### Negative & Edge Cases
- Invalid webhook URL (private IP, HTTP)
- Malformed Part data
- Missing required fields
- Oversized files
- Webhook timeout
- Network errors during URI fetch

## 11. Risks & Open Questions

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| a2a-sdk breaking changes | Low | High | Pin to 0.3.x; monitor releases |
| Performance with large files | Medium | Medium | Streaming, size limits |
| Webhook reliability | Medium | Low | Retry logic, logging |

### Open Questions
1. **Q**: Should we support batch artifact retrieval?
   **A**: Defer to future iteration; single artifact retrieval sufficient for v1

2. **Q**: Should webhooks be fire-and-forget or wait for acknowledgment?
   **A**: Fire-and-forget with retry; prevents blocking task processing

## 12. Milestones / Plan

### Task Breakdown

| # | Task | DoD | Owner |
|---|------|-----|-------|
| 1 | Update dependencies in pyproject.toml | Deps added, uv sync passes | Agent |
| 2 | Create types.py with Part/Artifact types | Types defined, unit tests pass | Agent |
| 3 | Update server.py with protocol version, auth | AC-1, AC-2, AC-12 tests pass | Agent |
| 4 | Implement FilePart/DataPart in client.py | AC-3, AC-4, AC-5, AC-6 tests pass | Agent |
| 5 | Implement Artifact support in server.py | AC-7 tests pass | Agent |
| 6 | Implement context_id support | AC-8 tests pass | Agent |
| 7 | Create notifications.py | AC-9, AC-10, AC-11 tests pass | Agent |
| 8 | Update adapter.py for new Part types | Integration tests pass | Agent |
| 9 | Verify backward compatibility | AC-13, AC-14 tests pass | Agent |
| 10 | Update documentation | Docs reflect new features | Agent |

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved in the PR.

