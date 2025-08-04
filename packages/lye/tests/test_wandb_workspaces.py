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
    
    def test_create_workspace_success(self):
        """Test successful workspace creation."""
        with patch('wandb_workspaces.workspaces') as mock_ws:
            # Mock workspace and save result
            mock_workspace = Mock()
            mock_workspace.save.return_value = Mock(id="workspace_123", url="https://wandb.ai/test/workspace")
            mock_ws.Workspace.return_value = mock_workspace
            mock_ws.Section = Mock()
            
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
            mock_workspace.save.assert_called_once()
    
    def test_create_workspace_import_error(self):
        """Test workspace creation when wandb_workspaces is not installed."""
        with patch('builtins.__import__', side_effect=ImportError()):
            result = create_workspace(
                name="Test Workspace",
                entity="test_entity",
                project="test_project"
            )
            
            assert result["success"] is False
            assert "wandb_workspaces package not installed" in result["error"]
    
    def test_load_workspace_success(self):
        """Test successful workspace loading."""
        with patch('wandb_workspaces.workspaces') as mock_ws:
            mock_workspace = Mock()
            mock_workspace.name = "Test Workspace"
            mock_workspace.entity = "test_entity"
            mock_workspace.project = "test_project"
            mock_workspace.sections = [Mock(), Mock()]
            mock_ws.Workspace.from_url.return_value = mock_workspace
            
            result = load_workspace(url="https://wandb.ai/test/workspace")
            
            assert result["success"] is True
            assert result["workspace_name"] == "Test Workspace"
            assert result["entity"] == "test_entity"
            assert result["project"] == "test_project"
            assert result["sections_count"] == 2
            assert result["error"] is None
    
    def test_create_line_plot_success(self):
        """Test successful line plot creation."""
        with patch('wandb_workspaces.reports') as mock_wr:
            mock_plot = Mock()
            mock_wr.LinePlot.return_value = mock_plot
            
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
    
    def test_create_scalar_chart_success(self):
        """Test successful scalar chart creation."""
        with patch('wandb_workspaces.reports') as mock_wr:
            mock_chart = Mock()
            mock_wr.ScalarChart.return_value = mock_chart
            
            result = create_scalar_chart(
                metric="final_accuracy",
                title="Model Performance"
            )
            
            assert result["success"] is True
            assert result["chart_type"] == "scalar_chart"
            assert result["chart_config"]["metric"] == "final_accuracy"
            assert result["chart_config"]["title"] == "Model Performance"
            assert result["error"] is None
    
    def test_create_run_filter_success(self):
        """Test successful run filter creation."""
        with patch('wandb_workspaces.workspaces') as mock_ws:
            mock_runset_settings = Mock()
            mock_ws.RunsetSettings.return_value = mock_runset_settings
            
            filters = {"accuracy": {"$gt": 0.9}}
            result = create_run_filter(
                filters=filters,
                sort_by="accuracy",
                sort_order="desc",
                limit=50
            )
            
            assert result["success"] is True
            assert result["filter_config"]["filters"] == filters
            assert result["filter_config"]["sort_by"] == "accuracy"
            assert result["filter_config"]["sort_order"] == "desc"
            assert result["filter_config"]["limit"] == 50
            assert result["error"] is None
    
    def test_save_workspace_view_success(self):
        """Test successful workspace view saving."""
        with patch('wandb_workspaces.workspaces') as mock_ws:
            mock_workspace = Mock()
            mock_result = Mock(url="https://wandb.ai/test/view")
            mock_workspace.save_as_new_view.return_value = mock_result
            mock_ws.Workspace.from_url.return_value = mock_workspace
            
            result = save_workspace_view(
                workspace_url="https://wandb.ai/test/workspace",
                view_name="Test View",
                description="Test view description"
            )
            
            assert result["success"] is True
            assert result["view_name"] == "Test View"
            assert result["description"] == "Test view description"
            assert result["new_view_url"] == "https://wandb.ai/test/view"
            assert result["error"] is None
    
    def test_get_project_runs_success(self):
        """Test successful project runs retrieval."""
        with patch('wandb.Api') as mock_api_class:
            # Mock API and runs
            mock_api = Mock()
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
            
            mock_run2 = Mock()
            mock_run2.id = "run_2"
            mock_run2.name = "Test Run 2"
            mock_run2.state = "running"
            mock_run2.config = {"learning_rate": 0.001}
            mock_run2.summary = {"accuracy": 0.92}
            mock_run2.url = "https://wandb.ai/test/run2"
            mock_run2.created_at = None
            mock_run2.tags = ["experiment2"]
            mock_run2.group = "group2"
            
            mock_api.runs.return_value = [mock_run1, mock_run2]
            mock_api_class.return_value = mock_api
            
            result = get_project_runs(
                entity="test_entity",
                project="test_project",
                limit=10
            )
            
            assert result["success"] is True
            assert result["entity"] == "test_entity"
            assert result["project"] == "test_project"
            assert result["runs_count"] == 2
            assert len(result["runs"]) == 2
            assert result["runs"][0]["id"] == "run_1"
            assert result["runs"][0]["name"] == "Test Run 1"
            assert result["runs"][1]["id"] == "run_2"
            assert result["error"] is None
    
    def test_get_project_runs_import_error(self):
        """Test project runs retrieval when wandb is not installed."""
        with patch('builtins.__import__', side_effect=ImportError()):
            result = get_project_runs(
                entity="test_entity",
                project="test_project"
            )
            
            assert result["success"] is False
            assert "wandb package not installed" in result["error"]
    
    def test_create_workspace_with_sections(self):
        """Test workspace creation with custom sections."""
        with patch('wandb_workspaces.workspaces') as mock_ws:
            mock_workspace = Mock()
            mock_workspace.save.return_value = Mock(id="workspace_123")
            mock_ws.Workspace.return_value = mock_workspace
            mock_section = Mock()
            mock_ws.Section.return_value = mock_section
            
            sections = [
                {
                    "name": "Training Metrics",
                    "panels": [],
                    "is_open": True
                },
                {
                    "name": "Validation Metrics", 
                    "panels": [],
                    "is_open": False
                }
            ]
            
            result = create_workspace(
                name="Test Workspace",
                entity="test_entity",
                project="test_project",
                sections=sections
            )
            
            assert result["success"] is True
            # Verify Section was called for each section
            assert mock_ws.Section.call_count == 2
    
    def test_error_handling(self):
        """Test error handling in various functions."""
        with patch('wandb_workspaces.workspaces', side_effect=Exception("Test error")):
            result = create_workspace(
                name="Test Workspace",
                entity="test_entity", 
                project="test_project"
            )
            
            assert result["success"] is False
            assert "Test error" in result["error"]