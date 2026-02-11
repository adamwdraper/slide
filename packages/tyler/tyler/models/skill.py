"""Skill model and manager for Agent Skills support.

Implements the Agent Skills open format (https://agentskills.io/specification).
Skills are directories containing a SKILL.md file with YAML frontmatter
(name, description) and markdown instructions. Skills are progressively
disclosed - only metadata appears in the system prompt, and full instructions
are loaded on-demand via the activate_skill tool.
"""
import re
import yaml
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from tyler.utils.tool_runner import tool_runner

logger = logging.getLogger(__name__)

# Validation constraints per the Agent Skills spec
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]*$')


@dataclass
class Skill:
    """Represents a loaded skill from a SKILL.md file."""
    name: str
    description: str
    path: Path
    content: str
    metadata: dict = field(default_factory=dict)


class SkillManager:
    """Manages skill discovery, loading, and tool registration."""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def load_skills(self, skill_paths: List[str]) -> Tuple[List[Skill], List[Dict]]:
        """Load skills from directories and register the activate_skill tool.

        Args:
            skill_paths: List of paths to skill directories containing SKILL.md files.

        Returns:
            Tuple of (loaded skills list, tool definitions for _processed_tools).

        Raises:
            ValueError: If a skill has invalid name/description or if activate_skill
                        tool name conflicts with an existing tool.
        """
        skills = []
        for path_str in skill_paths:
            path = Path(path_str).expanduser().resolve()
            skill_md = path / "SKILL.md"

            if not skill_md.exists():
                logger.warning(f"No SKILL.md found in {path}, skipping")
                continue

            skill = self._parse_skill(skill_md, path)
            self._validate_skill(skill)
            skills.append(skill)
            self._skills[skill.name] = skill

        if not skills:
            return [], []

        # Check for tool name collision before registering
        if "activate_skill" in tool_runner.tools:
            raise ValueError(
                "Cannot register skill tools: a tool named 'activate_skill' is already "
                "registered. Please rename your tool to avoid collision."
            )

        # Build the activate_skill tool
        tool_def = self._build_activate_skill_definition()
        implementation = self._build_activate_skill_implementation()

        tool_runner.register_tool(
            name="activate_skill",
            implementation=implementation,
            definition=tool_def["function"],
        )

        # Register tool attributes
        tool_runner.register_tool_attributes(
            "activate_skill", {"source": "skills"}
        )

        tool_definitions = [tool_def]
        return skills, tool_definitions

    def _parse_skill(self, skill_md: Path, directory: Path) -> Skill:
        """Parse a SKILL.md file into a Skill object."""
        raw = skill_md.read_text(encoding="utf-8")

        # Split on --- markers to extract YAML frontmatter
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise ValueError(
                f"SKILL.md in {directory} is missing YAML frontmatter "
                f"(expected --- delimiters)"
            )

        frontmatter_str = parts[1].strip()
        body = parts[2].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML frontmatter in {skill_md}: {e}"
            )

        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name:
            raise ValueError(f"SKILL.md in {directory} is missing 'name' in frontmatter")
        if not description:
            raise ValueError(f"SKILL.md in {directory} is missing 'description' in frontmatter")

        # Extract remaining metadata (everything except name/description)
        metadata = {k: v for k, v in frontmatter.items() if k not in ("name", "description")}

        return Skill(
            name=name,
            description=description,
            path=directory,
            content=body,
            metadata=metadata,
        )

    def _validate_skill(self, skill: Skill) -> None:
        """Validate skill name and description per the Agent Skills spec."""
        if not NAME_PATTERN.match(skill.name):
            raise ValueError(
                f"Skill name '{skill.name}' is invalid. Must be lowercase letters, "
                f"numbers, and hyphens, starting with a letter or number."
            )
        if len(skill.name) > MAX_NAME_LENGTH:
            raise ValueError(
                f"Skill name '{skill.name}' exceeds {MAX_NAME_LENGTH} characters."
            )
        if len(skill.description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"Skill description for '{skill.name}' exceeds "
                f"{MAX_DESCRIPTION_LENGTH} characters."
            )

    def _build_activate_skill_definition(self) -> Dict:
        """Build the OpenAI-compatible tool definition for activate_skill."""
        available = ", ".join(sorted(self._skills.keys()))
        return {
            "type": "function",
            "function": {
                "name": "activate_skill",
                "description": (
                    "Activate a skill to load its full instructions. "
                    "Use when a task matches an available skill."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": f"The name of the skill to activate. Available: {available}",
                        }
                    },
                    "required": ["name"],
                },
            },
        }

    def _build_activate_skill_implementation(self):
        """Build the activate_skill tool implementation function."""
        skills = self._skills

        async def activate_skill(name: str) -> str:
            """Load and return the full instructions for a skill."""
            skill = skills.get(name)
            if skill is None:
                available = ", ".join(sorted(skills.keys()))
                return f"Unknown skill '{name}'. Available skills: {available}"
            return skill.content

        return activate_skill

    def format_skills_prompt(self, skills: List[Skill]) -> str:
        """Format the skills metadata block for system prompt injection.

        Args:
            skills: List of loaded Skill objects.

        Returns:
            Formatted string for inclusion in the system prompt.
        """
        lines = []
        for skill in skills:
            lines.append(f"- `{skill.name}`: {skill.description}")
        return "\n".join(lines)
