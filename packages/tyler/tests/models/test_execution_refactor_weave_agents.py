"""Contract tests for the Tyler execution refactor and Weave Agents tracing."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from narrator import Message, Thread
from tyler import Agent, AgentResult, EventType


def test_agent_result_positional_args_preserve_pre_execution_order():
    """Adding execution telemetry does not change existing positional arguments."""
    thread = Thread()
    message = Message(role="assistant", content="Done")
    retry_history = [{"attempt": 1}]

    result = AgentResult(thread, [message], "Done", {"ok": True}, 2, retry_history)

    assert result.thread is thread
    assert result.new_messages == [message]
    assert result.content == "Done"
    assert result.structured_data == {"ok": True}
    assert result.validation_retries == 2
    assert result.retry_history == retry_history
    assert result.execution.events == []


class MockChoice:
    def __init__(self, message=None):
        self.message = message


class MockMessage:
    def __init__(self, content="Test response", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class MockResponse:
    def __init__(self, content="Test response", tool_calls=None, total_tokens=30):
        self.choices = [MockChoice(MockMessage(content, tool_calls))]
        self.usage = SimpleNamespace(
            completion_tokens=10,
            prompt_tokens=max(total_tokens - 10, 0),
            total_tokens=total_tokens,
        )


def _tool_definition(name: str, implementation):
    return {
        "definition": {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        "implementation": implementation,
    }


def _tool_call(name: str, call_id: str = "call_123", arguments=None):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments or {}),
        ),
    )


@pytest.mark.asyncio
async def test_agent_result_execution_contract_no_tools():
    """AgentResult exposes a stable execution summary for a no-tool run."""
    mock_completion = AsyncMock(return_value=MockResponse("Done", total_tokens=42))

    with patch("tyler.models.agent.acompletion", mock_completion):
        agent = Agent(model_name="gpt-4o-mini", purpose="Test agent")
        thread = Thread()
        thread.add_message(Message(role="user", content="Hello"))

        result = await agent.run(thread)

    assert isinstance(result, AgentResult)
    assert result.content == "Done"
    assert result.execution.duration_ms >= 0
    assert result.execution.total_tokens == 42
    assert result.execution.tool_calls == []
    assert EventType.LLM_REQUEST in [event.type for event in result.execution.events]
    assert EventType.EXECUTION_COMPLETE in [event.type for event in result.execution.events]


@pytest.mark.asyncio
async def test_agent_result_execution_contract_with_tool_call():
    """Tool calls are summarized with arguments, result, duration, and status."""
    tool_call = _tool_call("calculate", arguments={"x": 5, "y": 3})
    mock_completion = AsyncMock(
        side_effect=[
            MockResponse("Let me calculate", tool_calls=[tool_call], total_tokens=20),
            MockResponse("The result is 8", total_tokens=15),
        ]
    )

    async def calculate(x: int, y: int) -> int:
        return x + y

    with patch("tyler.models.agent.acompletion", mock_completion):
        agent = Agent(
            model_name="gpt-4o-mini",
            purpose="Test agent",
            tools=[_tool_definition("calculate", calculate)],
        )
        thread = Thread()
        thread.add_message(Message(role="user", content="What is 5 + 3?"))

        result = await agent.run(thread)

    assert result.content == "The result is 8"
    assert result.execution.total_tokens == 35
    assert len(result.execution.tool_calls) == 1
    summary = result.execution.tool_calls[0]
    assert summary.tool_name == "calculate"
    assert summary.tool_call_id == "call_123"
    assert summary.arguments == {"x": 5, "y": 3}
    assert summary.result == "8"
    assert summary.error is None
    assert summary.success is True
    assert summary.duration_ms is not None


@pytest.mark.asyncio
async def test_same_name_custom_tools_are_isolated_per_agent():
    """Two agents can own different implementations for the same tool name."""
    agent_a = Agent(
        name="AgentA",
        tools=[_tool_definition("identity", lambda: "agent-a")],
    )
    agent_b = Agent(
        name="AgentB",
        tools=[_tool_definition("identity", lambda: "agent-b")],
    )

    assert await agent_a._handle_tool_execution(_tool_call("identity")) == "agent-a"
    assert await agent_b._handle_tool_execution(_tool_call("identity")) == "agent-b"


@pytest.mark.asyncio
async def test_skill_tools_register_on_owning_agent_runner(tmp_path):
    """Skills register activate_skill on the agent runner used for execution."""
    skill_dir = tmp_path / "summary-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: summary-skill\ndescription: Summarize content.\n---\nUse bullets."
    )

    agent = Agent(skills=[str(skill_dir)])

    assert "activate_skill" in agent._tool_runner.tools
    result = await agent._tool_runner.run_tool_async(
        "activate_skill", {"name": "summary-skill"}
    )
    assert result == "Use bullets."


@pytest.mark.asyncio
async def test_delegation_tool_uses_agent_result_contract():
    """Delegation handlers treat child go()/run() as returning AgentResult."""
    child = Agent(name="Researcher", purpose="Research things")

    async def fake_go(thread):
        msg = Message(role="assistant", content="child done")
        thread.add_message(msg)
        return AgentResult(thread=thread, new_messages=[msg], content="child done")

    with patch.object(child, "go", fake_go):
        parent = Agent(name="Coordinator", agents=[child])
        result = await parent._handle_tool_execution(
            _tool_call("delegate_to_Researcher", arguments={"task": "research this"})
        )

    assert result == "child done"


@pytest.mark.asyncio
async def test_connect_mcp_registers_tools_on_owning_agent_runner():
    """MCP tools register into the active agent runner after connect_mcp()."""
    agent = Agent(
        name="MCPAgent",
        mcp={
            "servers": [
                {"name": "test", "transport": "sse", "url": "https://example.com/mcp"}
            ]
        },
    )

    with patch("tyler.mcp.config_loader._load_mcp_config") as mock_load:
        mock_load.return_value = (
            [_tool_definition("mcp_lookup", AsyncMock(return_value="mcp result"))],
            AsyncMock(),
        )
        await agent.connect_mcp()

    assert "mcp_lookup" in agent._tool_runner.tools


@pytest.mark.asyncio
async def test_weave_agents_tracing_calls_mocked_session_turn_llm_and_tool():
    """When Weave Agents APIs are active, Tyler maps run/LLM/tool spans."""
    calls = []

    class FakeWeave:
        def get_client(self):
            return object()

        def start_session(self, **kwargs):
            calls.append(("session", kwargs))
            return SimpleNamespace(kind="session")

        def start_turn(self, **kwargs):
            calls.append(("turn", kwargs))
            return SimpleNamespace(kind="turn")

        def start_llm(self, **kwargs):
            calls.append(("llm", kwargs))
            return SimpleNamespace(kind="llm")

        def start_tool(self, **kwargs):
            calls.append(("tool", kwargs))
            return SimpleNamespace(kind="tool")

    tool_call = _tool_call("lookup", arguments={"query": "x"})
    mock_completion = AsyncMock(
        side_effect=[
            MockResponse("Looking", tool_calls=[tool_call], total_tokens=10),
            MockResponse("Found it", total_tokens=11),
        ]
    )

    with patch("tyler.models.agent.acompletion", mock_completion), patch(
        "tyler.tracing.weave_agents.weave", FakeWeave()
    ):
        agent = Agent(tools=[_tool_definition("lookup", lambda query: f"found {query}")])
        thread = Thread()
        thread.add_message(Message(role="user", content="Find x"))

        await agent.run(thread)

    call_kinds = [kind for kind, _kwargs in calls]
    assert "session" in call_kinds
    assert "turn" in call_kinds
    assert "llm" in call_kinds
    assert "tool" in call_kinds
