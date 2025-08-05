"""Test imports for Lye tools"""
import pytest
from lye import (
    # Module lists
    WEB_TOOLS,
    AUDIO_TOOLS,
    IMAGE_TOOLS,
    FILES_TOOLS,
    COMMAND_LINE_TOOLS,
    BROWSER_TOOLS,
    SLACK_TOOLS,
    NOTION_TOOLS,
    WANDB_TOOLS,
    TOOLS,
    # Module namespaces
    web,
    files,
    command_line,
    audio,
    image,
    browser,
    slack,
    notion
)


class TestLyeImports:
    """Test Lye imports and tool structure"""
    
    def test_tool_lists_exist(self):
        """Test that all tool lists are accessible"""
        assert isinstance(TOOLS, list)
        assert isinstance(WEB_TOOLS, list)
        assert isinstance(FILES_TOOLS, list)
        assert isinstance(COMMAND_LINE_TOOLS, list)
        assert isinstance(AUDIO_TOOLS, list)
        assert isinstance(IMAGE_TOOLS, list)
    
    def test_module_namespaces(self):
        """Test that we can import modules as namespaces"""
        # Check modules exist
        assert web is not None
        assert files is not None
        assert command_line is not None
        assert audio is not None
        assert image is not None
        
        # Check modules have TOOLS attribute
        assert hasattr(web, 'TOOLS')
        assert hasattr(files, 'TOOLS')
        assert hasattr(command_line, 'TOOLS')
        assert hasattr(audio, 'TOOLS')
        assert hasattr(image, 'TOOLS')
        
        # Check we can access functions through namespaces
        assert hasattr(web, 'fetch_page')
        assert hasattr(web, 'download_file')
        assert hasattr(files, 'read_file')
        assert hasattr(files, 'write_file')
        assert hasattr(command_line, 'run_command')
        assert hasattr(audio, 'text_to_speech')
        assert hasattr(audio, 'speech_to_text')
        assert hasattr(image, 'generate_image')
        assert hasattr(image, 'analyze_image')
    
    def test_namespace_functions_are_callable(self):
        """Test that functions accessed through namespaces are callable"""
        assert callable(web.fetch_page)
        assert callable(web.download_file)
        assert callable(files.read_file)
        assert callable(files.write_file)
        assert callable(command_line.run_command)
        assert callable(audio.text_to_speech)
        assert callable(audio.speech_to_text)
    
    def test_tools_have_correct_structure(self):
        """Test that tools have the required structure"""
        for tool in WEB_TOOLS:
            assert isinstance(tool, dict)
            assert 'definition' in tool
            assert 'implementation' in tool
            assert 'type' in tool['definition']
            assert 'function' in tool['definition']
            assert 'name' in tool['definition']['function']
            assert 'description' in tool['definition']['function']
            assert 'parameters' in tool['definition']['function']
    
    def test_combined_tools_list(self):
        """Test that TOOLS contains all module tools"""
        # TOOLS should contain tools from all modules
        all_module_tools = (
            WEB_TOOLS + FILES_TOOLS + COMMAND_LINE_TOOLS + 
            AUDIO_TOOLS + IMAGE_TOOLS + BROWSER_TOOLS +
            SLACK_TOOLS + NOTION_TOOLS + WANDB_TOOLS
        )
        
        # Should have the same number of tools
        assert len(TOOLS) == len(all_module_tools)
    
    def test_no_duplicate_tools(self):
        """Test that there are no duplicate tool names"""
        tool_names = [tool['definition']['function']['name'] for tool in TOOLS]
        assert len(tool_names) == len(set(tool_names)), "Duplicate tool names found" 