# Spec (per PR)

**Feature name**: Preserve Minimum Version Constraints in Release Script  
**One-line summary**: Release script should preserve minimum version constraints while removing upper bounds to prevent incompatible package combinations

---

## Problem

The unified release script (`scripts/release.sh`) currently removes **all** inter-package version constraints during the release process. This creates compatibility issues:

1. **Bug Discovered**: Tyler 3.1.0 requires narrator 3.1.0+ (for `reasoning_content` field support), but the release script removed the minimum version constraint
2. **User Impact**: Users can install Tyler 3.1.0 with an older narrator (e.g., 1.0.2), causing runtime errors: `"Extra inputs are not permitted"` Pydantic validation error
3. **Root Cause**: Lines 119-145 of the release script strip ALL version constraints (e.g., `"slide-narrator>=3.1.0"` → `"slide-narrator"`)

**Why now?**
- We just released 3.1.0 with this bug affecting production users
- We're about to release 3.1.1 as a patch, but the release script will reintroduce the same bug
- This pattern will create recurring compatibility issues as packages evolve

## Goal

The release script should automatically set minimum version constraints to match the current release version for all inter-package dependencies, ensuring packages released together are guaranteed compatible.

## Success Criteria
- [x] Users installing Tyler 3.1.1+ will automatically get narrator 3.1.0+ (enforced by minimum constraint)
- [x] Release script no longer removes minimum version requirements from inter-package dependencies
- [x] Existing releases (3.1.0+) remain functional with proper dependency resolution

## User Story

As a **package maintainer**, I want the release script to preserve minimum version constraints, so that users installing one package automatically get compatible versions of dependent packages and don't encounter runtime compatibility errors.

## Flow / States

**Happy Path:**
1. Developer runs `./scripts/release.sh patch` (current version 3.1.0)
2. Script bumps versions to 3.1.1 for all packages
3. Script automatically sets inter-package constraints to `>=3.1.1`:
   - Tyler: `"slide-narrator>=3.1.1"`, `"slide-lye>=3.1.1"`
   - Space-monkey: `"slide-tyler>=3.1.1"`, `"slide-narrator>=3.1.1"`
4. PR is created and merged
5. User installs `pip install slide-tyler==3.1.1`
6. Pip automatically installs compatible versions: narrator>=3.1.1, lye>=3.1.1

**Edge Case - Future Version Compatible:**
1. User has narrator 3.2.0 installed
2. User installs tyler 3.1.1
3. Tyler requires narrator>=3.1.1 (satisfied by 3.2.0)
4. Installation succeeds without downgrading narrator

## UX Links

N/A - This is an internal developer tooling improvement

## Requirements

**Must:**
- Automatically set minimum version constraints to `>=NEW_VERSION` for all inter-package dependencies during release
- Work for all inter-package dependencies: tyler→narrator, tyler→lye, space-monkey→tyler, space-monkey→narrator
- Handle any existing constraint format (no constraint, `>=X.Y.Z`, or exact pins)
- Ensure released packages always require compatible versions of dependencies

**Must not:**
- Break the existing unified release workflow
- Introduce version conflicts that prevent package installation  
- Require manual version constraint management by developers
- Set constraints on external (non-Slide) packages

## Acceptance Criteria

**AC1: Auto-set minimum version constraints for Tyler dependencies**
- Given: Release script runs for version 3.1.1
- When: Processing Tyler's pyproject.toml
- Then: `"slide-narrator"` becomes `"slide-narrator>=3.1.1"`
- And: `"slide-lye"` becomes `"slide-lye>=3.1.1"`

**AC2: Auto-set minimum version constraints for Space-monkey dependencies**
- Given: Release script runs for version 3.1.1
- When: Processing Space-monkey's pyproject.toml
- Then: `"slide-tyler"` becomes `"slide-tyler>=3.1.1"`
- And: `"slide-narrator"` becomes `"slide-narrator>=3.1.1"`

**AC3: Handle existing constraints (override)**
- Given: Tyler has `"slide-narrator>=3.0.0"` from a previous release
- When: Release script runs for version 3.1.1
- Then: The constraint is updated to `"slide-narrator>=3.1.1"`

**AC4: Don't affect external dependencies**
- Given: Tyler has `"litellm>=1.63.0"` (external package)
- When: Release script runs
- Then: The external constraint remains `"litellm>=1.63.0"` unchanged

**AC5: Negative case - Old version installation prevented**
- Given: User tries to install Tyler 3.1.1 with narrator 3.0.0
- When: pip/uv resolves dependencies
- Then: Installation fails or narrator is upgraded to >=3.1.1
- Because: Tyler 3.1.1 requires narrator>=3.1.1

## Non-Goals

- Setting constraints for narrator or lye (they have no internal Slide dependencies)
- Backporting constraints to older released versions (only affects new releases going forward)
- Handling version constraints logic for external packages (those follow standard dependency rules)
- Supporting independent version releases (we maintain unified versioning across all Slide packages)

