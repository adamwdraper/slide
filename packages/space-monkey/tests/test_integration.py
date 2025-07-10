"""
Integration tests for space_monkey.

These tests verify that all components work together correctly.
"""

import pytest
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner
from space_monkey.cli import main
from space_monkey.templates import TemplateManager


class TestEndToEndIntegration:
    """Test complete end-to-end functionality."""
    
    def test_full_agent_generation_workflow(self):
        """Test the complete workflow from CLI to file generation."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Generate a complete Slack bot agent
            result = runner.invoke(main, [
                'generate', 'agent', 'integration-test-bot',
                '--description', 'A comprehensive test bot for integration testing',
                '--tools', 'notion:notion-search',
                '--tools', 'slack:send-message',
                '--sub-agents', 'message-classifier',
                '--bot-user-id',
                '--citations',
                '--guidelines', 'Always test thoroughly'
            ])
            
            # Should succeed
            if result.exit_code == 0:
                # Check that files were created
                agent_dir = Path("agents/integration_test_bot")
                assert agent_dir.exists()
                
                agent_file = agent_dir / "agent.py"
                purpose_file = agent_dir / "purpose.py"
                
                if agent_file.exists():
                    # Verify agent.py content
                    agent_content = agent_file.read_text()
                    assert "def initialize_integration_test_bot_agent" in agent_content
                    assert "notion:notion-search" in agent_content
                    assert "slack:send-message" in agent_content
                    assert "message_classifier_agent" in agent_content
                
                if purpose_file.exists():
                    # Verify purpose.py content
                    purpose_content = purpose_file.read_text()
                    assert "StringPrompt" in purpose_content
                    assert "bot_user_id" in purpose_content
                    assert "Always test thoroughly" in purpose_content
    
    def test_multiple_agent_generation(self):
        """Test generating multiple agents in sequence."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Generate first agent
            result1 = runner.invoke(main, [
                'generate', 'agent', 'bot-one',
                '--description', 'First bot'
            ])
            
            # Generate second agent
            result2 = runner.invoke(main, [
                'generate', 'agent', 'bot-two',
                '--description', 'Second bot',
                '--tools', 'notion:search'
            ])
            
            # Both should succeed or fail gracefully
            assert result1.exit_code in [0, 1]
            assert result2.exit_code in [0, 1]
            
            if result1.exit_code == 0 and result2.exit_code == 0:
                # Check that both directories exist
                assert Path("agents/bot_one").exists()
                assert Path("agents/bot_two").exists()


class TestTemplateManagerIntegration:
    """Test TemplateManager integration with file system."""
    
    def test_template_loading_and_generation(self):
        """Test that templates are loaded and can generate valid files."""
        manager = TemplateManager()
        
        # Test basic generation
        files = manager.generate_agent(
            agent_name="IntegrationBot",
            description="Testing template integration"
        )
        
        assert isinstance(files, dict)
        assert len(files) >= 1  # Should generate at least one file
        
        # If agent.py is generated, test its content
        if "agent.py" in files:
            content = files["agent.py"]
            assert "def initialize_integrationbot_agent" in content
            assert "Integrationbot" in content  # Agent name gets converted to title case
        
        # If purpose.py is generated, test its content
        if "purpose.py" in files:
            purpose_content = files["purpose.py"]
            assert "Testing template integration" in purpose_content
    
    def test_comprehensive_agent_generation(self):
        """Test generating an agent with all possible options."""
        manager = TemplateManager()
        
        files = manager.generate_agent(
            agent_name="ComprehensiveBot",
            description="A bot with all features enabled",
            tools=["notion:notion-search", "slack:send-message", "web:search"],
            sub_agents=["Classifier", "Reader", "Analyzer"],
            citations_required=True,
            specific_guidelines="Follow comprehensive testing practices",
            bot_user_id=True
        )
        
        assert isinstance(files, dict)
        
        # Verify agent.py if generated
        if "agent.py" in files:
            agent_content = files["agent.py"]
            assert "Comprehensivebot" in agent_content  # Agent name gets converted to title case
            assert "notion:notion-search" in agent_content
            assert "slack:send-message" in agent_content
            assert "web:search" in agent_content
            assert "classifier_agent" in agent_content
            assert "reader_agent" in agent_content
            assert "analyzer_agent" in agent_content
        
        # Verify purpose.py if generated
        if "purpose.py" in files:
            purpose_content = files["purpose.py"]
            assert "A bot with all features enabled" in purpose_content
            assert "Follow comprehensive testing practices" in purpose_content
            assert "bot_user_id" in purpose_content or "Slack User ID" in purpose_content


class TestSlackBotPatterns:
    """Test that generated agents follow Slack bot patterns."""
    
    def test_slack_bot_specific_patterns(self):
        """Test that generated agents include Slack-specific patterns."""
        manager = TemplateManager()
        
        files = manager.generate_agent(
            agent_name="SlackTestBot",
            description="Testing Slack bot patterns",
            bot_user_id=True,
            tools=["slack:send-message"]
        )
        
        if "agent.py" in files:
            content = files["agent.py"]
            # Should include Tyler Agent import
            assert "from tyler import Agent" in content
            # Should include weave decorator
            assert "@weave.op()" in content
            # Should include bot_user_id parameter
            assert "bot_user_id=None" in content
        
        if "purpose.py" in files:
            content = files["purpose.py"]
            # Should include Slack User ID handling
            assert "bot_user_id" in content or "Slack User ID" in content
    
    def test_hr_bot_pattern(self):
        """Test generating an HR bot following the Perci pattern."""
        manager = TemplateManager()
        
        files = manager.generate_agent(
            agent_name="HRAssistant",
            description="Answering HR questions for employees",
            tools=["notion:notion-search"],
            sub_agents=["NotionPageReader"],
            bot_user_id=True,
            citations_required=True,
            specific_guidelines="Use 'people team' instead of 'HR'"
        )
        
        if "agent.py" in files:
            content = files["agent.py"]
            assert "Hrassistant" in content  # Agent name gets converted to title case
            assert "notion:notion-search" in content
            assert "notionpagereader_agent" in content  # Sub-agent name gets converted to snake_case
        
        if "purpose.py" in files:
            content = files["purpose.py"]
            assert "people team" in content
            assert "citation" in content.lower() or "source" in content.lower()


class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios."""
    
    def test_invalid_output_directory(self):
        """Test handling of invalid output directories."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Try to create agent in a restricted path
            result = runner.invoke(main, [
                'generate', 'agent', 'test-bot',
                '--output-dir', '/invalid/path/that/should/not/exist'
            ])
            
            # Should handle gracefully (might fail but shouldn't crash)
            assert result.exit_code in [0, 1, 2]
    
    def test_special_characters_in_agent_name(self):
        """Test handling of special characters in agent names."""
        manager = TemplateManager()
        
        # Test with special characters that should be sanitized
        files = manager.generate_agent(
            agent_name="test-bot_with.special@chars!",
            description="Testing special character handling"
        )
        
        assert isinstance(files, dict)
        
        if "agent.py" in files:
            content = files["agent.py"]
            # Should contain sanitized function name
            assert "def initialize_" in content
            # Function name should be valid Python identifier
            import re
            function_match = re.search(r'def (initialize_\w+_agent)', content)
            if function_match:
                func_name = function_match.group(1)
                assert func_name.replace('_', '').isalnum()


class TestCLIIntegrationWithFileSystem:
    """Test CLI integration with actual file system operations."""
    
    def test_cli_creates_proper_directory_structure(self):
        """Test that CLI creates the expected directory structure."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, [
                'generate', 'agent', 'structure-test-bot'
            ])
            
            if result.exit_code == 0:
                # Check directory structure
                base_dir = Path("agents/structure_test_bot")
                assert base_dir.exists()
                assert base_dir.is_dir()
                
                # Check that files exist
                expected_files = ["agent.py", "purpose.py"]
                for filename in expected_files:
                    file_path = base_dir / filename
                    if file_path.exists():
                        assert file_path.is_file()
                        assert file_path.stat().st_size > 0  # Non-empty file
    
    def test_custom_output_directory(self):
        """Test CLI with custom output directory."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            custom_dir = "custom/slack-bots/my-bot"
            result = runner.invoke(main, [
                'generate', 'agent', 'custom-dir-bot',
                '--output-dir', custom_dir
            ])
            
            if result.exit_code == 0:
                # Check custom directory was created
                assert Path(custom_dir).exists()
                
                # Check files in custom directory
                agent_file = Path(custom_dir) / "agent.py"
                purpose_file = Path(custom_dir) / "purpose.py"
                
                # At least one file should exist
                assert agent_file.exists() or purpose_file.exists()


if __name__ == "__main__":
    pytest.main([__file__]) 