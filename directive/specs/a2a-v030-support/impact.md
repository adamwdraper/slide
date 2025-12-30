# Impact Analysis — A2A Protocol v0.3.0 Full Support

## Modules/packages likely touched

### Tyler Package (`packages/tyler/`)
- `tyler/a2a/__init__.py` - Export new classes (types, notifications)
- `tyler/a2a/server.py` - Major changes: protocol version, artifacts, push notifications, auth
- `tyler/a2a/client.py` - Major changes: FilePart, DataPart, context_id, push notifications
- `tyler/a2a/adapter.py` - Handle new Part types in delegation tools
- `tyler/a2a/types.py` - NEW: Type definitions and helpers for A2A parts/artifacts
- `tyler/a2a/notifications.py` - NEW: Push notification webhook handler

### Tyler Tests (`packages/tyler/tests/a2a/`)
- `test_adapter.py` - Extend tests for new Part types
- `test_client.py` - Extend tests for new features
- `test_server.py` - NEW: Server tests for artifacts, notifications
- `test_artifacts.py` - NEW: Artifact handling tests
- `test_notifications.py` - NEW: Push notification tests
- `test_types.py` - NEW: Part type conversion tests

### Configuration (`packages/tyler/`)
- `pyproject.toml` - Add required dependencies: a2a-sdk, fastapi, uvicorn

### Documentation (`docs/`)
- `docs/concepts/a2a.mdx` - Update with new features
- `docs/guides/a2a-integration.mdx` - Add examples for new capabilities

### Examples (`packages/tyler/examples/`)
- `401_a2a_basic_server.py` - Update with authentication declaration
- `402_a2a_basic_client.py` - Update with FilePart/DataPart examples
- `403_a2a_multi_agent.py` - Add context_id usage example

## Contracts to update (APIs, events, schemas, migrations)

### New/Modified Public APIs

#### A2AServer
```python
class A2AServer:
    def __init__(
        self, 
        tyler_agent, 
        agent_card: Optional[Dict[str, Any]] = None,
        authentication: Optional[Dict[str, Any]] = None  # NEW
    ): ...
    
    # NEW: Push notification configuration
    async def _handle_create_task(
        self, 
        message: Message,
        push_notification_config: Optional[PushNotificationConfig] = None
    ) -> Task: ...
```

#### A2AClient
```python
class A2AClient:
    async def create_task(
        self, 
        agent_name: str, 
        content: Union[str, List[Part]],  # CHANGED: Accept Part list
        context_id: Optional[str] = None,  # NEW
        push_notification_config: Optional[PushNotificationConfig] = None,  # NEW
        **kwargs
    ) -> Optional[str]: ...
    
    # NEW: Artifact retrieval
    async def get_task_artifacts(
        self, 
        agent_name: str, 
        task_id: str
    ) -> List[Artifact]: ...
```

#### A2AAdapter
```python
class A2AAdapter:
    # CHANGED: Support new Part types in delegation
    def _create_delegation_tool(
        self, 
        agent_name: str, 
        agent_card
    ) -> Dict[str, Any]: ...
```

### New Types
```python
# tyler/a2a/types.py
@dataclass
class FilePart:
    name: str
    mime_type: str
    data: Optional[bytes] = None  # Inline
    uri: Optional[str] = None      # Remote

@dataclass
class DataPart:
    data: Dict[str, Any]
    mime_type: str = "application/json"

@dataclass
class Artifact:
    artifact_id: str
    name: str
    parts: List[Part]
    created_at: datetime

@dataclass
class PushNotificationConfig:
    webhook_url: str
    events: List[str] = field(default_factory=lambda: ["created", "updated", "completed"])
    headers: Optional[Dict[str, str]] = None
```

### Webhook Event Schema
```json
{
    "event_type": "task.updated",
    "task_id": "uuid",
    "context_id": "optional-context-uuid",
    "timestamp": "ISO8601",
    "data": {
        "status": "running|completed|error",
        "artifacts": [],
        "message": {}
    }
}
```

## Risks

### Security
- **Webhook SSRF**: Push notifications POST to user-provided URLs. 
  - Mitigation: Validate webhook URLs, block private IP ranges, implement rate limiting
- **File URI Fetching**: FilePart URIs could point to internal resources.
  - Mitigation: Whitelist allowed schemes (https only), block private IPs
- **Auth Token Exposure**: Authentication headers in webhook callbacks.
  - Mitigation: Use HMAC signatures for webhook verification instead of tokens

### Performance/Availability
- **Webhook Timeouts**: Slow webhooks could block task processing.
  - Mitigation: Async webhook delivery with timeout, fire-and-forget pattern
- **Large File Handling**: Base64-encoded files in messages increase memory usage.
  - Mitigation: Stream large files, implement size limits
- **SDK Dependency**: Adding a2a-sdk as required increases installation footprint.
  - Mitigation: Well-justified addition; SDK is actively maintained

### Data integrity
- **Artifact ID Uniqueness**: Must ensure artifact_id is globally unique.
  - Mitigation: Use UUID4 for all artifact identifiers
- **Context ID Association**: Tasks must correctly associate with context_id.
  - Mitigation: Store context_id in task metadata, validate on retrieval

## Observability needs

### Logs
- `INFO`: A2A server started with protocol version
- `INFO`: Task created with context_id (if present)
- `INFO`: Artifact produced for task
- `INFO`: Push notification sent successfully
- `WARNING`: Push notification delivery failed (with retry count)
- `WARNING`: FilePart URI fetch failed
- `ERROR`: Webhook URL validation failed (SSRF attempt)
- `DEBUG`: Part type received (TextPart/FilePart/DataPart)
- `DEBUG`: Message content extraction details

### Metrics
- `a2a_tasks_created_total` - Counter of tasks created, labeled by context_id presence
- `a2a_artifacts_produced_total` - Counter of artifacts produced
- `a2a_push_notifications_sent_total` - Counter of webhook notifications, labeled by event_type
- `a2a_push_notifications_failed_total` - Counter of failed webhook deliveries
- `a2a_file_parts_processed_total` - Counter of file parts handled, labeled by source (inline/uri)
- `a2a_message_processing_duration_seconds` - Histogram of message processing time

### Alerts
- **High webhook failure rate**: > 10% of push notifications failing in 5-minute window
- **Large file processing**: FilePart > 10MB processed (potential memory issue)
- **SSRF attempt detected**: Any blocked webhook URL (security alert)

