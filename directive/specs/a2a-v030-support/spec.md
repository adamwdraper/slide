# Spec (per PR)

**Feature name**: A2A Protocol v0.3.0 Full Support  
**One-line summary**: Upgrade Tyler's A2A implementation to fully comply with the Agent-to-Agent Protocol v0.3.0 specification, enabling complete interoperability with other A2A-compliant agents.

---

## Problem
Tyler's current A2A implementation is incomplete and outdated relative to the latest A2A Protocol v0.3.0 specification. Key gaps include:

1. **Protocol version mismatch**: Tyler declares `protocol_version: "1.0"` instead of `"0.3.0"`
2. **Missing Part types**: Only `TextPart` is supported; `FilePart` and `DataPart` are not
3. **No Artifact support**: Task deliverables cannot be properly structured as A2A Artifacts
4. **No contextId**: Multi-task coordination across conversations is not possible
5. **No push notifications**: Long-running tasks cannot notify clients via webhooks
6. **No authentication declaration**: Agent Cards don't expose auth requirements
7. **Optional dependency**: `a2a-sdk` is optional, causing feature fragmentation

These gaps prevent Tyler agents from fully participating in A2A ecosystems and limit interoperability with agents built on other frameworks.

## Goal
Tyler agents can act as both A2A clients and servers with complete v0.3.0 compliance, enabling seamless multi-agent coordination across platforms, proper handling of files and structured data, and support for long-running asynchronous tasks with push notifications.

## Success Criteria
- [ ] Tyler agents can send and receive all Part types (TextPart, FilePart, DataPart)
- [ ] Tyler agents can produce and consume Artifacts with proper structure
- [ ] Multi-task coordination works via contextId grouping
- [ ] Long-running tasks can deliver updates via webhook push notifications
- [ ] Agent Cards declare authentication requirements per A2A spec
- [ ] All existing A2A tests continue to pass
- [ ] New integration tests validate v0.3.0 compliance

## User Story
As a developer building multi-agent systems, I want Tyler to fully support the A2A Protocol v0.3.0, so that my Tyler agents can seamlessly communicate with agents built on any A2A-compliant framework (LangGraph, CrewAI, etc.) and handle files, structured data, and long-running tasks properly.

## Flow / States

### Happy Path: File Transfer via A2A
1. Client agent connects to Tyler A2A server
2. Client sends task with FilePart containing a document
3. Tyler agent processes document, produces Artifact with analysis
4. Artifact streamed back to client with structured DataPart results

### Edge Case: Long-Running Task with Push Notifications
1. Client creates task with `webhook_url` for notifications
2. Tyler server acknowledges task creation immediately
3. As task progresses, server POSTs status updates to webhook
4. On completion, server POSTs final result with Artifacts to webhook
5. Client can also poll for status as fallback

## UX Links
- Designs: N/A (API/SDK feature)
- Prototype: N/A
- Copy/Content: See A2A Protocol docs at https://a2a-protocol.org/latest/

## Requirements
- Must support A2A Protocol version 0.3.0
- Must handle TextPart, FilePart, and DataPart in messages
- Must produce and consume Artifacts as task deliverables
- Must support contextId for grouping related tasks
- Must support push notifications via webhook for task updates
- Must declare authentication requirements in Agent Cards
- Must use snake_case for class fields per v0.3.0 convention
- Must serve Agent Card at `/.well-known/agent-card.json` path
- Must not break existing A2A functionality
- Must not require code changes for existing Tyler agent configurations

## Acceptance Criteria

### AC-1: Protocol Version
- Given a Tyler A2A server is running
- When a client fetches the Agent Card
- Then `protocol_version` equals `"0.3.0"`

### AC-2: Agent Card Path
- Given a Tyler A2A server is running at `http://localhost:8000`
- When a client requests `GET /.well-known/agent-card.json`
- Then the Agent Card JSON is returned

### AC-3: TextPart Support
- Given a Tyler A2A server receives a message
- When the message contains a TextPart
- Then the text content is extracted and processed correctly

### AC-4: FilePart Support (Inline)
- Given a Tyler A2A server receives a message
- When the message contains a FilePart with inline Base64 data
- Then the file is decoded and made available to the Tyler agent

### AC-5: FilePart Support (URI)
- Given a Tyler A2A server receives a message
- When the message contains a FilePart with a URI
- Then the file is fetched from the URI and made available to the Tyler agent

### AC-6: DataPart Support
- Given a Tyler A2A server receives a message
- When the message contains a DataPart with JSON data
- Then the structured data is parsed and made available to the Tyler agent

### AC-7: Artifact Production
- Given a Tyler agent completes a task with results
- When generating the A2A response
- Then results are wrapped in an Artifact with unique `artifact_id` and name

### AC-8: Context ID Grouping
- Given a client creates multiple tasks with the same `context_id`
- When querying task history
- Then all tasks with that context_id are logically grouped

### AC-9: Push Notification - Task Created
- Given a client creates a task with a `webhook_url`
- When the task is created
- Then an HTTP POST is sent to the webhook with task creation event

### AC-10: Push Notification - Task Update
- Given a task has a registered webhook
- When the task status changes or produces output
- Then an HTTP POST is sent to the webhook with the update

### AC-11: Push Notification - Task Complete
- Given a task has a registered webhook
- When the task completes (success or error)
- Then an HTTP POST is sent to the webhook with final status and artifacts

### AC-12: Authentication Declaration
- Given a Tyler A2A server is configured with auth requirements
- When a client fetches the Agent Card
- Then the `authentication` field declares supported schemes

### AC-13: Backward Compatibility
- Given existing Tyler A2A client code using TextPart only
- When upgrading to the new implementation
- Then existing code continues to work without modification

### AC-14: Dependency Requirement (Negative Case)
- Given a2a-sdk is not installed
- When importing tyler.a2a modules
- Then a clear ImportError is raised with installation instructions

## Non-Goals
- Implementing signed Agent Cards (future enhancement)
- Implementing A2A extensions framework (future enhancement)
- Supporting A2A protocol versions prior to 0.3.0
- Adding A2A discovery service integration
- Implementing A2A over WebSocket transport (HTTP only for now)

