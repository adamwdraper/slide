import pytest
from unittest.mock import Mock, patch, MagicMock
from lye.wandb_workspaces import (
    create_workspace,
    load_workspace,
    create_line_plot,
    create_scalar_chart,
    create_run_filter,
    save_workspace_view,
    get_project_runs,
    TOOLS
)

class TestWandBWorkspaceTools:
    """Test suite for Weights & Biases workspace tools."""
    
    def test_tools_list_structure(self):
        """Test that TOOLS list has correct structure."""
        assert isinstance(TOOLS, list)
        assert len(TOOLS) == 7
        
        # Check each tool has required structure
        for tool in TOOLS:
            assert "definition" in tool
            assert "implementation" in tool
            assert tool["definition"]["type"] == "function"
            assert "function" in tool["definition"]
            assert "name" in tool["definition"]["function"]
            assert "description" in tool["definition"]["function"]
            assert "parameters" in tool["definition"]["function"]
    
    def test_create_workspace_import_error(self):
        """Test workspace creation when wandb_workspaces is not installed."""
        # Since the actual import is inside a try/except, we mock the import failing
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb_workspaces.workspaces':
                    raise ImportError("No module named 'wandb_workspaces'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = create_workspace(
                name="Test Workspace",
                entity="test_entity",
                project="test_project"
            )
            
            assert result["success"] is False
            assert "wandb_workspaces package not installed" in result["error"]
    
    def test_get_project_runs_import_error(self):
        """Test project runs retrieval when wandb is not installed."""
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb':
                    raise ImportError("No module named 'wandb'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = get_project_runs(
                entity="test_entity",
                project="test_project"
            )
            
            assert result["success"] is False
            assert "wandb package not installed" in result["error"]
    
    def test_create_workspace_with_mock_success(self):
        """Test successful workspace creation with full mocking."""
        # Mock the entire function's dependencies
        mock_workspace = Mock()
        mock_workspace.save.return_value = Mock(id="workspace_123", url="https://wandb.ai/test/workspace")
        
        mock_section = Mock()
        
        with patch('builtins.__import__') as mock_import:
            mock_ws_module = Mock()
            mock_ws_module.Workspace.return_value = mock_workspace
            mock_ws_module.Section.return_value = mock_section
            
            def side_effect(name, *args, **kwargs):
                if name == 'wandb_workspaces.workspaces':
                    return mock_ws_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = create_workspace(
                name="Test Workspace",
                entity="test_entity",
                project="test_project",
                description="Test description"
            )
            
            assert result["success"] is True
            assert result["workspace_name"] == "Test Workspace"
            assert result["entity"] == "test_entity" 
            assert result["project"] == "test_project"
            assert result["error"] is None
    
    def test_get_project_runs_with_mock_success(self):
        """Test successful project runs retrieval with full mocking."""
        # Mock wandb module and API
        mock_run1 = Mock()
        mock_run1.id = "run_1"
        mock_run1.name = "Test Run 1"
        mock_run1.state = "finished"
        mock_run1.config = {"learning_rate": 0.01}
        mock_run1.summary = {"accuracy": 0.95}
        mock_run1.url = "https://wandb.ai/test/run1"
        mock_run1.created_at = None
        mock_run1.tags = ["experiment1"]
        mock_run1.group = "group1"
        
        mock_api = Mock()
        mock_api.runs.return_value = [mock_run1]
        
        mock_wandb_module = Mock()
        mock_wandb_module.Api.return_value = mock_api
        
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb':
                    return mock_wandb_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = get_project_runs(
                entity="test_entity",
                project="test_project",
                limit=10
            )
            
            assert result["success"] is True
            assert result["entity"] == "test_entity"
            assert result["project"] == "test_project"
            assert result["runs_count"] == 1
            assert len(result["runs"]) == 1
            assert result["runs"][0]["id"] == "run_1"
            assert result["runs"][0]["name"] == "Test Run 1"
            assert result["error"] is None
    
    def test_create_line_plot_import_error(self):
        """Test line plot creation when wandb_workspaces.reports is not available."""
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb_workspaces.reports':
                    raise ImportError("No module named 'wandb_workspaces'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = create_line_plot(
                x="step",
                y=["loss", "accuracy"]
            )
            
            assert result["success"] is False
            assert "wandb_workspaces package not installed" in result["error"]
    
    def test_create_line_plot_with_mock_success(self):
        """Test successful line plot creation.""" 
        mock_plot = Mock()
        mock_wr_module = Mock()
        mock_wr_module.LinePlot.return_value = mock_plot
        
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb_workspaces.reports':
                    return mock_wr_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = create_line_plot(
                x="step",
                y=["loss", "accuracy"],
                title="Training Metrics"
            )
            
            assert result["success"] is True
            assert result["plot_type"] == "line_plot"
            assert result["plot_config"]["x"] == "step"
            assert result["plot_config"]["y"] == ["loss", "accuracy"]
            assert result["plot_config"]["title"] == "Training Metrics"
            assert result["error"] is None
    
    def test_create_scalar_chart_with_mock_success(self):
        """Test successful scalar chart creation."""
        mock_chart = Mock()
        mock_wr_module = Mock()
        mock_wr_module.ScalarChart.return_value = mock_chart
        
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb_workspaces.reports':
                    return mock_wr_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = create_scalar_chart(
                metric="final_accuracy",
                title="Model Performance"
            )
            
            assert result["success"] is True
            assert result["chart_type"] == "scalar_chart"
            assert result["chart_config"]["metric"] == "final_accuracy"
            assert result["chart_config"]["title"] == "Model Performance"
            assert result["error"] is None
    
    def test_error_handling_general(self):
        """Test general error handling in functions."""
        # Test that unexpected exceptions are caught and returned properly
        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == 'wandb_workspaces.workspaces':
                    raise Exception("Unexpected error")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            
            result = create_workspace(
                name="Test Workspace",
                entity="test_entity",
                project="test_project"
            )
            
            assert result["success"] is False
            assert "Unexpected error" in result["error"]
    
    def test_tool_names_are_correct(self):
        """Test that all tool names follow expected naming convention."""
        expected_names = [
            "wandb-create_workspace",
            "wandb-load_workspace", 
            "wandb-create_line_plot",
            "wandb-create_scalar_chart",
            "wandb-create_run_filter",
            "wandb-save_workspace_view",
            "wandb-get_project_runs"
        ]
        
        actual_names = [tool["definition"]["function"]["name"] for tool in TOOLS]
        
        assert set(actual_names) == set(expected_names)
        assert len(actual_names) == len(expected_names)  # No duplicates
    
    def test_tool_parameters_are_valid(self):
        """Test that all tools have valid parameter schemas."""
        for tool in TOOLS:
            params = tool["definition"]["function"]["parameters"]
            assert "type" in params
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params
            
            # Check that required parameters exist in properties
            for required_param in params["required"]:
                assert required_param in params["properties"]