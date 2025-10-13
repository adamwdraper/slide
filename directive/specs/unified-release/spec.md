# Spec: Unified Monorepo Release Process

**Feature name**: Unified Monorepo Release Process  
**One-line summary**: Simplify releases by synchronizing all package versions and using a single release branch/PR instead of separate releases per package  

---

## Problem

The current release process releases each package independently, which creates several pain points:

1. **Multiple release branches**: Each release requires 4 separate branches (`release/tyler-v2.1.0`, `release/narrator-v1.0.2`, etc.)
2. **Multiple PRs**: Each release requires reviewing and merging 4 separate PRs
3. **Complex dependency management**: When releasing a package that other packages depend on (e.g., narrator), we must:
   - First release the dependency (narrator)
   - Then update constraints in dependent packages (tyler, space-monkey)
   - Then release those packages
   - This creates a sequential release process
4. **Version drift**: Packages have different version numbers (tyler: v2.1.0, narrator: v1.0.2, space-monkey: v1.0.0, lye: v1.0.1), making it unclear which versions are compatible
5. **Maintenance overhead**: Four separate GitHub Actions workflows to maintain
6. **Cognitive load**: Developers must track "which version of X works with version Y of Z"

This complexity slows down releases and increases the risk of dependency mismatches.

## Goal

Create a unified release process where:
- All packages share synchronized version numbers
- A single release branch bumps all package versions together
- A single PR contains all version changes
- A single GitHub Actions workflow handles building and publishing all packages
- No need to manually manage cross-package dependency constraints

## Success Criteria

- [ ] Releasing all packages takes 1 PR instead of 4 PRs
- [ ] All packages maintain synchronized version numbers (e.g., all at v2.2.0)
- [ ] Dependencies between packages no longer specify version constraints (always compatible by default)
- [ ] Release time reduced by ~75% (from ~4 separate workflows to 1)
- [ ] No more sequential dependency releases needed

## User Story

As a Slide maintainer, I want to release all packages together with synchronized versions, so that I can ship features faster without managing complex dependency constraints and multiple release branches.

## Flow / States

**Happy Path - Unified Release:**
1. Developer runs `./scripts/release.sh patch` (or `minor`, `major`)
2. Script creates a single branch `release/v2.2.0`
3. Script bumps version in all 4 packages to `2.2.0`
4. Script updates `__init__.py` files in all packages
5. Script removes version constraints from inter-package dependencies
6. Script commits all changes and creates a single PR titled "Release v2.2.0"
7. PR is reviewed and merged to main
8. GitHub Actions workflow triggers on merge
9. Workflow creates 4 tags: `tyler-v2.2.0`, `narrator-v2.2.0`, `space-monkey-v2.2.0`, `lye-v2.2.0`
10. Workflow builds and publishes all 4 packages to PyPI
11. Workflow creates 4 separate GitHub releases with package-specific changelogs

**Edge Case - Failed PyPI Publish:**
1. Unified release workflow starts
2. Tyler publishes successfully to PyPI
3. Narrator publish fails (network error, auth issue, etc.)
4. Workflow marks the job as failed
5. Tags remain in git (can retry or rollback)
6. Maintainer investigates and re-runs workflow, or manually publishes remaining packages

## UX Links

- Current release script: `/scripts/release.sh`
- Current release-all script: `/scripts/release-all.sh`
- Current bump script: `/scripts/bump_version.py`
- Current constraint updater: `/scripts/update_dependent_constraints.py`
- Current workflows: `.github/workflows/release-*.yml` (4 files)

## Requirements

**Must:**
- Synchronize all package versions to the same number (starting at v2.2.0)
- Create a single unified release script that bumps all packages
- Create a single unified GitHub Actions workflow that publishes all packages
- Remove version constraints from inter-package dependencies in `pyproject.toml` files
- Create individual git tags per package (e.g., `tyler-v2.2.0`) for historical tracking
- Create individual GitHub releases per package with package-specific changelogs
- Preserve existing git tag history (don't remove old tags)
- Support `major`, `minor`, `patch` version bump types
- Create per-package CHANGELOGs if they don't exist
- Update CHANGELOGs as part of the release process

**Must not:**
- Break existing package consumers (semantic versioning still applies)
- Force a single GitHub release for all packages (keep them separate for clarity)
- Remove the ability to manually version individual packages (even though we won't use it regularly)
- Change PyPI package names

## Acceptance Criteria

**AC-1: Synchronized Version Numbers**
- Given all four packages (tyler, narrator, space-monkey, lye)
- When a unified release is performed
- Then all packages should have the same version number in their `pyproject.toml` and `__init__.py` files
- And the starting version should be v2.2.0 (next minor from tyler's current 2.1.0)

**AC-2: Single Release Script**
- Given a maintainer wants to create a release
- When they run `./scripts/release.sh patch` (or `minor`, `major`)
- Then a single branch `release/v2.2.0` is created
- And all four packages are updated to version 2.2.0
- And a single PR is created

**AC-3: No Inter-Package Version Constraints**
- Given packages with dependencies on other Slide packages
- When examining `pyproject.toml` files
- Then tyler should depend on `slide-narrator` and `slide-lye` without version constraints
- And space-monkey should depend on `slide-tyler` and `slide-narrator` without version constraints
- And packages should use workspace references in development

**AC-4: Single Unified Workflow**
- Given a release PR is merged
- When the GitHub Actions workflow triggers
- Then one workflow should handle all packages
- And create tags for all packages: `tyler-v2.2.0`, `narrator-v2.2.0`, `space-monkey-v2.2.0`, `lye-v2.2.0`
- And build and publish all packages to PyPI
- And create individual GitHub releases for each package

**AC-5: Individual GitHub Releases**
- Given the unified workflow completes successfully
- When viewing GitHub releases
- Then four separate releases should exist:
  - "Tyler v2.2.0"
  - "Narrator v2.2.0"
  - "Space Monkey v2.2.0"
  - "Lye v2.2.0"
- And each should have its own changelog/release notes

**AC-6: Per-Package CHANGELOGs**
- Given each package directory
- When a release is performed
- Then each package should have a `CHANGELOG.md` file
- And the changelog should be updated with version and changes

**AC-7: Backward Compatibility**
- Given existing git tags like `tyler-v2.1.0`
- When the new release process is implemented
- Then old tags remain accessible
- And new tags follow the same naming convention

**AC-8: Failed Publish Handling**
- Given the workflow is publishing packages
- When one package fails to publish to PyPI
- Then the workflow should fail clearly with an error message
- And tags should still exist for retry/debugging
- And successfully published packages remain published (no automatic rollback)

## Non-Goals

- Creating a meta-package that installs all Slide packages together
- Changing PyPI package names or structure
- Implementing automatic changelog generation from git commits (manual changelog updates are acceptable)
- Supporting selective package releases (all packages always released together)
- Implementing a canary or beta release process
- Creating a monolithic package (packages remain separate on PyPI)

