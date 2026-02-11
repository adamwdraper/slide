"""Tests for Agent Skills support.

Tests cover skill loading, validation, activation, system prompt injection,
config loading, and no-regression scenarios.
"""
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from tyler import Agent
from tyler.models.skill import Skill, SkillManager
from tyler.utils.tool_runner import tool_runner
from tyler.config import load_config


@pytest.fixture(autouse=True)
def cleanup_activate_skill():
    """Clean up activate_skill from tool_runner after each test."""
    yield
    if "activate_skill" in tool_runner.tools:
        del tool_runner.tools["activate_skill"]
    # Also clean up tool attributes if present
    if "activate_skill" in tool_runner.tool_attributes:
        del tool_runner.tool_attributes["activate_skill"]


def _create_skill_dir(tmp_path, name="test-skill", description="A test skill", body="Do the thing.", extra_frontmatter=None):
    """Helper to create a skill directory with a SKILL.md file."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(exist_ok=True)
    frontmatter = {"name": name, "description": description}
    if extra_frontmatter:
        frontmatter.update(extra_frontmatter)
    content = f"---\n{yaml.dump(frontmatter)}---\n{body}"
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


class TestSkillLoading:
    """Test loading skills from directories."""

    def test_skill_loading_from_directory(self, tmp_path):
        """Valid SKILL.md is parsed correctly."""
        skill_dir = _create_skill_dir(
            tmp_path,
            name="pdf-processing",
            description="Process PDF files and extract text.",
            body="# Instructions\nUse pdfplumber to extract text.",
        )

        manager = SkillManager()
        skills, tool_defs = manager.load_skills([str(skill_dir)])

        assert len(skills) == 1
        skill = skills[0]
        assert skill.name == "pdf-processing"
        assert skill.description == "Process PDF files and extract text."
        assert "pdfplumber" in skill.content
        assert skill.path == skill_dir

    def test_skill_loading_multiple(self, tmp_path):
        """Multiple skills load correctly."""
        dir_a = _create_skill_dir(tmp_path, name="skill-a", description="First skill")
        dir_b = _create_skill_dir(tmp_path, name="skill-b", description="Second skill")

        manager = SkillManager()
        skills, tool_defs = manager.load_skills([str(dir_a), str(dir_b)])

        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"skill-a", "skill-b"}

    def test_skill_missing_skill_md(self, tmp_path):
        """Directory without SKILL.md is skipped with warning."""
        empty_dir = tmp_path / "no-skill"
        empty_dir.mkdir()

        manager = SkillManager()
        skills, tool_defs = manager.load_skills([str(empty_dir)])

        assert len(skills) == 0
        assert len(tool_defs) == 0

    def test_skill_extra_metadata(self, tmp_path):
        """Extra frontmatter fields are captured in metadata."""
        skill_dir = _create_skill_dir(
            tmp_path,
            name="with-meta",
            description="Has metadata",
            extra_frontmatter={"version": "1.0", "author": "test"},
        )

        manager = SkillManager()
        skills, _ = manager.load_skills([str(skill_dir)])

        assert skills[0].metadata == {"version": "1.0", "author": "test"}


class TestSkillValidation:
    """Test frontmatter validation per the Agent Skills spec."""

    def test_invalid_name_uppercase(self, tmp_path):
        """Name with uppercase letters is rejected."""
        skill_dir = _create_skill_dir(tmp_path, name="BadName", description="test")

        manager = SkillManager()
        with pytest.raises(ValueError, match="invalid"):
            manager.load_skills([str(skill_dir)])

    def test_invalid_name_spaces(self, tmp_path):
        """Name with spaces is rejected."""
        skill_dir = _create_skill_dir(tmp_path, name="bad name", description="test")

        manager = SkillManager()
        with pytest.raises(ValueError, match="invalid"):
            manager.load_skills([str(skill_dir)])

    def test_invalid_name_too_long(self, tmp_path):
        """Name exceeding 64 chars is rejected."""
        long_name = "a" * 65
        skill_dir = _create_skill_dir(tmp_path, name=long_name, description="test")

        manager = SkillManager()
        with pytest.raises(ValueError, match="exceeds"):
            manager.load_skills([str(skill_dir)])

    def test_invalid_description_too_long(self, tmp_path):
        """Description exceeding 1024 chars is rejected."""
        long_desc = "x" * 1025
        skill_dir = _create_skill_dir(tmp_path, name="valid-name", description=long_desc)

        manager = SkillManager()
        with pytest.raises(ValueError, match="exceeds"):
            manager.load_skills([str(skill_dir)])

    def test_missing_frontmatter_delimiters(self, tmp_path):
        """SKILL.md without --- delimiters raises error."""
        skill_dir = tmp_path / "bad-format"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here, just text.")

        manager = SkillManager()
        with pytest.raises(ValueError, match="frontmatter"):
            manager.load_skills([str(skill_dir)])

    def test_missing_name_in_frontmatter(self, tmp_path):
        """SKILL.md without name in frontmatter raises error."""
        skill_dir = tmp_path / "no-name"
        skill_dir.mkdir()
        content = "---\ndescription: Has description but no name\n---\nBody text"
        (skill_dir / "SKILL.md").write_text(content)

        manager = SkillManager()
        with pytest.raises(ValueError, match="missing 'name'"):
            manager.load_skills([str(skill_dir)])

    def test_missing_description_in_frontmatter(self, tmp_path):
        """SKILL.md without description in frontmatter raises error."""
        skill_dir = tmp_path / "no-desc"
        skill_dir.mkdir()
        content = "---\nname: no-desc\n---\nBody text"
        (skill_dir / "SKILL.md").write_text(content)

        manager = SkillManager()
        with pytest.raises(ValueError, match="missing 'description'"):
            manager.load_skills([str(skill_dir)])

    def test_valid_name_with_hyphens_and_numbers(self, tmp_path):
        """Name with hyphens and numbers is valid."""
        skill_dir = _create_skill_dir(tmp_path, name="my-skill-v2", description="Valid skill")

        manager = SkillManager()
        skills, _ = manager.load_skills([str(skill_dir)])
        assert skills[0].name == "my-skill-v2"


class TestActivateSkill:
    """Test the activate_skill tool implementation."""

    @pytest.mark.asyncio
    async def test_activate_skill_returns_content(self, tmp_path):
        """activate_skill tool returns the full SKILL.md body."""
        body = "# Step 1\nDo this.\n\n# Step 2\nDo that."
        skill_dir = _create_skill_dir(
            tmp_path, name="my-skill", description="A skill", body=body
        )

        manager = SkillManager()
        skills, tool_defs = manager.load_skills([str(skill_dir)])

        # Execute via tool_runner
        result = await tool_runner.run_tool_async("activate_skill", {"name": "my-skill"})
        assert result == body

    @pytest.mark.asyncio
    async def test_activate_skill_unknown_name(self, tmp_path):
        """activate_skill with unknown name returns helpful error."""
        skill_dir = _create_skill_dir(tmp_path, name="known-skill", description="Known")

        manager = SkillManager()
        manager.load_skills([str(skill_dir)])

        result = await tool_runner.run_tool_async("activate_skill", {"name": "unknown"})
        assert "Unknown skill" in result
        assert "known-skill" in result

    def test_activate_skill_tool_registered(self, tmp_path):
        """activate_skill is registered in the global tool_runner."""
        skill_dir = _create_skill_dir(tmp_path, name="reg-test", description="Test")

        manager = SkillManager()
        manager.load_skills([str(skill_dir)])

        assert "activate_skill" in tool_runner.tools

    def test_activate_skill_tool_attributes(self, tmp_path):
        """activate_skill has source='skills' attribute."""
        skill_dir = _create_skill_dir(tmp_path, name="attr-test", description="Test")

        manager = SkillManager()
        manager.load_skills([str(skill_dir)])

        attrs = tool_runner.get_tool_attributes("activate_skill")
        assert attrs == {"source": "skills"}

    def test_activate_skill_tool_definition(self, tmp_path):
        """activate_skill tool definition has correct shape."""
        skill_dir = _create_skill_dir(tmp_path, name="def-test", description="Test")

        manager = SkillManager()
        _, tool_defs = manager.load_skills([str(skill_dir)])

        assert len(tool_defs) == 1
        tool_def = tool_defs[0]
        assert tool_def["type"] == "function"
        assert tool_def["function"]["name"] == "activate_skill"
        assert "name" in tool_def["function"]["parameters"]["properties"]


class TestSkillsInSystemPrompt:
    """Test that skills metadata appears in the system prompt."""

    def test_skills_in_system_prompt(self, tmp_path):
        """System prompt includes available_skills block when skills configured."""
        skill_dir = _create_skill_dir(
            tmp_path,
            name="code-review",
            description="Review code for quality and bugs.",
        )

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            skills=[str(skill_dir)],
        )

        assert "<available_skills>" in agent._system_prompt
        assert "code-review" in agent._system_prompt
        assert "Review code for quality and bugs." in agent._system_prompt
        assert "activate_skill" in agent._system_prompt

    def test_multiple_skills_in_prompt(self, tmp_path):
        """Multiple skills listed in system prompt."""
        dir_a = _create_skill_dir(tmp_path, name="skill-a", description="First")
        dir_b = _create_skill_dir(tmp_path, name="skill-b", description="Second")

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            skills=[str(dir_a), str(dir_b)],
        )

        assert "skill-a" in agent._system_prompt
        assert "skill-b" in agent._system_prompt


class TestAgentWithNoSkills:
    """Test that agents without skills work normally (no regression)."""

    def test_agent_with_no_skills(self):
        """Agent with skills=[] has no skills in prompt."""
        agent = Agent(model_name="gpt-4.1", purpose="test")

        assert "<available_skills>" not in agent._system_prompt
        assert "activate_skill" not in agent._system_prompt

    def test_agent_with_empty_skills_list(self):
        """Explicitly passing skills=[] causes no issues."""
        agent = Agent(model_name="gpt-4.1", purpose="test", skills=[])

        assert len(agent._processed_tools) == 0
        assert "<available_skills>" not in agent._system_prompt

    def test_agent_with_tools_and_no_skills(self):
        """Tools work normally without skills."""
        agent = Agent(model_name="gpt-4.1", purpose="test", tools=["web"])

        assert len(agent._processed_tools) > 0
        assert "<available_skills>" not in agent._system_prompt

    def test_agent_with_tools_and_skills(self, tmp_path):
        """Tools and skills coexist."""
        skill_dir = _create_skill_dir(
            tmp_path, name="my-skill", description="A skill"
        )

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            tools=["web"],
            skills=[str(skill_dir)],
        )

        tool_names = {t["function"]["name"] for t in agent._processed_tools}
        assert "activate_skill" in tool_names
        # Web tools should also be present
        assert any(n.startswith("web-") for n in tool_names)
        assert "<available_skills>" in agent._system_prompt


class TestSkillsYamlConfig:
    """Test skills configuration via YAML config files."""

    def test_skills_in_config(self, tmp_path):
        """Skills paths are processed from YAML config."""
        # Create a skill directory
        skill_dir = _create_skill_dir(tmp_path, name="config-skill", description="From config")

        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "Agent",
            "skills": [str(skill_dir)],
        }
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert "skills" in result
        assert len(result["skills"]) == 1
        assert result["skills"][0] == str(skill_dir)

    def test_skills_relative_path_in_config(self, tmp_path):
        """Relative skill paths are resolved relative to config directory."""
        skill_dir = _create_skill_dir(tmp_path, name="rel-skill", description="Relative")

        config_file = tmp_path / "config.yaml"
        config_data = {"skills": ["./rel-skill"]}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        # Should be resolved to an absolute path
        resolved = Path(result["skills"][0])
        assert resolved.is_absolute()
        assert resolved.name == "rel-skill"

    def test_skills_home_path_in_config(self, tmp_path):
        """Home (~) skill paths are expanded."""
        config_file = tmp_path / "config.yaml"
        config_data = {"skills": ["~/my-skills/code-review"]}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        # Should be expanded (no ~ remaining)
        assert "~" not in result["skills"][0]

    def test_skills_absolute_path_in_config(self, tmp_path):
        """Absolute skill paths are passed through."""
        config_file = tmp_path / "config.yaml"
        config_data = {"skills": ["/opt/skills/code-review"]}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert result["skills"][0] == "/opt/skills/code-review"

    def test_config_without_skills(self, tmp_path):
        """Config without skills key works fine."""
        config_file = tmp_path / "config.yaml"
        config_data = {"name": "Agent"}
        config_file.write_text(yaml.dump(config_data))

        result = load_config(str(config_file))

        assert "skills" not in result


class TestToolNameCollision:
    """Test activate_skill tool name collision detection."""

    def test_collision_with_existing_tool(self, tmp_path):
        """Raises ValueError if activate_skill is already registered."""
        skill_dir = _create_skill_dir(tmp_path, name="collision-test", description="Test")

        # Pre-register a tool named activate_skill
        tool_runner.register_tool(
            name="activate_skill",
            implementation=lambda: "existing",
        )

        try:
            manager = SkillManager()
            with pytest.raises(ValueError, match="already registered"):
                manager.load_skills([str(skill_dir)])
        finally:
            # Clean up the pre-registered tool
            if "activate_skill" in tool_runner.tools:
                del tool_runner.tools["activate_skill"]


class TestSkillsSurviveConnectMcp:
    """Test that skills are preserved when connect_mcp() regenerates the system prompt."""

    @pytest.mark.asyncio
    async def test_connect_mcp_preserves_skills_in_prompt(self, tmp_path):
        """Skills description and tool defs survive connect_mcp() prompt regeneration."""
        skill_dir = _create_skill_dir(
            tmp_path, name="mcp-test-skill", description="Skill that must survive MCP"
        )

        agent = Agent(
            model_name="gpt-4.1",
            purpose="test",
            skills=[str(skill_dir)],
            mcp={"servers": [{"name": "test", "transport": "stdio", "command": "echo"}]},
        )

        # Before connect_mcp: skills present
        assert "<available_skills>" in agent._system_prompt
        assert "mcp-test-skill" in agent._system_prompt
        tool_names_before = {t["function"]["name"] for t in agent._processed_tools}
        assert "activate_skill" in tool_names_before

        # Mock MCP connection to add a fake tool
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

        # After connect_mcp: skills STILL present
        assert "<available_skills>" in agent._system_prompt
        assert "mcp-test-skill" in agent._system_prompt
        assert "Skill that must survive MCP" in agent._system_prompt
        tool_names_after = {t["function"]["name"] for t in agent._processed_tools}
        assert "activate_skill" in tool_names_after
