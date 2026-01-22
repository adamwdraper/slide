# AGENTS.md

## Project Overview

Slide is a Python monorepo with 4 packages that use **synchronized versioning**:
- **tyler** (`slide-tyler`) - AI agent framework
- **narrator** (`slide-narrator`) - Thread/message storage
- **lye** (`slide-lye`) - Tools (web, files, Slack, browser, etc.)
- **space-monkey** (`slide-space-monkey`) - Slack integration

## Setup

```bash
# Install dependencies (uses uv workspaces)
uv sync --dev

# Add dependency to specific package
uv add --package tyler <dependency>
```

**Important**: Single `uv.lock` and `.venv` at root. Never create these in packages.

## Testing

```bash
# Test specific package
cd packages/tyler && uv run pytest tests/
cd packages/narrator && uv run pytest tests/
cd packages/lye && uv run pytest tests/
cd packages/space-monkey && uv run pytest tests/

# Smoke test examples
uv run python tests/run_examples.py --smoke
```

## Code Style

- Python 3.11+ required
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- TDD: Write failing test → Implement → Refactor
- Commit order: `test:` → `feat:` → `refactor:`
- Docstrings for all public functions/classes
- Secrets in env vars only, never hardcoded

## Feature Development

For new features, create these files **before writing code**:
1. `/directive/specs/<feature>/spec.md` - Requirements
2. `/directive/specs/<feature>/impact.md` - Impact analysis
3. `/directive/specs/<feature>/tdr.md` - Technical design

See `/directive/reference/agent_operating_procedure.md` for full workflow.

## Project Structure

```
slide/
├── packages/
│   ├── tyler/        # Agent framework
│   ├── narrator/     # Storage
│   ├── lye/          # Tools
│   └── space-monkey/ # Slack integration
├── examples/         # Cross-package examples
├── directive/        # Specs and agent guidance
│   ├── reference/    # Templates and context
│   └── specs/        # Feature specifications
└── scripts/          # Release scripts
```

## Running Examples

```bash
uv run examples/getting-started/quickstart.py
uv run packages/tyler/examples/001_basic.py
```

Requires `OPENAI_API_KEY` in `.env` or environment.

## Releases

All packages release together with the same version:
```bash
./scripts/release.sh patch  # Bug fixes
./scripts/release.sh minor  # New features
./scripts/release.sh major  # Breaking changes
```

## Key References

- `/directive/reference/agent_context.md` - Technical context
- `/directive/reference/agent_operating_procedure.md` - Development workflow
- `/.github/workflows/test.yml` - CI configuration
