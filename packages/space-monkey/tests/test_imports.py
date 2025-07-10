"""
Test basic imports for space_monkey package.
"""

import pytest


def test_space_monkey_imports():
    """Test that the main space_monkey package can be imported."""
    import space_monkey
    assert hasattr(space_monkey, '__version__')
    assert space_monkey.__version__ is not None


def test_space_monkey_modules():
    """Test that space_monkey modules can be imported."""
    import space_monkey.agents
    import space_monkey.templates
    import space_monkey.core
    
    # Basic structure validation
    assert hasattr(space_monkey.agents, '__all__')
    assert hasattr(space_monkey.templates, '__all__')
    assert hasattr(space_monkey.core, '__all__')
