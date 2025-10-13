# Unified Release Script

This directory contains the unified release script for all Slide packages (tyler, narrator, space-monkey, lye).

## Overview

The Slide monorepo uses **synchronized versioning** - all packages share the same version number and are released together. This ensures compatibility and simplifies dependency management.

## Prerequisites

Before running releases, install the required tools:

```bash
brew install gh          # GitHub CLI
brew install git-cliff   # Changelog generator
```

## Usage

```bash
# From the slide root directory
./scripts/release.sh [version_type]
```

**Version types:**
- `patch` - Bug fixes (2.1.0 → 2.1.1)
- `minor` - New features (2.1.0 → 2.2.0)
- `major` - Breaking changes (2.1.0 → 3.0.0)

**Default**: `patch` if not specified

## Examples

```bash
# Create a patch release (bug fixes)
./scripts/release.sh patch

# Create a minor release (new features)
./scripts/release.sh minor

# Create a major release (breaking changes)
./scripts/release.sh major
```

## What the Script Does

1. **Validates environment** - Ensures you're on main branch with no uncommitted changes
2. **Bumps versions** - Updates all 4 packages to the same new version
3. **Removes version constraints** - Clears inter-package version requirements
4. **Generates CHANGELOGs** - Auto-generates from conventional commits using git-cliff
5. **Creates release branch** - Named `release/v<VERSION>`
6. **Commits changes** - All version bumps and changelog updates
7. **Pushes to GitHub** - Pushes the release branch
8. **Creates PR** - Automatically creates a pull request with "release" label

## After Merging the Release PR

Once the release PR is merged to `main`, the unified release workflow automatically:

1. **Creates git tags** - One for each package:
   - `tyler-v2.2.0`
   - `narrator-v2.2.0`
   - `space-monkey-v2.2.0`
   - `lye-v2.2.0`

2. **Builds packages** - All 4 packages built with hatch

3. **Publishes to PyPI** - All packages published automatically

4. **Creates GitHub releases** - Individual releases for each package with changelogs

## Synchronized Versioning

**Key Points:**
- All packages always have the same version number
- Releasing means bumping ALL packages, even if some have no changes
- Packages at the same version are guaranteed compatible
- No version constraints between internal packages (e.g., `slide-tyler` depends on `slide-narrator` without a version requirement)

**Example:**
```toml
# Tyler's dependencies (no version constraints on internal packages)
dependencies = [
    "slide-narrator",  # No version constraint!
    "slide-lye",       # No version constraint!
    "litellm>=1.60.2", # External packages still have constraints
]
```

## Changelog Generation

Changelogs are automatically generated from git commit messages using **conventional commits**:

```bash
feat: add new streaming mode      # → Features section
fix: handle auth errors            # → Bug Fixes section
docs: update streaming guide       # → Documentation section
chore: bump dependencies          # → Chores section
```

**Best Practice:** Use conventional commit format for automatic changelog generation.

## Available Packages

All packages are released together:
- **tyler** - AI agent development kit
- **narrator** - Thread and message storage system
- **space-monkey** - Slack agent framework
- **lye** - Tools package for Tyler

## Troubleshooting

### "GitHub CLI (gh) required"
```bash
brew install gh
gh auth login
```

### "git-cliff required"
```bash
brew install git-cliff
```

### "Uncommitted changes detected"
```bash
git status
git add <files>
git commit -m "your message"
# or
git stash
```

### "Not on main branch"
```bash
git checkout main
git pull origin main
```

## Migration from Old Process

### Removed Scripts
- ❌ `scripts/release-all.sh` (no longer needed)
- ❌ `scripts/update_dependent_constraints.py` (no longer needed)

### Removed Workflows
- ❌ `.github/workflows/release-tyler.yml` (replaced by unified workflow)
- ❌ `.github/workflows/release-narrator.yml` (replaced by unified workflow)
- ❌ `.github/workflows/release-space-monkey.yml` (replaced by unified workflow)
- ❌ `.github/workflows/release-lye.yml` (replaced by unified workflow)

### New Files
- ✅ `.github/workflows/release.yml` (unified workflow for all packages)

## More Information

See `/directive/specs/unified-release/` for:
- Complete specification (spec.md)
- Impact analysis (impact.md)
- Technical design record (tdr.md)
- Implementation guide (README.md)
