#!/usr/bin/env python3
"""
Test file to run all project-level examples as integration tests.
This ensures that all cross-package examples are working correctly.
"""
import os
import sys
import pytest
import importlib.util
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file for tests
load_dotenv()

# Get the examples directory path
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Recursively get all Python files in the examples directory
def get_example_files():
    """Get all Python example files recursively."""
    example_files = []
    for root, dirs, files in os.walk(EXAMPLES_DIR):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                example_files.append(Path(root) / file)
    return example_files

example_files = get_example_files()

# Skip these examples in automated tests (require user interaction, external services, etc.)
SKIP_EXAMPLES = [
    "slack-bot/basic.py",  # Requires Slack tokens and socket mode  
    "integrations/storage-patterns.py",  # Requires libmagic system dependency
    "use-cases/slack-bot/basic.py",  # Requires libmagic system dependency
]

# Examples that have import issues in CI/certain environments
SKIP_IMPORT_TESTS = [
    "integrations/storage-patterns.py",  # Has libmagic dependency issues
    "integrations/streaming.py",  # Has libmagic dependency issues  
    "integrations/cross-package.py",  # Has libmagic dependency issues
    "use-cases/research-assistant/basic.py",  # Has libmagic dependency issues
    "use-cases/slack-bot/basic.py",  # Has libmagic dependency issues
    "getting-started/tool-groups.py",  # Has libmagic dependency issues
    "getting-started/quickstart.py",  # Has libmagic dependency issues
    "getting-started/basic-persistence.py",  # Has libmagic dependency issues
]

# Examples that need special environment setup
REQUIRES_API_KEY = [
    # All examples now use load_dotenv() and make real API calls
    # They will gracefully handle missing API keys through the LLM library
]


def import_module_from_path(path):
    """Import a module from a file path."""
    # Create a unique module name based on the full path
    module_name = str(path.relative_to(EXAMPLES_DIR)).replace('/', '_').replace('.py', '')
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


def should_skip_example(example_path):
    """Determine if an example should be skipped."""
    relative_path = str(example_path.relative_to(EXAMPLES_DIR))
    
    # Skip if in skip list
    if relative_path in SKIP_EXAMPLES:
        return True, f"Skipping {relative_path} as it's in the skip list"
    
    # All examples now use load_dotenv() and handle missing API keys gracefully
    # No need to skip based on API key availability
    
    return False, None


@pytest.mark.examples  # Mark all example tests with 'examples' marker
@pytest.mark.integration  # Also mark as integration tests
@pytest.mark.parametrize("example_path", example_files)
def test_example(example_path, monkeypatch):
    """Test that an example runs without errors."""
    relative_path = str(example_path.relative_to(EXAMPLES_DIR))
    
    # Check if we should skip this example
    should_skip, skip_reason = should_skip_example(example_path)
    if should_skip:
        pytest.skip(skip_reason)
    
    # Set up environment for examples
    monkeypatch.setattr("sys.argv", [str(example_path)])
    
    # Some examples might use input() - mock it to return empty string
    monkeypatch.setattr("builtins.input", lambda _: "")
    
    # Mock print to capture output (optional - helps with test output)
    printed_output = []
    original_print = print
    def mock_print(*args, **kwargs):
        printed_output.append(" ".join(str(arg) for arg in args))
        # Still print for debugging if needed
        return original_print(*args, **kwargs)
    
    monkeypatch.setattr("builtins.print", mock_print)
    
    # Import and run the example module
    try:
        module = import_module_from_path(example_path)
        
        # If the module has a main function, run it
        # Otherwise, the import itself is the test
        if hasattr(module, "main"):
            run_example_main(module)
        
        # If we got here, the example ran without errors
        assert True, "Example completed successfully"
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully in tests
        pytest.skip(f"Example {relative_path} was interrupted (likely requires user interaction)")
        
    except Exception as e:
        # Provide detailed error information
        error_msg = f"Example {relative_path} failed with error: {str(e)}"
        if printed_output:
            error_msg += f"\nOutput: {printed_output[-5:]}"  # Last 5 lines of output
        pytest.fail(error_msg)


@pytest.mark.examples
@pytest.mark.smoke  # Quick smoke test
def test_examples_directory_structure():
    """Test that the examples directory has the expected structure."""
    
    # Check that main directories exist
    expected_dirs = [
        "getting-started",
        "use-cases", 
        "integrations"
    ]
    
    for dirname in expected_dirs:
        dir_path = EXAMPLES_DIR / dirname
        assert dir_path.exists(), f"Missing examples directory: {dirname}"
        assert dir_path.is_dir(), f"{dirname} is not a directory"
    
    # Check that we have some example files
    assert len(example_files) > 0, "No example files found"
    
    # Check that README exists
    readme_path = EXAMPLES_DIR / "README.md"
    assert readme_path.exists(), "Missing examples README.md"


@pytest.mark.examples  
@pytest.mark.smoke
def test_examples_can_be_imported():
    """Smoke test that all examples can at least be imported."""
    
    import_failures = []
    
    for example_path in example_files:
        relative_path = str(example_path.relative_to(EXAMPLES_DIR))
        
        # Skip examples that we know require special setup
        should_skip, _ = should_skip_example(example_path)
        if should_skip:
            continue
            
        # Skip examples with known import issues
        if relative_path in SKIP_IMPORT_TESTS:
            continue
            
        try:
            import_module_from_path(example_path)
        except Exception as e:
            import_failures.append(f"{relative_path}: {str(e)}")
    
    if import_failures:
        pytest.fail(f"Failed to import examples:\n" + "\n".join(import_failures))


# Custom pytest configuration for examples
def pytest_configure(config):
    """Configure pytest for examples testing."""
    config.addinivalue_line(
        "markers", 
        "examples: mark test as an example integration test"
    )
    config.addinivalue_line(
        "markers",
        "smoke: mark test as a quick smoke test"
    )


if __name__ == "__main__":
    # Run tests when executed directly
    print("Running example tests...")
    sys.exit(pytest.main([__file__, "-v"]))