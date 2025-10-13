# Unified Monorepo Release Process

**Status**: Approved - Ready for Implementation  
**Created**: 2025-10-13  

## Overview

This feature transitions Slide from independent per-package releases to a unified monorepo release process.

## Key Changes

### Before (Current)
- 4 separate release branches per release
- 4 separate PRs to review and merge
- 4 separate GitHub Actions workflows
- Manual version constraint updates between packages
- Versions out of sync: tyler 2.1.0, narrator 1.0.2, space-monkey 1.0.0, lye 1.0.1

### After (Unified)
- 1 release branch per release (`release/v2.2.0`)
- 1 PR with all package updates
- 1 consolidated GitHub Actions workflow
- No version constraints between packages (always compatible)
- All packages synchronized: all at v2.2.0

## Benefits

- **75% faster releases**: 1 PR instead of 4
- **No dependency conflicts**: Synchronized versions guarantee compatibility
- **Simplified process**: Less cognitive overhead for maintainers
- **Clear versioning**: "v2.2.0" means all packages are at 2.2.0 and compatible

## Technical Approach

### 1. Version Synchronization
All packages share the same version number at all times.

**Starting version**: v2.2.0 (next minor from tyler's current 2.1.0)

### 2. Unified Release Script
New `/scripts/release.sh` that:
- Bumps all 4 packages to the same version
- Removes inter-package version constraints
- Generates CHANGELOGs automatically with git-cliff
- Creates single release branch and PR

**Usage**:
```bash
./scripts/release.sh patch   # 2.2.0 → 2.2.1
./scripts/release.sh minor   # 2.2.0 → 2.3.0
./scripts/release.sh major   # 2.2.0 → 3.0.0
```

### 3. Automated Changelog Generation
Uses [git-cliff](https://git-cliff.org/) to generate CHANGELOGs from conventional commits.

**Why git-cliff**:
- Fast (Rust-based)
- Monorepo support (filter by package paths)
- Parses conventional commits (feat:, fix:, chore:, docs:)
- Zero config to start

**Installation**:
```bash
brew install git-cliff
```

**How it works**:
```bash
# Automatically generates package-specific changelog
git cliff --include-path "packages/tyler/**" \
    --tag "tyler-v2.2.0" \
    --output packages/tyler/CHANGELOG.md
```

### 4. Consolidated Workflow
Single `.github/workflows/release.yml` that:
- Verifies all packages at same version
- Creates 4 tags: `tyler-v2.2.0`, `narrator-v2.2.0`, etc.
- Builds all packages
- Publishes all packages to PyPI
- Creates 4 separate GitHub releases

### 5. Simplified Dependencies
**Before**:
```toml
dependencies = ["slide-narrator>=1.0.2"]
```

**After**:
```toml
dependencies = ["slide-narrator"]  # No constraints
```

## Prerequisites

1. **GitHub CLI**: `brew install gh`
2. **git-cliff**: `brew install git-cliff`

## Documents

- **[spec.md](spec.md)**: Full specification with acceptance criteria
- **[impact.md](impact.md)**: Impact analysis with risks and mitigation
- **[tdr.md](tdr.md)**: Technical design with implementation details

## Implementation Plan

### Phase 1: Preparation (1-2 days)
- Complete in-flight releases
- Merge pending PRs
- Team coordination

### Phase 2: Implementation (2-3 hours)
- Update release script
- Create unified workflow
- Remove old workflows
- Update documentation

### Phase 3: First Release (30 min)
- Execute `./scripts/release.sh minor`
- Review and merge PR
- Monitor workflow
- Verify packages published

### Phase 4: Validation (1 week)
- Execute second release
- Verify repeatability
- Gather feedback

## Rollback Plan

If unified release needs to be reverted:
1. Restore old workflow files from git history
2. Restore old release scripts
3. Add version constraints back to dependencies
4. Release patch versions using old process

## Success Metrics

- Release PR count: 4 → 1 ✅
- Release time: 12-20 min → 3-5 min ✅
- Version synchronization: 100% ✅
- Team satisfaction: Simpler process ✅

## Questions?

See the full TDR for detailed implementation guidance, or contact the team.

