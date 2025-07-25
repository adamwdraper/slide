import os
import pytest
import requests
from unittest.mock import patch, MagicMock
from lye.notion import (
    NotionClient, search, get_page, get_page_content,
    create_comment, get_comments, create_page, update_block,
    create_notion_client
)

# Mock responses
MOCK_RAW_PAGE_ITEM_FOR_SEARCH = {
    "object": "page",
    "id": "page_id_123",
    "created_time": "2023-01-01T12:00:00.000Z",
    "last_edited_time": "2023-01-02T12:00:00.000Z",
    "created_by": {"object": "user", "id": "user_id_1"},
    "last_edited_by": {"object": "user", "id": "user_id_2"},
    "cover": None,
    "icon": None,
    "parent": {"type": "database_id", "database_id": "db_id_456"},
    "archived": False,
    "in_trash": False, # Assuming in_trash might be in raw, or handled by _simplify_notion_item
    "properties": {
        "title": {
            "id": "title",
            "type": "title",
            "title": [{"type": "text", "text": {"content": "Test Page Title", "link": None}, "annotations": {}, "plain_text": "Test Page Title", "href": None}]
        }
    },
    "url": "https://www.notion.so/page_id_123",
    "public_url": None,
}

SIMPLIFIED_PAGE_ITEM_FOR_SEARCH = {
    "object": "page",
    "id": "page_id_123",
    "created_time": "2023-01-01T12:00:00.000Z",
    "last_edited_time": "2023-01-02T12:00:00.000Z",
    "archived": False,
    "in_trash": False,
    "parent": {"type": "database_id", "database_id": "db_id_456"},
    "title": "Test Page Title",
    "url": "https://www.notion.so/page_id_123",
    "public_url": None
}

# This mocks the direct JSON response from the Notion API's search endpoint
MOCK_RAW_NOTION_SEARCH_API_RESPONSE = {
    "object": "list",
    "results": [MOCK_RAW_PAGE_ITEM_FOR_SEARCH],
    "next_cursor": "some_next_cursor_value",
    "has_more": True,
    "type": "page_or_database",
    "page_or_database": {},
    "request_id": "test_request_id_123"
}

# This is the expected output from our @weave.op search function
EXPECTED_WEAVE_OP_SEARCH_RESULT = {
    "object": "list",
    "results": [SIMPLIFIED_PAGE_ITEM_FOR_SEARCH],
    "next_cursor": "some_next_cursor_value",
    "has_more": True,
    "type": "page_or_database",
    "page_or_database": {},
    "request_id": "test_request_id_123"
}

MOCK_PAGE_RESPONSE = {
    "id": "123",
    "properties": {"title": "Test Page"}
}

MOCK_PAGE_CONTENT_RESPONSE = {
    "results": [{"type": "paragraph", "paragraph": {"text": "Test content"}}],
    "next_cursor": None
}

MOCK_COMMENT_RESPONSE = {
    "id": "comment-123",
    "rich_text": {"text": {"content": "Test comment"}}
}

MOCK_COMMENTS_LIST_RESPONSE = {
    "results": [MOCK_COMMENT_RESPONSE],
    "next_cursor": None
}

MOCK_CREATE_PAGE_RESPONSE = {
    "id": "page-123",
    "properties": {"title": "New Test Page"}
}

MOCK_UPDATE_BLOCK_RESPONSE = {
    "id": "block-123",
    "type": "paragraph",
    "paragraph": {"text": [{"text": {"content": "Updated content"}}]}
}

@pytest.fixture
def mock_env_token():
    """Mock environment token fixture"""
    with patch.dict(os.environ, {"NOTION_TOKEN": "test-token"}):
        yield

def test_notion_client_init_missing_token():
    """Test NotionClient initialization with missing token"""
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="Notion API token not found"):
            create_notion_client()

def test_search(mock_env_token):
    """Test search functionality"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RAW_NOTION_SEARCH_API_RESPONSE
        mock_post.return_value = mock_response

        result = search(
            query="test query",
            filter={"property": "object", "value": "page"},
            start_cursor="cursor1",
            page_size=10
        )
        assert result == EXPECTED_WEAVE_OP_SEARCH_RESULT
        mock_post.assert_called_once()

def test_get_page(mock_env_token):
    """Test get_page functionality"""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_PAGE_RESPONSE
        mock_get.return_value = mock_response

        result = get_page(page_id="123")
        assert result == MOCK_PAGE_RESPONSE
        mock_get.assert_called_once()

def test_get_page_content(mock_env_token):
    """Test get_page_content functionality"""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        # First call - return page info
        mock_response.json.return_value = MOCK_PAGE_RESPONSE
        # Second call - return page content
        mock_response.json.side_effect = [
            MOCK_PAGE_RESPONSE,  # First call returns page info
            MOCK_PAGE_CONTENT_RESPONSE  # Second call returns content
        ]
        mock_get.return_value = mock_response

        result = get_page_content(page_id="123")
        assert "results" in result
        assert mock_get.call_count == 2  # Expect two calls

def test_create_comment(mock_env_token):
    """Test create_comment functionality"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_COMMENT_RESPONSE
        mock_post.return_value = mock_response

        rich_text = [{"text": {"content": "Test comment"}}]
        result = create_comment(rich_text=rich_text, page_id="123")
        assert result == MOCK_COMMENT_RESPONSE
        mock_post.assert_called_once()

def test_get_comments(mock_env_token):
    """Test get_comments function with all parameters"""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_COMMENTS_LIST_RESPONSE
        mock_get.return_value = mock_response

        result = get_comments(block_id="block1", start_cursor="cursor1", page_size=10)
        assert result == MOCK_COMMENTS_LIST_RESPONSE
        mock_get.assert_called_once()

def test_create_page(mock_env_token):
    """Test create_page function"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CREATE_PAGE_RESPONSE
        mock_post.return_value = mock_response

        parent = {"type": "page_id", "id": "parent1"}
        properties = {"title": {"title": [{"text": {"content": "New Test Page"}}]}}
        children = [{"type": "paragraph", "paragraph": {"text": [{"text": {"content": "Test content"}}]}}]
        icon = {"type": "emoji", "emoji": "📝"}
        cover = {"type": "external", "external": {"url": "https://example.com/image.jpg"}}

        result = create_page(
            parent=parent,
            properties=properties,
            children=children,
            icon=icon,
            cover=cover
        )
        assert result == MOCK_CREATE_PAGE_RESPONSE
        mock_post.assert_called_once()

def test_update_block(mock_env_token):
    """Test update_block function"""
    with patch('requests.patch') as mock_patch:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_UPDATE_BLOCK_RESPONSE
        mock_patch.return_value = mock_response

        block_type = "paragraph"
        content = {
            "rich_text": [{"text": {"content": "Updated content"}}]
        }

        result = update_block(
            block_id="block1",
            block_type=block_type,
            content=content
        )
        assert result == MOCK_UPDATE_BLOCK_RESPONSE
        mock_patch.assert_called_once()

def test_notion_api_error_handling(mock_env_token):
    """Test error handling for API requests"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            search(query="test")

def test_search_with_minimal_params(mock_env_token):
    """Test search function with minimal parameters"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RAW_NOTION_SEARCH_API_RESPONSE
        mock_post.return_value = mock_response

        result = search()
        assert result == EXPECTED_WEAVE_OP_SEARCH_RESULT
        mock_post.assert_called_once()

def test_create_comment_with_page_id(mock_env_token):
    """Test create_comment function with page_id"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_COMMENT_RESPONSE
        mock_post.return_value = mock_response

        rich_text = [{"text": {"content": "Test comment"}}]
        result = create_comment(rich_text=rich_text, page_id="page1")
        assert result == MOCK_COMMENT_RESPONSE
        mock_post.assert_called_once()

def test_create_comment_with_discussion_id(mock_env_token):
    """Test create_comment function with discussion_id"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_COMMENT_RESPONSE
        mock_post.return_value = mock_response

        rich_text = [{"text": {"content": "Test comment"}}]
        result = create_comment(rich_text=rich_text, discussion_id="discussion1")
        assert result == MOCK_COMMENT_RESPONSE
        mock_post.assert_called_once()

def test_get_comments_minimal_params(mock_env_token):
    """Test get_comments function with only required parameters"""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_COMMENTS_LIST_RESPONSE
        mock_get.return_value = mock_response

        result = get_comments(block_id="block1")
        assert result == MOCK_COMMENTS_LIST_RESPONSE
        mock_get.assert_called_once() 