# GitHub Actions Workflows

This document describes the CI/CD workflows for the Slide project.

## Workflow Overview

### 📦 `test.yml` - Main Test Workflow
**Triggers:** PRs to `main` branch
**Paths:** `packages/**, examples/**, tests/**, .github/workflows/test.yml`

**Jobs:**
1. **Package Tests** (parallel):
   - `test-narrator` - Tests narrator package
   - `test-tyler` - Tests tyler package (depends on narrator)
   - `test-space-monkey` - Tests space-monkey package (depends on narrator)
   - `test-lye` - Tests lye package (with system dependencies)

2. **Integration Tests** (after package tests):
   - `integration-test` - Tests package imports and basic functionality
   - `test-examples` - Tests project examples (smoke tests, imports, structure)

**Key Features:**
- ✅ Runs on every PR to main
- ✅ Tests Python 3.11 (min) and 3.13 (max) for fast feedback
- ✅ Tests both packages and examples
- ✅ Installs system dependencies (libmagic, poppler-utils)
- ✅ Uses uv workspace setup
- ✅ No API keys required (examples are smoke-tested)

### 🔍 `test-examples.yml` - Extended Example Testing
**Triggers:** Pushes to `main` branch
**Paths:** `examples/**, tests/**, packages/**`

**Jobs:**
1. **Extended Testing**:
   - Tests across all supported Python versions (3.11, 3.12, 3.13)
   - Comprehensive example testing
   - Mock API key testing

2. **Real API Testing** (if secrets available):
   - Tests with real API keys
   - Limited to getting-started examples
   - Only runs on main branch with secrets

**Key Features:**
- ✅ Extended testing after PR merge
- ✅ Full Python version matrix (3.11, 3.12, 3.13)
- ✅ Real API integration testing
- ✅ System dependencies included

### 🚀 Release Workflows
- `release-tyler.yml` - Tyler package releases
- `release-lye.yml` - Lye package releases  
- `release-narrator.yml` - Narrator package releases
- `release-space-monkey.yml` - Space Monkey package releases

## Workflow Strategy

### PR Testing (test.yml)
```
PR Created → Package Tests (3.11, 3.13) → Integration Tests → Examples Tests → ✅ Ready to Merge
```
- **Optimized for speed**: Tests minimum (3.11) and maximum (3.13) versions only
- **Fast feedback**: 33% fewer jobs than full matrix testing
- **Quality maintained**: Boundary testing catches most compatibility issues

### Post-Merge Testing (test-examples.yml)
```
Merge to Main → Extended Example Tests (3.11, 3.12, 3.13) → API Integration Tests → ✅ Verified
```
- **Comprehensive coverage**: Full Python version matrix
- **Safety net**: Catches any edge cases in Python 3.12
- **Real-world validation**: Tests with actual API integrations

## Example Test Strategy

### 🔒 **Smoke Tests** (Always Run)
- Directory structure validation
- Import testing (with libmagic dependency handling)
- No API keys required
- Fast execution (< 30 seconds)

### 🧪 **Integration Tests** (PR + Main)
- Basic package functionality
- Cross-package imports
- System dependency testing
- Mock API usage

### 🌐 **API Tests** (Main Branch Only)
- Real API integration
- Limited example subset
- Requires repository secrets
- Comprehensive functionality testing

## System Dependencies

All workflows install required system dependencies:
```bash
sudo apt-get update
sudo apt-get install -y libmagic1 poppler-utils
```

This ensures:
- ✅ File type detection works (narrator attachments)
- ✅ PDF processing works (lye tools)
- ✅ Examples can run properly

## Configuration Consistency

All workflows use:
- **uv**: v4 with caching enabled
- **Python**: setup-python@v5
- **Ubuntu**: latest LTS
- **Dependencies**: Workspace `uv sync --dev`

## Adding New Examples

When adding new examples:

1. **Automatic Testing**: Examples are automatically discovered and tested
2. **Skip Configuration**: Add to `tests/test_examples.py` skip lists if needed:
   ```python
   SKIP_EXAMPLES = ["problematic-example.py"]  # Skips from all tests
   SKIP_IMPORT_TESTS = ["import-issue.py"]     # Skips from import tests only
   ```
3. **API Requirements**: Add to `REQUIRES_API_KEY` list if API key needed

## Troubleshooting

### Common Issues

**libmagic errors:**
- System dependency automatically installed in CI
- Examples with issues are automatically skipped

**API key errors:**
- Expected in PR testing (examples are smoke-tested)
- Real API testing only happens on main branch

**Import errors:**
- Check `SKIP_IMPORT_TESTS` configuration
- Verify uv workspace setup

### Testing Locally

```bash
# Test like PR
uv run python tests/run_examples.py --smoke

# Test like main branch
uv run python tests/run_examples.py --no-api-key

# Test with real API
export OPENAI_API_KEY="sk-..."
uv run python tests/run_examples.py --category getting-started
```