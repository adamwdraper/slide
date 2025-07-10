"""
Tests for the CLI functionality in space_monkey.
"""

import pytest
import sys
from io import StringIO
from unittest.mock import patch, MagicMock
from pathlib import Path

from space_monkey.cli import main, handle_status, handle_generate_agent


class TestCLIBasics:
    """Test basic CLI functionality."""
    
    def test_main_command_help(self):
        """Test the main command shows help."""
        with patch('sys.argv', ['space-monkey', '--help']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    main()
                output = mock_stdout.getvalue()
                assert "Space Monkey" in output
                assert "Slack bots" in output
    
    def test_main_command_version(self):
        """Test the main command shows version."""
        with patch('sys.argv', ['space-monkey', '--version']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    main()
                output = mock_stdout.getvalue()
                assert "space-monkey 0.1.0" in output
    
    def test_status_command(self):
        """Test the status command."""
        with patch('sys.argv', ['space-monkey', 'status']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with patch('space_monkey.cli.handle_status') as mock_handle:
                    main()
                    mock_handle.assert_called_once()
    
    def test_generate_command_help(self):
        """Test the generate command shows help."""
        with patch('sys.argv', ['space-monkey', 'generate', '--help']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    main()
                output = mock_stdout.getvalue()
                assert "agent" in output


class TestAgentGenerationCLI:
    """Test agent generation CLI commands."""
    
    def test_agent_command_help(self):
        """Test the agent generation command shows help."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', '--help']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    main()
                output = mock_stdout.getvalue()
                assert "Name of the agent to generate" in output
                assert "--description" in output
                assert "--tools" in output
                assert "--bot-user-id" in output
    
    def test_agent_generation_basic(self):
        """Test basic agent generation."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'test-bot']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'test-bot'
    
    def test_agent_generation_with_description(self):
        """Test agent generation with description."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'hr-bot', '--description', 'An HR assistant for Slack']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'hr-bot'
                assert args.description == 'An HR assistant for Slack'
    
    def test_agent_generation_with_tools(self):
        """Test agent generation with tools."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'tool-bot', '--tools', 'notion:notion-search', '--tools', 'slack:send-message']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'tool-bot'
                assert args.tools == ['notion:notion-search', 'slack:send-message']
    
    def test_agent_generation_with_sub_agents(self):
        """Test agent generation with sub-agents."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'main-bot', '--sub-agents', 'classifier', '--sub-agents', 'reader']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'main-bot'
                assert args.sub_agents == ['classifier', 'reader']
    
    def test_agent_generation_with_bot_user_id(self):
        """Test agent generation with bot user ID."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'slack-bot', '--bot-user-id']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'slack-bot'
                assert args.bot_user_id is True
    
    def test_agent_generation_with_citations(self):
        """Test agent generation with citations."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'info-bot', '--citations']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'info-bot'
                assert args.citations is True
    
    def test_agent_generation_with_guidelines(self):
        """Test agent generation with guidelines."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'guided-bot', '--guidelines', 'Always be polite and helpful']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'guided-bot'
                assert args.guidelines == 'Always be polite and helpful'
    
    def test_agent_generation_with_output_dir(self):
        """Test agent generation with custom output directory."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'custom-bot', '--output-dir', './custom/bots/custom-bot']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'custom-bot'
                assert args.output_dir == './custom/bots/custom-bot'
    
    def test_agent_generation_with_pattern(self):
        """Test agent generation with pattern."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'hr-bot', '--pattern', 'hr_bot']):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'hr-bot'
                assert args.pattern == 'hr_bot'
    
    def test_agent_generation_all_options(self):
        """Test agent generation with all options."""
        with patch('sys.argv', [
            'space-monkey', 'generate', 'agent', 'full-featured-bot',
            '--description', 'A full-featured Slack bot',
            '--tools', 'notion:notion-search',
            '--tools', 'slack:send-message',
            '--sub-agents', 'classifier',
            '--sub-agents', 'reader',
            '--bot-user-id',
            '--citations',
            '--guidelines', 'Be helpful and professional',
            '--output-dir', './bots/full-featured'
        ]):
            with patch('space_monkey.cli.handle_generate_agent') as mock_handle:
                main()
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.name == 'full-featured-bot'
                assert args.description == 'A full-featured Slack bot'
                assert args.tools == ['notion:notion-search', 'slack:send-message']
                assert args.sub_agents == ['classifier', 'reader']
                assert args.bot_user_id is True
                assert args.citations is True
                assert args.guidelines == 'Be helpful and professional'
                assert args.output_dir == './bots/full-featured'


class TestCLIErrorHandling:
    """Test CLI error handling."""
    
    def test_missing_agent_name(self):
        """Test error when agent name is missing."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent']):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit):
                    main()
                error_output = mock_stderr.getvalue()
                assert "required" in error_output or "argument" in error_output
    
    def test_invalid_pattern(self):
        """Test error when invalid pattern is provided."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', 'test-bot', '--pattern', 'invalid_pattern']):
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit):
                    main()
                error_output = mock_stderr.getvalue()
                assert "invalid choice" in error_output
    
    def test_no_command_provided(self):
        """Test behavior when no command is provided."""
        with patch('sys.argv', ['space-monkey']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()
                assert "Space Monkey" in output


class TestCLIOutputFormatting:
    """Test CLI output formatting."""
    
    def test_status_message_format(self):
        """Test that status messages are properly formatted."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            handle_status()
            output = mock_stdout.getvalue()
            assert "🐒 Space Monkey Status" in output
            assert "Ready for Slack bot agent generation" in output
            assert "Available commands:" in output
    
    def test_help_message_formatting(self):
        """Test that help messages mention Slack-specific features."""
        with patch('sys.argv', ['space-monkey', 'generate', 'agent', '--help']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit):
                    main()
                output = mock_stdout.getvalue()
                assert "--bot-user-id" in output
                assert "--citations" in output


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    def test_cli_imports_correctly(self):
        """Test that all CLI components import without errors."""
        from space_monkey.cli import main, handle_status, handle_generate_agent
        
        assert main is not None
        assert handle_status is not None
        assert handle_generate_agent is not None
    
    def test_cli_module_structure(self):
        """Test that CLI module has expected structure."""
        import space_monkey.cli as cli_module
        
        assert hasattr(cli_module, 'main')
        assert hasattr(cli_module, 'handle_status')
        assert hasattr(cli_module, 'handle_generate_agent')
    
    def test_pattern_names_import(self):
        """Test that pattern names can be imported."""
        from space_monkey.templates.common_patterns import get_pattern_names
        
        pattern_names = get_pattern_names()
        assert isinstance(pattern_names, list)
        assert len(pattern_names) > 0
        assert 'hr_bot' in pattern_names


class TestCLIRealGeneration:
    """Test actual generation functionality."""
    
    def test_real_agent_generation(self):
        """Test that agents can actually be generated."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, 'test_agent')
            
            # Mock the args object
            args = MagicMock()
            args.name = 'test-bot'
            args.description = 'A test bot'
            args.tools = ['notion:search']
            args.sub_agents = None
            args.bot_user_id = True
            args.citations = False
            args.guidelines = 'Be helpful'
            args.output_dir = output_dir
            args.pattern = None
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                handle_generate_agent(args)
                output = mock_stdout.getvalue()
                assert "🐒 Generating agent: test-bot" in output
                assert "🎉 Agent 'test-bot' generated successfully!" in output
                
                # Check that files were created
                assert os.path.exists(os.path.join(output_dir, 'agent.py'))
                assert os.path.exists(os.path.join(output_dir, 'purpose.py'))


if __name__ == "__main__":
    pytest.main([__file__]) 