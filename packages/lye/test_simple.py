#!/usr/bin/env python3
"""Simple test script to validate W&B workspace tools without external dependencies."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lye'))

def test_basic_structure():
    """Test that the tools have the correct basic structure."""
    from wandb_workspaces import TOOLS
    
    print(f"✓ Found {len(TOOLS)} tools")
    assert len(TOOLS) == 7, f"Expected 7 tools, got {len(TOOLS)}"
    
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
    
    for expected in expected_names:
        assert expected in actual_names, f"Missing tool: {expected}"
        print(f"✓ Found tool: {expected}")
    
    # Test tool structure
    for tool in TOOLS:
        assert "definition" in tool, "Tool missing definition"
        assert "implementation" in tool, "Tool missing implementation"
        assert callable(tool["implementation"]), "Implementation is not callable"
        
        func_def = tool["definition"]["function"]
        assert "name" in func_def, "Tool missing name"
        assert "description" in func_def, "Tool missing description"
        assert "parameters" in func_def, "Tool missing parameters"
        
        params = func_def["parameters"]
        assert params["type"] == "object", "Parameters type should be object"
        assert "properties" in params, "Parameters missing properties"
        assert "required" in params, "Parameters missing required list"
        
        # Check required params exist in properties
        for req_param in params["required"]:
            assert req_param in params["properties"], f"Required param {req_param} not in properties"
    
    print("✓ All tool structure validation passed")

def test_import_error_handling():
    """Test that functions handle missing dependencies gracefully."""
    from wandb_workspaces import create_workspace
    
    # This should return an error since wandb_workspaces isn't available
    result = create_workspace(
        name="Test Workspace",
        entity="test_entity", 
        project="test_project"
    )
    
    assert result["success"] is False, "Should fail when dependencies missing"
    assert "wandb_workspaces package not installed" in result["error"], "Should show correct error message"
    print("✓ Import error handling works correctly")

if __name__ == "__main__":
    print("Running simple W&B workspace tools tests...")
    
    try:
        test_basic_structure()
        test_import_error_handling()
        print("\n✓ All tests passed!")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)