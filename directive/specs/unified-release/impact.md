# Impact Analysis — Unified Monorepo Release Process

## Modules/packages likely touched

### Package Metadata (Version Synchronization)
All packages must be updated to synchronized version `2.2.0`:
- `/packages/tyler/pyproject.toml` - Update version from `2.1.0` to `2.2.0`
- `/packages/tyler/tyler/__init__.py` - Update `__version__` from `2.1.0` to `2.2.0`
- `/packages/narrator/pyproject.toml` - Update version from `1.0.2` to `2.2.0`
- `/packages/narrator/narrator/__init__.py` - Update `__version__` from `1.0.2` to `2.2.0`
- `/packages/space-monkey/pyproject.toml` - Update version from `1.0.0` to `2.2.0`
- `/packages/space-monkey/space_monkey/__init__.py` - Update `__version__` from `1.0.0` to `2.2.0`
- `/packages/lye/pyproject.toml` - Update version from `1.0.1` to `2.2.0`
- `/packages/lye/lye/__init__.py` - Update `__version__` from `1.0.1` to `2.2.0`

### Inter-Package Dependencies (Remove Version Constraints)
- `/packages/tyler/pyproject.toml` - Remove version constraints from `slide-narrator` and `slide-lye` dependencies
  - Current: `slide-narrator>=1.0.2`, `slide-lye>=1.0.1`
  - New: `slide-narrator`, `slide-lye` (no constraints, workspace references in dev)
- `/packages/space-monkey/pyproject.toml` - Remove version constraints from `slide-tyler` and `slide-narrator`
  - Current: `slide-tyler>=2.1.0`, `slide-narrator>=1.0.2`
  - New: `slide-tyler`, `slide-narrator` (no constraints)

### Release Scripts (Unified Approach)
- `/scripts/release.sh` - **MAJOR REWRITE**
  - From: Single package release (4 separate branches/PRs)
  - To: All packages release (1 unified branch/PR)
  - New functionality:
    - Bump version in all 4 packages simultaneously
    - Update all `__init__.py` files
    - Remove inter-package version constraints
    - Create single release branch `release/v2.2.0`
    - Create single PR with all changes

- `/scripts/release-all.sh` - **DEPRECATED/REMOVED**
  - No longer needed (functionality absorbed into `release.sh`)

- `/scripts/bump_version.py` - **MODIFY**
  - Add new mode: `--all-packages` flag to bump all packages together
  - Keep existing single-package mode for compatibility (but won't be used in normal workflow)

- `/scripts/update_dependent_constraints.py` - **DEPRECATED/REMOVED**
  - No longer needed (packages don't have version constraints on each other)

### GitHub Actions Workflows (Consolidation)
- `/.github/workflows/release-tyler.yml` - **REMOVE**
- `/.github/workflows/release-narrator.yml` - **REMOVE**
- `/.github/workflows/release-space-monkey.yml` - **REMOVE**
- `/.github/workflows/release-lye.yml` - **REMOVE**
- `/.github/workflows/release.yml` - **CREATE NEW**
  - Single unified workflow triggered by merged PRs matching `release/v*`
  - Creates 4 tags: `tyler-v2.2.0`, `narrator-v2.2.0`, `space-monkey-v2.2.0`, `lye-v2.2.0`
  - Builds all 4 packages
  - Publishes all 4 packages to PyPI
  - Creates 4 separate GitHub releases

### Documentation
- `/scripts/README.md` - Update to document new unified release process
- Root `/README.md` - Update if it mentions release process
- Could add: `/directive/specs/unified-release/MIGRATION.md` - Document transition plan

### Changelog Files (Create New)
- `/packages/tyler/CHANGELOG.md` - **CREATE**
- `/packages/narrator/CHANGELOG.md` - **CREATE**
- `/packages/space-monkey/CHANGELOG.md` - **CREATE**
- `/packages/lye/CHANGELOG.md` - **CREATE**

## Contracts to update (APIs, events, schemas, migrations)

### PyPI Package Dependencies
**Breaking Change Classification**: This is a **major change** requiring a coordinated release

#### Inter-Package Dependency Changes
**Before:**
```toml
# packages/tyler/pyproject.toml
dependencies = [
    "slide-narrator>=1.0.2",
    "slide-lye>=1.0.1",
]

# packages/space-monkey/pyproject.toml
dependencies = [
    "slide-tyler>=2.1.0",
    "slide-narrator>=1.0.2",
]
```

**After:**
```toml
# packages/tyler/pyproject.toml
dependencies = [
    "slide-narrator",
    "slide-lye",
]

# packages/space-monkey/pyproject.toml
dependencies = [
    "slide-tyler",
    "slide-narrator",
]
```

**Impact:**
- Users installing packages will always get the latest compatible versions
- Package managers will resolve to the highest available version
- No more "constraint conflicts" between Slide packages
- Users can no longer pin to specific inter-package version combinations

**Compatibility Guarantee:**
- All packages with the same synchronized version (e.g., v2.2.0) are guaranteed compatible
- Installing different versions of Slide packages together is no longer officially supported (though may still work)

### Git Tagging Convention
**No Breaking Change** - maintains existing convention:
- Tags remain per-package: `tyler-v2.2.0`, `narrator-v2.2.0`, etc.
- New pattern: All package tags from same release share version number
- Historical tags preserved (e.g., `tyler-v2.1.0` still exists)

### GitHub Release Structure
**No Breaking Change** - maintains separate releases:
- Four individual releases created per unified release
- Each release tagged with package-specific tag
- Each release contains package-specific changelog
- New: All releases from same PR share version number

### Release Branch Naming
**Breaking Change:**
- **Old**: `release/tyler-v2.1.0`, `release/narrator-v1.0.2`, etc.
- **New**: `release/v2.2.0` (no package name, applies to all)
- **Impact**: Old release branch patterns will no longer trigger workflows

## Risks

### Security
**Risk Level**: Low

**Potential Issues:**
1. **PyPI Token Exposure**: Unified workflow publishes all packages with single token
   - **Current**: 4 separate workflows (implicit separation)
   - **New**: 1 workflow with access to publish all packages
   - **Impact**: Single point of failure if workflow is compromised
   - **Mitigation**: 
     - Use GitHub environment secrets with protection rules
     - Require manual approval for releases (optional)
     - Review workflow carefully for any secret leakage

2. **Supply Chain**: Failed publish in middle of release could create confusion
   - **Impact**: Some packages at new version, others at old version
   - **Mitigation**: Document rollback procedure, ensure atomic-as-possible releases

**Overall Assessment**: Minimal security impact, standard monorepo practices apply

### Performance/Availability
**Risk Level**: Low

**Potential Issues:**
1. **CI/CD Duration**: Single workflow doing all package builds may take longer
   - **Current**: 4 parallel workflows (each ~3-5 minutes)
   - **New**: 1 workflow doing 4 packages sequentially (~12-20 minutes) OR in parallel (~5-7 minutes with matrix)
   - **Impact**: Release time may increase if sequential
   - **Mitigation**: Use job matrix to parallelize package builds

2. **PyPI Rate Limits**: Publishing 4 packages in rapid succession
   - **Impact**: May hit rate limits (unlikely but possible)
   - **Mitigation**: Add small delays between publishes if needed

3. **GitHub Actions Minutes**: Consolidating reduces workflow overhead
   - **Benefit**: Actually reduces overall CI time (less setup/teardown)

### Data integrity
**Risk Level**: None
- No database changes
- No data migrations
- File-only changes

### Version Compatibility
**Risk Level**: Medium-High (transition period only)

**Critical Compatibility Issues:**

1. **First Unified Release (2.1.0 → 2.2.0 transition)**
   - **Tyler**: Version jump from 2.1.0 to 2.2.0 (normal minor bump)
   - **Narrator**: Version jump from 1.0.2 to 2.2.0 (appears major, but is minor)
   - **Space Monkey**: Version jump from 1.0.0 to 2.2.0 (appears major, but is minor)
   - **Lye**: Version jump from 1.0.1 to 2.2.0 (appears major, but is minor)
   - **Perception Risk**: Users may think major breaking changes occurred
   - **Mitigation**: 
     - Clear release notes explaining version synchronization
     - Document as "packaging change, no API changes"
     - Consider if actual breaking changes warrant it

2. **Users with Pinned Versions**
   ```toml
   # User's pyproject.toml
   dependencies = [
       "slide-tyler==2.1.0",
       "slide-narrator==1.0.2",
   ]
   ```
   - **Impact**: Won't automatically upgrade
   - **Mitigation**: Document upgrade path in release notes

3. **Existing Projects with Old Constraints**
   ```toml
   # Old projects may have
   dependencies = [
       "slide-tyler>=2.0.0,<3.0.0",
   ]
   ```
   - **Impact**: Will work fine (2.2.0 fits in range)
   - **No action needed**

4. **Dependency Resolution During Transition**
   - **Scenario**: User has tyler 2.2.0 (no constraints) but installs old narrator 1.0.2
   - **Impact**: May install incompatible combination
   - **Mitigation**: 
     - First release (2.2.0) should maintain backward compatibility
     - Release notes emphasize installing all packages together
     - Consider adding version constraints temporarily for first release only

### Release Process Risk
**Risk Level**: Medium (first release), Low (subsequent releases)

**First Unified Release Risks:**
1. **Tooling Untested**: New scripts and workflow never run in production
   - **Mitigation**: 
     - Thorough testing on test repository first
     - Manual dry-run before actual release
     - Have rollback plan ready

2. **PyPI Publish Failure Scenarios:**
   - Scenario A: Tyler publishes, Narrator fails
     - **Impact**: Inconsistent state, some packages at new version
     - **Recovery**: Manually publish remaining packages, or roll forward with patch
   
   - Scenario B: Network error mid-workflow
     - **Impact**: Partial release
     - **Recovery**: Workflow can be re-run (PyPI handles duplicate publishes gracefully)

3. **Git Tag Cleanup**: If release fails, may need to delete tags
   - **Impact**: Manual cleanup required
   - **Mitigation**: Document tag cleanup process

### Documentation Drift
**Risk Level**: Low
- **Issue**: README and docs may reference old release process
- **Mitigation**: Update all documentation as part of TDR implementation

## Observability needs

### Logs

**Required Logging:**
1. **Release Script Logs**
   - Version bump operations for each package
   - Git operations (branch creation, commits, push)
   - PR creation status
   - Log file: Could output to console and optionally save to `release-{version}.log`

2. **GitHub Actions Workflow Logs**
   - Package build status (per package)
   - Tag creation (per package)
   - PyPI publish status (per package)
   - GitHub release creation (per package)
   - Use `::group::` and `::endgroup::` for better organization
   - Use `::notice::` for important milestones

**Example Workflow Logging:**
```yaml
- name: Build Tyler
  run: |
    echo "::group::Building Tyler"
    cd packages/tyler
    uv tool run hatch build
    echo "::endgroup::"
    echo "::notice::Tyler built successfully"
```

### Metrics

**Recommended Metrics to Track:**
1. **Release Success Rate**
   - Track via GitHub Actions workflow status
   - Goal: >95% success rate after stabilization

2. **Release Duration**
   - Time from PR merge to all packages published
   - Baseline: Measure first few releases
   - Goal: <15 minutes end-to-end

3. **Package Publish Failures**
   - Count failures per package
   - Identify if specific packages are problematic

4. **Version Drift Detection**
   - Automated check that all packages have same version
   - Part of CI to prevent accidental desynchronization

**Implementation:**
- GitHub Actions provides built-in metrics
- Could add custom metrics via workflow_run events if needed

### Alerts

**Critical Alerts Needed:**
1. **Release Workflow Failure**
   - **Trigger**: Unified release workflow fails
   - **Channel**: GitHub notifications (automatic), Slack (if integrated)
   - **Action**: Immediate investigation, may need manual intervention
   - **Implementation**: GitHub Actions built-in notifications

2. **PyPI Publish Failure**
   - **Trigger**: Any package fails to publish
   - **Channel**: Workflow status, email notification
   - **Action**: Manual publish or rollback decision
   - **Implementation**: Workflow failure status

3. **Version Mismatch Detected**
   - **Trigger**: CI detects packages with different versions
   - **Channel**: PR comments, workflow failure
   - **Action**: Fix before merge
   - **Implementation**: Add pre-commit or CI check

**Nice-to-Have Alerts:**
- Release took longer than expected (>20 minutes)
- Tag creation succeeded but publish failed (inconsistent state)

## Verification Plan

### Pre-Implementation Testing

1. **Test on Fork/Branch First**
   ```bash
   # Create test repository or use branch
   # Test new release script without actually publishing
   ./scripts/release.sh patch --dry-run
   ```

2. **Test Version Bump Logic**
   ```bash
   # Verify all packages get updated correctly
   python scripts/bump_version.py --all-packages patch --dry-run
   # Check output versions match
   ```

3. **Test Workflow Locally** (using act or manual testing)
   ```bash
   # Install act (GitHub Actions local runner)
   brew install act
   # Test workflow locally
   act -j publish-all -W .github/workflows/release.yml
   ```

### First Unified Release (v2.2.0) Checklist

**Pre-Release:**
- [ ] All new scripts tested in dry-run mode
- [ ] New workflow tested on test repository
- [ ] All 4 packages currently at expected versions (tyler: 2.1.0, others: 1.0.x)
- [ ] CHANGELOG.md files created for all packages
- [ ] Documentation updated to reference new process

**During Release:**
- [ ] Run new release script: `./scripts/release.sh minor`
- [ ] Verify PR contains all 4 package updates
- [ ] Verify inter-package constraints are removed
- [ ] Verify all versions are 2.2.0
- [ ] Review and merge PR

**Post-Merge Monitoring:**
- [ ] Watch workflow progress in GitHub Actions
- [ ] Verify 4 tags created: `tyler-v2.2.0`, `narrator-v2.2.0`, `space-monkey-v2.2.0`, `lye-v2.2.0`
- [ ] Verify all 4 packages published to PyPI
- [ ] Verify 4 GitHub releases created
- [ ] Test installation: `pip install slide-tyler==2.2.0 slide-narrator==2.2.0`

### Subsequent Release Testing

After first release succeeds, verify:
```bash
# Create next release to validate repeatability
./scripts/release.sh patch  # Should create v2.2.1

# Verify:
# - All versions bump together
# - Process completes smoothly
# - No manual intervention needed
```

### Rollback Procedure

If release fails mid-process:

1. **If workflow fails before PyPI publish:**
   ```bash
   # Delete tags
   git tag -d tyler-v2.2.0 narrator-v2.2.0 space-monkey-v2.2.0 lye-v2.2.0
   git push --delete origin tyler-v2.2.0 narrator-v2.2.0 space-monkey-v2.2.0 lye-v2.2.0
   # Delete GitHub releases (via UI or API)
   # Retry or debug
   ```

2. **If some packages published to PyPI:**
   - Cannot remove from PyPI (only yank)
   - Roll forward: Fix issue and republish remaining packages manually
   - Document the incident for process improvement

3. **If all published but issues found:**
   - Yank the releases on PyPI (makes them uninstallable by default)
   - Release a patch version (e.g., v2.2.1) with fixes
   - Update release notes to indicate v2.2.0 was yanked

## Release Coordination

### First Unified Release (v2.2.0)

**Version Bumps:**
- `slide-tyler`: 2.1.0 → 2.2.0 (minor - significant release process change)
- `slide-narrator`: 1.0.2 → 2.2.0 (appears major, actually minor - version sync)
- `slide-space-monkey`: 1.0.0 → 2.2.0 (appears major, actually minor - version sync)
- `slide-lye`: 1.0.1 → 2.2.0 (appears major, actually minor - version sync)

**Rationale for 2.2.0:**
- Tyler is the "lead" package at 2.1.0
- Unified release is a significant change warranting minor bump
- Brings all packages to same major version (2.x)

### Release Notes Template

Each package's CHANGELOG.md should include:

```markdown
# Changelog

## [2.2.0] - YYYY-MM-DD

### Changed
- **BREAKING PACKAGING CHANGE**: Slide now uses synchronized versioning across all packages
- All Slide packages released together now share the same version number
- Removed version constraints from inter-package dependencies
- All packages with version 2.2.0 are guaranteed compatible with each other

### Migration Guide
If upgrading from previous versions:
- Update all Slide packages together: `pip install --upgrade slide-tyler slide-narrator slide-space-monkey slide-lye`
- No code changes required - this is a packaging change only
- Inter-package version constraints are no longer needed

### Note for Maintainers
This release transitions to unified monorepo releases. All future releases will bump all packages together.

---

## Previous Versions
[Link to historical releases if applicable]
```

### Communication Plan

**Announce via:**
1. **GitHub Release Notes**: Detailed explanation in each package release
2. **README Updates**: Note about synchronized versioning
3. **Documentation**: Update release process docs
4. **Discord/Slack** (if applicable): Announce the change
5. **PyPI Description**: Update if mentioning version strategy

**Key Messages:**
- "Simplified release process for better compatibility"
- "All packages at same version are guaranteed compatible"
- "No code changes - packaging change only"
- "Update all Slide packages together going forward"

### Coordination with Other Features

**Before Implementing Unified Release:**
- Complete any in-flight releases using old process
- Merge any pending PRs that affect package versions
- Coordinate with team to pause individual package releases

**After Implementing:**
- All future releases use unified process
- Document the change in team knowledge base
- Update contributor guidelines if applicable

