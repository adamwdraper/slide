# Unified Release Scripts

This directory contains unified release scripts for all slide packages (tyler, narrator, space-monkey).

## Usage

To create a release branch for any package:

```bash
# From the slide root directory
./scripts/release.sh <package> [version_type]
```

### Examples

```bash
# Patch release for narrator (1.0.0 -> 1.0.1)
./scripts/release.sh narrator patch

# Minor release for tyler (1.0.0 -> 1.1.0)
./scripts/release.sh tyler minor

# Major release for space-monkey (1.0.0 -> 2.0.0)
./scripts/release.sh space-monkey major
```

## What the script does

1. **Validates inputs** - checks package name and version type
2. **Creates a release branch** - named `release/<package>-v<NEW_VERSION>`
3. **Bumps the version** - updates both `pyproject.toml` and `<package>/__init__.py`
4. **Commits the changes** - creates a commit with the version bump
5. **Pushes the branch** - pushes the new release branch to origin
6. **Creates a PR** - automatically creates a GitHub pull request with the "release" label

## Requirements

- GitHub CLI (`gh`) must be installed and authenticated
- Must be run from the slide root directory
- Git must be on the `main` branch and up to date

## Available packages

- `tyler` - The main tyler package
- `narrator` - The narrator storage system
- `space-monkey` - The Slack agent framework

## Version types

- `patch` - Bug fixes (1.0.0 -> 1.0.1)
- `minor` - New features (1.0.0 -> 1.1.0)
- `major` - Breaking changes (1.0.0 -> 2.0.0)

## Migration from individual scripts

This replaces the individual release scripts that were previously located in:
- `packages/tyler/scripts/release.sh`
- `packages/narrator/scripts/release.sh`

Those scripts can now be removed to avoid duplication. 