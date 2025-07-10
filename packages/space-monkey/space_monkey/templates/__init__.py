"""
Template system for generating agent code.
"""

from typing import Dict, List, Optional
import os
from pathlib import Path

__all__ = ["AgentTemplate", "TemplateManager"]


class AgentTemplate:
    """Represents a template for generating agent code."""
    
    def __init__(self, name: str, content: str):
        self.name = name
        self.content = content
    
    def render(self, **kwargs) -> str:
        """Render the template with the given variables."""
        # Simple string formatting for now
        return self.content.format(**kwargs)


class TemplateManager:
    """Manages agent templates and generation."""
    
    def __init__(self):
        self.template_dir = Path(__file__).parent
        self._templates = {}
        self._load_templates()
    
    @property
    def templates(self):
        """Backwards compatibility property."""
        return self._templates
    
    def _load_templates(self):
        """Load templates from the template directory."""
        # Load agent.py template
        agent_template_path = self.template_dir / "agent.py.template"
        if agent_template_path.exists():
            self._templates["agent.py"] = AgentTemplate(
                "agent.py", 
                agent_template_path.read_text()
            )
        
        # Load purpose.py template
        purpose_template_path = self.template_dir / "purpose.py.template"
        if purpose_template_path.exists():
            self._templates["purpose.py"] = AgentTemplate(
                "purpose.py",
                purpose_template_path.read_text()
            )
    
    def get_template(self, name: str) -> AgentTemplate:
        """Get a template by name."""
        return self._templates.get(name)
    
    def generate_agent(self, 
                      agent_name: str,
                      description: str = "",
                      tools: Optional[List[str]] = None,
                      sub_agents: Optional[List[str]] = None,
                      bot_user_id: bool = False,
                      citations_required: bool = False,
                      specific_guidelines: str = "",
                      output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generate an agent with the specified configuration.
        
        Args:
            agent_name: Name of the agent
            description: Description of what the agent does
            tools: List of tools the agent uses
            sub_agents: List of sub-agents this agent uses
            bot_user_id: Whether the agent needs bot user ID
            citations_required: Whether citations are required
            specific_guidelines: Specific guidelines for the agent
            output_dir: Output directory (if None, returns content dict)
            
        Returns:
            Dictionary mapping filenames to their content
        """
        if tools is None:
            tools = []
        if sub_agents is None:
            sub_agents = []
        
        # Prepare template variables
        template_vars = {
            "agent_name": agent_name,
            "agent_name_lower": self._to_safe_name(agent_name),
            "description": description,
            "tools": tools,
            "sub_agents": sub_agents,
            "bot_user_id": bot_user_id,
            "citations_required": citations_required,
            "specific_guidelines": specific_guidelines,
            "tools_formatted": self._format_tools(tools),
            "sub_agents_formatted": self._format_sub_agents(sub_agents),
            "sub_agents_snake_case": [self._to_snake_case(name) for name in sub_agents],
            "bot_user_id_section": self._format_bot_user_id_section(bot_user_id),
            "tool_notes_section": self._format_tool_notes_section(tools),
            "specific_guidelines_section": self._format_specific_guidelines_section(specific_guidelines),
            "citations_section": self._format_citations_section(citations_required)
        }
        
        # Generate files
        files = {}
        
        # Generate agent.py
        agent_template = self.get_template("agent.py")
        if agent_template:
            files["agent.py"] = agent_template.render(**template_vars)
        
        # Generate purpose.py
        purpose_template = self.get_template("purpose.py")
        if purpose_template:
            files["purpose.py"] = purpose_template.render(**template_vars)
        
        # If output_dir is specified, write files
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            for filename, content in files.items():
                file_path = output_path / filename
                file_path.write_text(content)
        
        return files
    
    def _to_safe_name(self, name: str) -> str:
        """Convert name to a safe variable name."""
        return name.lower().replace("-", "_").replace(" ", "_")
    
    def _format_tools(self, tools: List[str]) -> str:
        """Format tools for template rendering."""
        if not tools:
            return "# No tools specified"
        
        formatted = []
        for tool in tools:
            if ":" in tool:
                tool_type, tool_name = tool.split(":", 1)
                formatted.append(f'    # {tool_type.title()}: {tool_name}')
            else:
                formatted.append(f'    # {tool}')
        
        return "\n".join(formatted)
    
    def _format_sub_agents(self, sub_agents: List[str]) -> str:
        """Format sub-agents for template rendering."""
        if not sub_agents:
            return "# No sub-agents specified"
        
        formatted = []
        for agent in sub_agents:
            formatted.append(f'    # Sub-agent: {agent}')
        
        return "\n".join(formatted)
    
    def _format_bot_user_id_section(self, bot_user_id: bool) -> str:
        """Format bot user ID section for purpose template."""
        if bot_user_id:
            return "Your Slack User ID is: {bot_user_id}. Any message that contains (<@{bot_user_id}>) is a direct @mention of You."
        return ""
    
    def _format_tool_notes_section(self, tools: List[str]) -> str:
        """Format tool notes section for purpose template."""
        if not tools:
            return ""
        
        notes = ["<tool_specific_notes>", "# Notes on Tools"]
        for tool in tools:
            if ":" in tool:
                tool_type, tool_name = tool.split(":", 1)
                notes.append(f"- {tool_type.title()}: {tool_name}")
                notes.append(f"  - Add specific notes about how to use this tool effectively")
            else:
                notes.append(f"- {tool}")
                notes.append(f"  - Add specific notes about how to use this tool effectively")
        notes.append("</tool_specific_notes>")
        
        return "\n".join(notes)
    
    def _format_specific_guidelines_section(self, specific_guidelines: str) -> str:
        """Format specific guidelines section for purpose template."""
        if specific_guidelines:
            return f"- {specific_guidelines}"
        return ""
    
    def _format_citations_section(self, citations_required: bool) -> str:
        """Format citations section for purpose template."""
        if citations_required:
            return """<critical_requirement_citation>
# CRITICAL REQUIREMENT: Citations
EVERY response MUST end by citing the sources in the following format exactly (note the blank line before "Sources:"):

Sources:
[Source Name](source_url)
</critical_requirement_citation>"""
        return ""
    
    def _to_snake_case(self, name: str) -> str:
        """Convert a name to snake_case."""
        import re
        # Insert underscores before uppercase letters
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        # Handle sequences of uppercase letters
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower() + "_agent"
