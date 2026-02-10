"""Tests for AGENTS.md support.

Tests cover discovery, loading, system prompt injection, MCP survival,
YAML config processing, and no-regression scenarios.
"""
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from tyler import Agent
from tyler.models.agents_md import discover_agents_md, load_agents_md, MAX_AGENTS_MD_SIZE
from tyler.config import load_config
from tyler.utils.tool_runner import tool_runner


@pytest.fixture(autouse=True)
def cleanup_activate_skill():
    """Clean up activate_skill from tool_runner after each test."""
    yield
    if "activate_skill" in tool_runner.tools:
        del tool_runner.tools["activate_skill"]
    if "activate_skill" in tool_runner.tool_attributes:
        del tool_runner.tool_attributes["activate_skill"]


def _within(paths, root):
    """Filter discovered paths to only those within root (for test isolation)."""
    root = root.resolve()
    return [p for p in paths if root in p.parents or p.parent == root]


class TestDiscovery:
    """Test hierarchical AGENTS.md discovery."""

    def test_discover_from_nested_dir(self, tmp_path):
        """Discovers AGENTS.md files walking upward from a nested directory."""
        # Create hierarchy: root/AGENTS.md, root/sub/AGENTS.md
        (tmp_path / "AGENTS.md").write_text("Root instructions")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "AGENTS.md").write_text("Sub instructions")

        found = _within(discover_agents_md(sub), tmp_path)

        assert len(found) == 2
        # Root-first ordering
        assert found[0] == (tmp_path / "AGENTS.md").resolve()
        assert found[1] == (sub / "AGENTS.md").resolve()

    def test_discover_root_only(self, tmp_path):
        """Finds AGENTS.md only at root level."""
        (tmp_path / "AGENTS.md").write_text("Root only")
        sub = tmp_path / "sub"
        sub.mkdir()

        found = _within(discover_agents_md(sub), tmp_path)

        assert len(found) == 1
        assert found[0] == (tmp_path / "AGENTS.md").resolve()

    def test_discover_none_found(self, tmp_path):
        """Returns empty list when no AGENTS.md found in tmp_path tree."""
        sub = tmp_path / "sub"
        sub.mkdir()

        found = _within(discover_agents_md(sub), tmp_path)

        assert found == []

    def test_discover_ordering_root_first(self, tmp_path):
        """Result ordering is root-first, closest-last."""
        # root/AGENTS.md, root/a/AGENTS.md, root/a/b/AGENTS.md
        (tmp_path / "AGENTS.md").write_text("1")
        a = tmp_path / "a"
        a.mkdir()
        (a / "AGENTS.md").write_text("2")
        b = a / "b"
        b.mkdir()
        (b / "AGENTS.md").write_text("3")

        found = _within(discover_agents_md(b), tmp_path)

        assert len(found) == 3
        assert found[0] == (tmp_path / "AGENTS.md").resolve()
        assert found[1] == (a / "AGENTS.md").resolve()
        assert found[2] == (b / "AGENTS.md").resolve()


class TestLoading:
    """Test load_agents_md with various config variants."""

    def test_load_none_returns_empty(self):
        """agents_md=None returns empty string."""
        assert load_agents_md(None) == ""

    def test_load_false_returns_empty(self):
        """agents_md=False returns empty string."""
        assert load_agents_md(False) == ""

    def test_load_true_auto_discovers(self, tmp_path):
        """agents_md=True triggers auto-discovery from base_dir."""
        (tmp_path / "AGENTS.md").write_text("Auto-discovered content")

        result = load_agents_md(True, base_dir=tmp_path)

        assert "Auto-discovered content" in result

    def test_load_explicit_path(self, tmp_path):
        """agents_md=str loads a single file."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Explicit file content")

        result = load_agents_md(str(agents_file))

        assert result == "Explicit file content"

    def test_load_multiple_paths(self, tmp_path):
        """agents_md=List[str] loads multiple files, joined with separator."""
        file_a = tmp_path / "A.md"
        file_b = tmp_path / "B.md"
        file_a.write_text("File A")
        file_b.write_text("File B")

        result = load_agents_md([str(file_a), str(file_b)])

        assert "File A" in result
        assert "File B" in result
        assert "\n\n---\n\n" in result

    def test_load_missing_file_skipped(self, tmp_path):
        """Missing file is skipped with warning, not an error."""
        result = load_agents_md(str(tmp_path / "nonexistent.md"))

        assert result == ""

    def test_load_truncation(self, tmp_path):
        """Content exceeding MAX_AGENTS_MD_SIZE is truncated."""
        big_content = "x" * (MAX_AGENTS_MD_SIZE + 1000)
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text(big_content)

        result = load_agents_md(str(agents_file))

        assert len(result) <= MAX_AGENTS_MD_SIZE

    def test_load_true_no_files_found(self, tmp_path):
        """agents_md=True with no files returns empty string."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = load_agents_md(True, base_dir=empty_dir)

        assert result == ""


class TestSystemPromptInjection:
    """Test that AGENTS.md content appears in the system prompt."""

    def test_agents_md_in_system_prompt(self, tmp_path):
        """System prompt includes <project_instructions> block."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("# Project Rules\nAlways use type hints.")

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            agents_md=str(agents_file),
        )

        assert "<project_instructions>" in agent._system_prompt
        assert "Always use type hints." in agent._system_prompt
        assert "</project_instructions>" in agent._system_prompt

    def test_no_agents_md_no_block(self):
        """Agent with agents_md=None has no <project_instructions> block."""
        agent = Agent(model_name="gpt-4.1", purpose="test")

        assert "<project_instructions>" not in agent._system_prompt

    def test_agents_md_coexists_with_skills(self, tmp_path):
        """AGENTS.md and skills both appear in system prompt."""
        # Create AGENTS.md
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Project instructions here.")

        # Create a skill
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        frontmatter = {"name": "my-skill", "description": "A test skill"}
        (skill_dir / "SKILL.md").write_text(
            f"---\n{yaml.dump(frontmatter)}---\nSkill body."
        )

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            agents_md=str(agents_file),
            skills=[str(skill_dir)],
        )

        assert "<project_instructions>" in agent._system_prompt
        assert "Project instructions here." in agent._system_prompt
        assert "<available_skills>" in agent._system_prompt
        assert "my-skill" in agent._system_prompt

    def test_project_instructions_before_skills(self, tmp_path):
        """<project_instructions> appears before <available_skills> in prompt."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Project instructions")

        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        frontmatter = {"name": "test-skill", "description": "Test"}
        (skill_dir / "SKILL.md").write_text(
            f"---\n{yaml.dump(frontmatter)}---\nBody."
        )

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            agents_md=str(agents_file),
            skills=[str(skill_dir)],
        )

        pi_pos = agent._system_prompt.index("<project_instructions>")
        as_pos = agent._system_prompt.index("<available_skills>")
        assert pi_pos < as_pos


class TestSurvivesConnectMcp:
    """Test that AGENTS.md content survives connect_mcp() prompt regeneration."""

    @pytest.mark.asyncio
    async def test_connect_mcp_preserves_agents_md(self, tmp_path):
        """AGENTS.md content survives connect_mcp() prompt regeneration."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Must survive MCP reconnect.")

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            agents_md=str(agents_file),
            mcp={"servers": [{"name": "test", "transport": "stdio", "command": "echo"}]},
        )

        # Before connect_mcp
        assert "<project_instructions>" in agent._system_prompt
        assert "Must survive MCP reconnect." in agent._system_prompt

        # Mock MCP connection
        mcp_tool_def = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "mcp_fake_tool",
                    "description": "A fake MCP tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            "implementation": lambda: "ok",
        }
        with patch(
            "tyler.mcp.config_loader._load_mcp_config",
            return_value=([mcp_tool_def], lambda: None),
        ), patch(
            "tyler.mcp.config_loader._validate_mcp_config",
        ):
            await agent.connect_mcp()

        # After connect_mcp: AGENTS.md STILL present
        assert "<project_instructions>" in agent._system_prompt
        assert "Must survive MCP reconnect." in agent._system_prompt


class TestYamlConfig:
    """Test agents_md configuration via YAML config files."""

    def test_agents_md_path_in_config(self, tmp_path):
        """Explicit agents_md path is resolved from config."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Config content")

        config_file = tmp_path / "config.yaml"
        config_data = {"name": "Agent", "agents_md": str(agents_file)}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert "agents_md" in result
        assert result["agents_md"] == str(agents_file)

    def test_agents_md_relative_path_in_config(self, tmp_path):
        """Relative agents_md path resolved relative to config directory."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Relative content")

        config_file = tmp_path / "config.yaml"
        config_data = {"agents_md": "./AGENTS.md"}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        resolved = Path(result["agents_md"])
        assert resolved.is_absolute()
        assert resolved.name == "AGENTS.md"

    def test_agents_md_list_in_config(self, tmp_path):
        """List of agents_md paths are all resolved."""
        file_a = tmp_path / "A.md"
        file_b = tmp_path / "B.md"
        file_a.write_text("A")
        file_b.write_text("B")

        config_file = tmp_path / "config.yaml"
        config_data = {"agents_md": ["./A.md", "./B.md"]}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert isinstance(result["agents_md"], list)
        assert len(result["agents_md"]) == 2
        assert all(Path(p).is_absolute() for p in result["agents_md"])

    def test_agents_md_bool_in_config(self, tmp_path):
        """Boolean agents_md passes through unchanged."""
        config_file = tmp_path / "config.yaml"
        config_data = {"agents_md": True}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert result["agents_md"] is True

    def test_agents_md_disabled_in_config(self, tmp_path):
        """agents_md=false in config passes through as False."""
        config_file = tmp_path / "config.yaml"
        config_data = {"agents_md": False}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert result["agents_md"] is False

    def test_config_without_agents_md(self, tmp_path):
        """Config without agents_md key works fine."""
        config_file = tmp_path / "config.yaml"
        config_data = {"name": "Agent"}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert "agents_md" not in result


class TestNoRegression:
    """Test that agents without agents_md work normally."""

    def test_agent_default_no_project_instructions(self):
        """Default agent has no <project_instructions> block."""
        agent = Agent(model_name="gpt-4.1", purpose="test")

        assert "<project_instructions>" not in agent._system_prompt

    def test_agent_with_agents_md_none(self):
        """Explicitly passing agents_md=None has no effect."""
        agent = Agent(model_name="gpt-4.1", purpose="test", agents_md=None)

        assert "<project_instructions>" not in agent._system_prompt

    def test_agent_with_agents_md_false(self):
        """Explicitly passing agents_md=False has no effect."""
        agent = Agent(model_name="gpt-4.1", purpose="test", agents_md=False)

        assert "<project_instructions>" not in agent._system_prompt

    def test_agent_with_tools_and_agents_md(self, tmp_path):
        """Tools work normally alongside agents_md."""
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Project rules.")

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            tools=["web"],
            agents_md=str(agents_file),
        )

        tool_names = {t["function"]["name"] for t in agent._processed_tools}
        assert any(n.startswith("web-") for n in tool_names)
        assert "<project_instructions>" in agent._system_prompt
        assert "Project rules." in agent._system_prompt
