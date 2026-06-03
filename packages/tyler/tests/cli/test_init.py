"""Tests for the Tyler init scaffolding."""

from tyler.cli.init import create_agent_py


def test_init_agent_template_uses_agent_result_contract(tmp_path):
    """Generated starter code should use AgentResult fields from run()."""
    create_agent_py(tmp_path, "demo-agent", "Help users")

    generated = (tmp_path / "agent.py").read_text()

    assert "result = await agent.run(thread)" in generated
    assert "for msg in result.new_messages:" in generated
    assert "processed_thread, new_messages = await agent.go(thread)" not in generated
