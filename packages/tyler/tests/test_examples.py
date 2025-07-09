#!/usr/bin/env python3
"""
Test file to run all examples as integration tests.
This ensures that all examples are working correctly.
"""
import os
import sys
import pytest
import importlib.util
import asyncio
from pathlib import Path

# Get the examples directory path
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Get all Python files in the examples directory
example_files = [f for f in EXAMPLES_DIR.glob("*.py") if f.is_file() and not f.name.startswith("__")]

# Skip these examples in automated tests (if any are problematic or require user interaction)
SKIP_EXAMPLES = []


def import_module_from_path(path):
    """Import a module from a file path."""
    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_example_main(module):
    """Run the main function of an example module."""
    if hasattr(module, "main"):
        if asyncio.iscoroutinefunction(module.main):
            return asyncio.run(module.main())
        else:
            return module.main()
    return None


@pytest.mark.examples  # Mark all example tests with 'examples' marker
@pytest.mark.integration  # Also mark as integration tests
@pytest.mark.parametrize("example_path", example_files)
def test_example(example_path, monkeypatch):
    """Test that an example runs without errors."""
    example_name = example_path.name
    
    # Skip examples that are in the skip list
    if example_name in SKIP_EXAMPLES:
        pytest.skip(f"Skipping {example_name} as it's in the skip list")
    
    # Set up environment for examples
    monkeypatch.setattr("sys.argv", [str(example_path)])
    
    # Some examples might use input() - mock it to return empty string
    monkeypatch.setattr("builtins.input", lambda _: "")
    
    # Import the example module
    try:
        module = import_module_from_path(example_path)
        
        # If the module has a main function, run it
        # Otherwise, the import itself is the test
        if hasattr(module, "main"):
            run_example_main(module)
        
        # If we got here, the example ran without errors
        assert True
    except Exception as e:
        pytest.fail(f"Example {example_name} failed with error: {str(e)}") 