"""
Tests for the Slack blocks utility module
"""

import pytest
from unittest.mock import Mock

from space_monkey.utils.blocks import (
    convert_to_slack_blocks,
    create_simple_blocks,
    create_error_blocks,
    create_info_blocks,
    _convert_basic_markdown
)

class TestConvertToSlackBlocks:
    """Tests for the convert_to_slack_blocks function"""
    
    async def test_convert_simple_text(self):
        """Test converting simple text"""
        text = "Hello, world!"
        result = await convert_to_slack_blocks(text)
        
        assert "blocks" in result
        assert "text" in result
        assert result["text"] == text
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["type"] == "section"
        assert result["blocks"][0]["text"]["type"] == "mrkdwn"
        assert result["blocks"][0]["text"]["text"] == text
    
    async def test_convert_with_thread_ts(self):
        """Test converting text with thread timestamp"""
        text = "Hello, world!"
        thread_ts = "1234567890.123456"
        result = await convert_to_slack_blocks(text, thread_ts)
        
        # Should still work the same, thread_ts is just for context
        assert "blocks" in result
        assert "text" in result
        assert result["text"] == text
    
    async def test_convert_code_block(self):
        """Test converting text with code block"""
        text = "Here's some code:\n```python\nprint('hello')\n```"
        result = await convert_to_slack_blocks(text)
        
        assert len(result["blocks"]) == 2  # Text section + code section
        
        # First block should be the text
        assert "Here's some code:" in result["blocks"][0]["text"]["text"]
        
        # Second block should be the code
        code_block = result["blocks"][1]
        assert "```" in code_block["text"]["text"]
        assert "print('hello')" in code_block["text"]["text"]
    
    async def test_convert_multiple_sections(self):
        """Test converting text with multiple sections"""
        text = "Section 1\n\nSection 2\n\nSection 3"
        result = await convert_to_slack_blocks(text)
        
        assert len(result["blocks"]) == 3
        assert result["blocks"][0]["text"]["text"] == "Section 1"
        assert result["blocks"][1]["text"]["text"] == "Section 2"
        assert result["blocks"][2]["text"]["text"] == "Section 3"
    
    async def test_convert_empty_text(self):
        """Test converting empty text"""
        text = ""
        result = await convert_to_slack_blocks(text)
        
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["text"]["text"] == ""
    
    async def test_convert_with_error_handling(self):
        """Test that errors are handled gracefully"""
        # This should test the error handling, but it's hard to trigger
        # Let's test with a very long text that might cause issues
        text = "A" * 10000  # Very long text
        result = await convert_to_slack_blocks(text)
        
        # Should still return a valid result
        assert "blocks" in result
        assert "text" in result
        assert result["text"] == text

class TestConvertBasicMarkdown:
    """Tests for the _convert_basic_markdown function"""
    
    def test_convert_bold(self):
        """Test converting bold markdown"""
        text = "This is **bold** text"
        result = _convert_basic_markdown(text)
        assert result == "This is *bold* text"
    
    def test_convert_multiple_bold(self):
        """Test converting multiple bold sections"""
        text = "**First** and **second** bold"
        result = _convert_basic_markdown(text)
        assert result == "*First* and *second* bold"
    
    def test_convert_links(self):
        """Test converting markdown links"""
        text = "Check out [Google](https://google.com) for search"
        result = _convert_basic_markdown(text)
        assert result == "Check out <https://google.com|Google> for search"
    
    def test_convert_headers(self):
        """Test converting headers"""
        text = "# Header 1\n## Header 2\n### Header 3"
        result = _convert_basic_markdown(text)
        assert result == "*Header 1*\n*Header 2*\n*Header 3*"
    
    def test_convert_bullet_points(self):
        """Test converting bullet points"""
        text = "- Item 1\n- Item 2\n* Item 3"
        result = _convert_basic_markdown(text)
        assert result == "• Item 1\n• Item 2\n• Item 3"
    
    def test_convert_numbered_lists(self):
        """Test converting numbered lists"""
        text = "1. First item\n2. Second item\n3. Third item"
        result = _convert_basic_markdown(text)
        assert result == "1. First item\n2. Second item\n3. Third item"
    
    def test_convert_inline_code(self):
        """Test that inline code is preserved"""
        text = "Use `print()` function"
        result = _convert_basic_markdown(text)
        assert result == "Use `print()` function"  # Should be unchanged
    
    def test_convert_italic(self):
        """Test that italic is preserved"""
        text = "This is _italic_ text"
        result = _convert_basic_markdown(text)
        assert result == "This is _italic_ text"  # Should be unchanged
    
    def test_convert_complex_markdown(self):
        """Test converting complex markdown with multiple elements"""
        text = """# Title
        
This is **bold** and _italic_ text with a [link](https://example.com).

- Item 1
- Item 2

1. First
2. Second"""
        
        result = _convert_basic_markdown(text)
        
        assert "*Title*" in result
        assert "*bold*" in result
        assert "_italic_" in result
        assert "<https://example.com|link>" in result
        assert "• Item 1" in result
        assert "• Item 2" in result
        assert "1. First" in result
        assert "2. Second" in result

class TestCreateSimpleBlocks:
    """Tests for the create_simple_blocks function"""
    
    def test_create_simple_blocks(self):
        """Test creating simple blocks"""
        text = "Simple message"
        blocks = create_simple_blocks(text)
        
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["type"] == "mrkdwn"
        assert blocks[0]["text"]["text"] == text
    
    def test_create_simple_blocks_empty(self):
        """Test creating blocks with empty text"""
        text = ""
        blocks = create_simple_blocks(text)
        
        assert len(blocks) == 1
        assert blocks[0]["text"]["text"] == ""

class TestCreateErrorBlocks:
    """Tests for the create_error_blocks function"""
    
    def test_create_error_blocks(self):
        """Test creating error blocks"""
        error_message = "Something went wrong"
        blocks = create_error_blocks(error_message)
        
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["type"] == "mrkdwn"
        assert ":warning:" in blocks[0]["text"]["text"]
        assert "*Error:*" in blocks[0]["text"]["text"]
        assert error_message in blocks[0]["text"]["text"]
    
    def test_create_error_blocks_with_special_chars(self):
        """Test creating error blocks with special characters"""
        error_message = "Error with *special* characters & symbols"
        blocks = create_error_blocks(error_message)
        
        assert error_message in blocks[0]["text"]["text"]

class TestCreateInfoBlocks:
    """Tests for the create_info_blocks function"""
    
    def test_create_info_blocks(self):
        """Test creating info blocks"""
        info_message = "Here's some information"
        blocks = create_info_blocks(info_message)
        
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["type"] == "mrkdwn"
        assert ":information_source:" in blocks[0]["text"]["text"]
        assert info_message in blocks[0]["text"]["text"]
    
    def test_create_info_blocks_with_markdown(self):
        """Test creating info blocks with markdown"""
        info_message = "Info with **bold** text"
        blocks = create_info_blocks(info_message)
        
        assert info_message in blocks[0]["text"]["text"]

class TestBlocksIntegration:
    """Integration tests for the blocks module"""
    
    async def test_full_conversion_pipeline(self):
        """Test the full conversion pipeline with complex content"""
        text = """# Status Update

Here's what happened today:

1. **Fixed** the authentication bug
2. Added new [documentation](https://docs.example.com)
3. Deployed to production

```bash
npm run deploy
```

Next steps:
- Monitor for issues
- Update changelog"""
        
        result = await convert_to_slack_blocks(text)
        
        # Should have multiple blocks
        assert len(result["blocks"]) > 1
        
        # Should preserve original text
        assert result["text"] == text
        
        # Should convert markdown appropriately
        content = " ".join([block["text"]["text"] for block in result["blocks"]])
        assert "*Status Update*" in content
        assert "*Fixed*" in content
        assert "<https://docs.example.com|documentation>" in content
        assert "• Monitor for issues" in content 