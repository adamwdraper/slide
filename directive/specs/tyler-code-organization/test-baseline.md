# Test Baseline - Tyler Refactoring

This document tracks the test baseline before refactoring begins.

## Pre-Refactor Checklist

Before starting any code changes:

- [ ] Run full test suite
- [ ] Document all test results
- [ ] Capture coverage percentage
- [ ] Set up performance benchmarks
- [ ] Document any existing failures
- [ ] Review test organization

## Running Tests

### Full Test Suite

The Tyler test suite can be run with pytest. Note: The `pytest.ini` has coverage configured, which may require the `pytest-cov` package.

```bash
cd /Users/adamdraper/Documents/Code/slide/packages/tyler

# Option 1: Full test suite with coverage (recommended)
pytest tests/

# Option 2: If coverage issues, disable coverage temporarily
pytest tests/ --no-cov

# Option 3: Run specific test categories
pytest tests/ -m "not examples"  # Skip example tests
pytest tests/ -m "integration"   # Only integration tests
pytest tests/models/             # Only model tests
```

### Test Files Discovered

```
tests/
├── __init__.py
├── conftest.py
├── test_imports.py
├── test_examples.py
│
├── models/
│   ├── test_agent.py
│   ├── test_agent_tools.py
│   ├── test_agent_tools_direct.py
│   ├── test_agent_delegation.py
│   ├── test_agent_observability.py
│   └── test_agent_streaming.py
│
├── utils/
│   └── test_tool_runner.py
│
├── mcp/
│   ├── test_adapter.py
│   └── test_client.py
│
├── a2a/
│   ├── test_adapter.py
│   └── test_client.py
│
├── eval/
│   └── test_eval_framework.py
│
└── integration/
    ├── test_agent_delegation_integration.py
    └── test_direct_imports_integration.py
```

Total: **16 test files**

## Baseline Results

### Test Status

**Date**: 2025-01-11  
**Branch**: `refactor/tyler-code-organization`  
**Commit**: `265ef91`

```bash
# Run this command to capture baseline:
cd /Users/adamdraper/Documents/Code/slide/packages/tyler
pytest tests/ -v --tb=short > baseline-test-results.txt 2>&1
```

**Status**: ⏳ To be run before Phase 1

### Coverage Baseline

```bash
# Run this command to capture coverage:
cd /Users/adamdraper/Documents/Code/slide/packages/tyler
pytest tests/ --cov=tyler --cov-report=term --cov-report=html > baseline-coverage.txt 2>&1
```

**Target**: ≥80% coverage  
**Status**: ⏳ To be captured

### Performance Baseline

Create a benchmark script:

```python
# benchmark/baseline.py
import asyncio
import time
from tyler import Agent, Thread, Message

async def benchmark_agent_init():
    """Measure Agent initialization time"""
    start = time.perf_counter()
    agent = Agent(
        model_name="gpt-4.1",
        purpose="Test agent",
        tools=["web"]
    )
    end = time.perf_counter()
    return (end - start) * 1000  # milliseconds

async def benchmark_message_creation():
    """Measure message creation time"""
    agent = Agent(model_name="gpt-4.1")
    
    start = time.perf_counter()
    for _ in range(1000):
        Message(role="user", content="test")
    end = time.perf_counter()
    
    return (end - start) * 1000 / 1000  # ms per message

# Run benchmarks
if __name__ == "__main__":
    init_time = asyncio.run(benchmark_agent_init())
    print(f"Agent init: {init_time:.2f}ms")
    
    msg_time = asyncio.run(benchmark_message_creation())
    print(f"Message creation: {msg_time:.4f}ms per message")
```

**Status**: ⏳ To be created in Phase 1

## Test Requirements for Each Phase

After each refactoring phase:

1. ✅ **All existing tests pass** (100%)
2. ✅ **Coverage maintains ≥80%**
3. ✅ **New tests added for new components**
4. ✅ **Performance within 5% of baseline**
5. ✅ **No test skips or xfails added**

## Monitoring During Refactor

### After Each Commit

```bash
# Quick test run
pytest tests/ -x  # Stop on first failure

# If tests pass, check coverage
pytest tests/ --cov=tyler --cov-report=term-missing
```

### After Each Phase

```bash
# Full test suite
pytest tests/ -v

# Coverage report
pytest tests/ --cov=tyler --cov-report=html

# View coverage
open htmlcov/index.html

# Run performance benchmarks
python benchmark/baseline.py
```

## Known Issues / Baseline Notes

### Pre-Existing Test Failures
**Status**: ⏳ To be documented

_Document any tests that are currently failing or skipped:_
- None expected (clean baseline required)

### Test Dependencies
- pytest >= 7.4.3
- pytest-asyncio >= 0.21.1
- pytest-cov (for coverage)
- Python 3.13+

### Environment Setup

```bash
# Ensure dependencies installed
cd /Users/adamdraper/Documents/Code/slide/packages/tyler
uv pip install -e ".[dev]"

# Verify pytest works
pytest --version
```

## Baseline Capture Commands

Run these before starting Phase 1:

```bash
#!/bin/bash
# capture-baseline.sh

cd /Users/adamdraper/Documents/Code/slide/packages/tyler

echo "Capturing test baseline..."
echo "=========================="

# 1. Run tests
echo "Running tests..."
pytest tests/ -v --tb=short > baseline-test-results.txt 2>&1
TEST_EXIT_CODE=$?
echo "Test exit code: $TEST_EXIT_CODE"

# 2. Capture coverage
echo "Capturing coverage..."
pytest tests/ --cov=tyler --cov-report=term --cov-report=html > baseline-coverage.txt 2>&1

# 3. Extract coverage percentage
COVERAGE=$(grep "TOTAL" baseline-coverage.txt | awk '{print $NF}')
echo "Coverage: $COVERAGE"

# 4. Line counts
echo "Line counts..."
echo "Agent.py: $(wc -l tyler/models/agent.py | awk '{print $1}') lines"
echo "tool_runner.py: $(wc -l tyler/utils/tool_runner.py | awk '{print $1}') lines"

# 5. Create summary
cat > baseline-summary.txt << EOF
Test Baseline Captured: $(date)
Branch: $(git branch --show-current)
Commit: $(git rev-parse --short HEAD)

Test Results: $TEST_EXIT_CODE (0 = pass)
Coverage: $COVERAGE
Agent Size: $(wc -l tyler/models/agent.py | awk '{print $1}') lines
Tool Runner: $(wc -l tyler/utils/tool_runner.py | awk '{print $1}') lines

Files:
- baseline-test-results.txt
- baseline-coverage.txt
- htmlcov/ (coverage report)
EOF

echo "Baseline captured!"
cat baseline-summary.txt
```

## Next Steps

1. **Run baseline capture script**
2. **Review all test results**
3. **Fix any pre-existing failures**
4. **Document the clean baseline**
5. **Begin Phase 1 of refactoring**

---

**Important**: Do not proceed with refactoring until we have a clean baseline with all tests passing.

