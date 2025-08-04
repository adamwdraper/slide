# Development Guide for Slide Examples

This guide shows how to work with Slide examples using the uv workspace setup.

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd slide

# 2. Setup workspace (installs all packages in dev mode)
uv sync --dev

# 3. Set API key
export OPENAI_API_KEY="sk-..."

# 4. Run an example
uv run examples/getting-started/quickstart.py
```

## Project Structure

This is a **uv workspace** containing multiple packages:

```
slide/
├── pyproject.toml          # Workspace configuration
├── uv.lock                 # Single lock file for all packages
├── .venv/                  # Single virtual environment
├── examples/               # ✨ Project-level examples
│   ├── getting-started/    # Simple cross-package examples
│   ├── use-cases/         # Real-world applications
│   └── integrations/      # Advanced patterns
├── packages/              # Individual packages
│   ├── tyler/             # Agent framework
│   ├── lye/               # Tools and capabilities
│   ├── narrator/          # Storage and persistence
│   └── space-monkey/      # Slack integration
└── tests/                 # Project-level tests
```

## Running Examples

### Using uv (Recommended)

```bash
# From project root - uv automatically finds the right dependencies
uv run examples/getting-started/quickstart.py
uv run examples/use-cases/research-assistant/basic.py
uv run examples/integrations/cross-package.py
```

### Using python (After uv sync)

```bash
# After running uv sync --dev, you can also use python directly
python examples/getting-started/quickstart.py
```

## Testing Examples

### Test All Examples

```bash
# Run all example tests
uv run pytest tests/test_examples.py

# Or use the test runner
uv run python tests/run_examples.py
```

### Quick Tests (No API Key Required)

```bash
# Smoke tests - just check imports and structure
uv run python tests/run_examples.py --smoke
```

### Test by Category

```bash
# Test specific categories
uv run python tests/run_examples.py --category getting-started
uv run python tests/run_examples.py --category use-cases
uv run python tests/run_examples.py --category integrations
```

### Test Specific Example

```bash
# Test one example
uv run python tests/run_examples.py --example quickstart.py
uv run python tests/run_examples.py --example research-assistant/basic.py
```

## Development Workflow

### Adding New Examples

1. **Create the example file** in the appropriate directory:
   ```bash
   # Getting started example
   touch examples/getting-started/my-example.py
   
   # Use case example
   mkdir examples/use-cases/my-use-case
   touch examples/use-cases/my-use-case/basic.py
   ```

2. **Follow the existing patterns**:
   - Import from tyler, lye, narrator as needed
   - Add proper error handling and setup instructions
   - Include helpful print statements for user guidance

3. **Test your example**:
   ```bash
   # Test it runs
   uv run examples/getting-started/my-example.py
   
   # Test it passes automated tests
   uv run python tests/run_examples.py --example my-example.py
   ```

### Package Development

When working on the packages themselves:

```bash
# Make changes to packages/tyler/... 
# Changes are immediately available to examples (no reinstall needed)

# Test that examples still work
uv run python tests/run_examples.py --category getting-started

# Run package-specific tests  
uv run --package tyler pytest
uv run --package lye pytest
```

### Adding Dependencies

```bash
# Add to workspace dev dependencies (for testing)
uv add --dev new-test-package

# Add to specific package
uv add --package tyler new-dependency
uv add --package lye new-tool-dependency
```

## Environment Setup

### Required Environment Variables

```bash
# At least one LLM API key
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# For Slack examples
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
```

### Optional Environment Variables

```bash  
# For Weave tracing
export WANDB_API_KEY="..."

# For specific bot types
export BOT_TYPE="research"  # or "assistant" or "support"
```

## Troubleshooting

### Common Issues

**"No module named 'slide-tyler'"**
```bash
# Solution: Sync the workspace
uv sync --dev
```

**"No API key found" errors**
```bash
# Solution: Set at least one API key
export OPENAI_API_KEY="sk-..."
```

**"libmagic" errors in tests**
```bash
# This is expected in some environments
# Affected examples are automatically skipped in tests
uv run python tests/run_examples.py --smoke  # Works around this
```

**Examples seem to use old code**
```bash
# In uv workspace, changes to packages are immediate
# But if you have issues, try:
uv sync --dev
```

### Debugging

```bash  
# Verbose test output
uv run python tests/run_examples.py --verbose

# List all available examples
uv run python tests/run_examples.py --list

# Check workspace status
uv tree
```

## CI/CD

Examples are automatically tested in GitHub Actions:

- **Smoke tests** run on every PR (no API key needed)
- **Import tests** verify all examples can be imported
- **Structure tests** check directory organization
- **Full tests** run on main branch with API keys (if available)

The testing is designed to be robust and skip examples that require external services or special setup.

## Best Practices

1. **Use `uv run`** for consistency
2. **Test your examples** before committing
3. **Add helpful error messages** when API keys are missing
4. **Follow existing patterns** for imports and structure
5. **Keep examples focused** - one concept per example
6. **Add README files** for complex use cases
7. **Use relative imports** when importing from slide packages