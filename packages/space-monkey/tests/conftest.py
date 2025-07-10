"""
Pytest configuration for space_monkey tests.
"""

import pytest
import sys
from pathlib import Path

# Add the parent directory to the path so we can import space_monkey
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def space_monkey_version():
    """Fixture to get the space_monkey version."""
    import space_monkey
    return space_monkey.__version__
