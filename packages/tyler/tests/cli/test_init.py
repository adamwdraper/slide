"""Tests for the Tyler init scaffolding."""

from pathlib import Path

from tyler.cli.init import create_agent_py


def test_init_agent_template_uses_agent_result_contract(tmp_path):
    """Generated starter code should use AgentResult fields from run()."""
    create_agent_py(tmp_path, "demo-agent", "Help users")

    generated = (tmp_path / "agent.py").read_text()

    assert "result = await agent.run(thread)" in generated
    assert "for msg in result.new_messages:" in generated
    assert "processed_thread, new_messages = await agent.go(thread)" not in generated


def test_mcp_docs_and_config_do_not_claim_websocket_transport():
    """MCP docs/config examples should not advertise websocket support."""
    root = Path(__file__).resolve().parents[4]
    files = [
        root / "packages/tyler/tyler-chat-config.yaml",
        root / "packages/tyler/README.md",
        root / "docs/guides/mcp-integration.mdx",
        root / "docs/concepts/mcp.mdx",
        root / "docs/apps/tyler-cli.mdx",
    ]

    for path in files:
        content = path.read_text().lower()
        assert "websocket" not in content, f"{path} still claims MCP websocket support"
