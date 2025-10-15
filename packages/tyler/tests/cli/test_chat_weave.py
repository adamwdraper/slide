"""
Unit tests for Weave initialization in ChatManager.

Tests verify that Weave initialization is conditional on WANDB_PROJECT env var.
"""
import os
from unittest.mock import patch, MagicMock
import pytest


class TestChatManagerWeaveInit:
    """Test Weave initialization behavior in ChatManager"""
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': 'test-project'})
    def test_weave_init_with_project(self, mock_weave):
        """Test that Weave initializes when WANDB_PROJECT is set"""
        from tyler.cli.chat import ChatManager
        
        manager = ChatManager()
        mock_weave.init.assert_called_once_with('test-project')
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {}, clear=True)
    def test_weave_no_init_without_project(self, mock_weave):
        """Test that Weave does NOT initialize when WANDB_PROJECT not set"""
        from tyler.cli.chat import ChatManager
        
        manager = ChatManager()
        mock_weave.init.assert_not_called()
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': ''})
    def test_weave_no_init_with_empty_project(self, mock_weave):
        """Test that Weave does NOT initialize with empty WANDB_PROJECT"""
        from tyler.cli.chat import ChatManager
        
        manager = ChatManager()
        mock_weave.init.assert_not_called()
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': '   '})
    def test_weave_no_init_with_whitespace_project(self, mock_weave):
        """Test that Weave does NOT initialize with whitespace-only WANDB_PROJECT"""
        from tyler.cli.chat import ChatManager
        
        manager = ChatManager()
        mock_weave.init.assert_not_called()
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': 'my-custom-project'})
    def test_weave_init_with_custom_project_name(self, mock_weave):
        """Test that Weave initializes with custom project name"""
        from tyler.cli.chat import ChatManager
        
        manager = ChatManager()
        mock_weave.init.assert_called_once_with('my-custom-project')

