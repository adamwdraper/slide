"""
Common Slack bot patterns for space-monkey.

This module provides pre-configured patterns for common types of Slack bots.
"""

from typing import Dict, List, Optional
from . import TemplateManager


class SlackBotPatterns:
    """Pre-configured patterns for common Slack bot types."""
    
    def __init__(self):
        self.template_manager = TemplateManager()
    
    def hr_bot(self, agent_name: str = "HRAssistant", **kwargs) -> Dict[str, str]:
        """
        Generate an HR bot following the Perci pattern.
        
        Args:
            agent_name: Name of the HR agent
            **kwargs: Additional options to override defaults
            
        Returns:
            Dictionary of generated files
        """
        defaults = {
            "description": "Answering employee HR questions via Slack channels and DMs",
            "tools": ["notion:notion-search"],
            "sub_agents": ["NotionPageReader", "MessageClassifier"],
            "bot_user_id": True,
            "citations_required": True,
            "specific_guidelines": "Use 'people team' instead of 'HR' in responses. Always search Notion for the most up-to-date information."
        }
        defaults.update(kwargs)
        
        return self.template_manager.generate_agent(agent_name=agent_name, **defaults)
    
    def customer_support_bot(self, agent_name: str = "SupportBot", **kwargs) -> Dict[str, str]:
        """
        Generate a customer support bot.
        
        Args:
            agent_name: Name of the support agent
            **kwargs: Additional options to override defaults
            
        Returns:
            Dictionary of generated files
        """
        defaults = {
            "description": "Providing customer support through Slack channels and DMs",
            "tools": [
                "notion:notion-search",  # For knowledge base
                "slack:send-message",    # For communication
                "zendesk:create-ticket"  # For escalation
            ],
            "sub_agents": ["TicketClassifier", "KnowledgeSearcher"],
            "bot_user_id": True,
            "citations_required": True,
            "specific_guidelines": "Escalate complex issues to human support agents. Always provide helpful and empathetic responses."
        }
        defaults.update(kwargs)
        
        return self.template_manager.generate_agent(agent_name=agent_name, **defaults)
    
    def knowledge_bot(self, agent_name: str = "KnowledgeBot", **kwargs) -> Dict[str, str]:
        """
        Generate a knowledge base bot for answering questions.
        
        Args:
            agent_name: Name of the knowledge agent
            **kwargs: Additional options to override defaults
            
        Returns:
            Dictionary of generated files
        """
        defaults = {
            "description": "Answering questions using company knowledge base and documentation",
            "tools": [
                "notion:notion-search",
                "confluence:search",
                "web:search"
            ],
            "sub_agents": ["DocumentReader", "SourceValidator"],
            "bot_user_id": True,
            "citations_required": True,
            "specific_guidelines": "Always provide sources for information. If uncertain, direct users to authoritative documentation."
        }
        defaults.update(kwargs)
        
        return self.template_manager.generate_agent(agent_name=agent_name, **defaults)
    
    def project_bot(self, agent_name: str = "ProjectBot", **kwargs) -> Dict[str, str]:
        """
        Generate a project management bot.
        
        Args:
            agent_name: Name of the project agent
            **kwargs: Additional options to override defaults
            
        Returns:
            Dictionary of generated files
        """
        defaults = {
            "description": "Managing project updates, tasks, and team coordination via Slack",
            "tools": [
                "jira:search-issues",
                "slack:send-message",
                "notion:notion-search"
            ],
            "sub_agents": ["TaskClassifier", "StatusUpdater"],
            "bot_user_id": True,
            "citations_required": False,
            "specific_guidelines": "Keep updates concise and actionable. Use threads for detailed discussions."
        }
        defaults.update(kwargs)
        
        return self.template_manager.generate_agent(agent_name=agent_name, **defaults)
    
    def message_classifier(self, agent_name: str = "MessageClassifier", **kwargs) -> Dict[str, str]:
        """
        Generate a message classifier agent.
        
        Args:
            agent_name: Name of the classifier agent
            **kwargs: Additional options to override defaults
            
        Returns:
            Dictionary of generated files
        """
        defaults = {
            "description": "Classifying Slack messages to determine response type (ignore, emoji, or full response)",
            "tools": [],  # Classifiers typically don't need external tools
            "sub_agents": [],
            "bot_user_id": True,
            "citations_required": False,
            "specific_guidelines": "Return JSON with response_type, suggested_emoji, confidence, and reasoning. Be conservative about when to respond."
        }
        defaults.update(kwargs)
        
        return self.template_manager.generate_agent(agent_name=agent_name, **defaults)
    
    def document_reader(self, agent_name: str = "DocumentReader", **kwargs) -> Dict[str, str]:
        """
        Generate a document reader agent for analyzing content.
        
        Args:
            agent_name: Name of the document reader agent
            **kwargs: Additional options to override defaults
            
        Returns:
            Dictionary of generated files
        """
        defaults = {
            "description": "Reading and analyzing documents to extract relevant information",
            "tools": [
                "notion:read-page",
                "pdf:extract-text",
                "web:scrape"
            ],
            "sub_agents": [],
            "bot_user_id": False,  # Usually a sub-agent
            "citations_required": True,
            "specific_guidelines": "Focus on extracting the most relevant information. Provide clear summaries and cite sources."
        }
        defaults.update(kwargs)
        
        return self.template_manager.generate_agent(agent_name=agent_name, **defaults)
    
    def multi_agent_system(self, 
                          main_agent_name: str = "MainAgent",
                          system_purpose: str = "coordinating specialized agents",
                          sub_agent_patterns: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
        """
        Generate a complete multi-agent system.
        
        Args:
            main_agent_name: Name of the main orchestrator agent
            system_purpose: Purpose of the overall system
            sub_agent_patterns: List of patterns to include as sub-agents
            
        Returns:
            Dictionary mapping agent names to their generated files
        """
        if sub_agent_patterns is None:
            sub_agent_patterns = ["message_classifier", "document_reader"]
        
        system = {}
        sub_agent_names = []
        
        # Generate sub-agents first
        for pattern in sub_agent_patterns:
            if hasattr(self, pattern):
                pattern_method = getattr(self, pattern)
                agent_name = f"{pattern.title().replace('_', '')}"
                sub_agent_names.append(agent_name)
                system[agent_name] = pattern_method(agent_name=agent_name)
        
        # Generate main agent
        main_files = self.template_manager.generate_agent(
            agent_name=main_agent_name,
            description=system_purpose,
            tools=["slack:send-message"],
            sub_agents=sub_agent_names,
            bot_user_id=True,
            citations_required=False,
            specific_guidelines="Coordinate with sub-agents to provide comprehensive responses."
        )
        
        system[main_agent_name] = main_files
        
        return system


# Convenience functions for CLI integration
def get_pattern_names() -> List[str]:
    """Get list of available pattern names."""
    return [
        "hr_bot",
        "customer_support_bot", 
        "knowledge_bot",
        "project_bot",
        "message_classifier",
        "document_reader"
    ]


def generate_pattern(pattern_name: str, agent_name: str, **kwargs) -> Dict[str, str]:
    """
    Generate an agent using a predefined pattern.
    
    Args:
        pattern_name: Name of the pattern to use
        agent_name: Name for the generated agent
        **kwargs: Additional options
        
    Returns:
        Dictionary of generated files
        
    Raises:
        ValueError: If pattern_name is not recognized
    """
    patterns = SlackBotPatterns()
    
    if not hasattr(patterns, pattern_name):
        available = get_pattern_names()
        raise ValueError(f"Unknown pattern '{pattern_name}'. Available: {available}")
    
    pattern_method = getattr(patterns, pattern_name)
    return pattern_method(agent_name=agent_name, **kwargs) 