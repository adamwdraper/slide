# Testing & Rollout Plan - Unified Release Process

## Pre-Merge Validation ✅ COMPLETED

### Automated Tests
Run: `./test_release_process.sh`

**Results**: All 42 checks passed
- ✅ Prerequisites installed (gh, git-cliff, uv)
- ✅ Release script syntax valid
- ✅ GitHub Actions workflow structure correct
- ✅ Package versions readable
- ✅ Version bump logic correct
- ✅ git-cliff changelog generation works
- ✅ Inter-package dependencies have no constraints
- ✅ Old files properly removed
- ✅ Documentation updated

### Manual Workflow Validation
Validate with GitHub's action validator:
```bash
# The workflow has been pushed to the branch and GitHub will validate it automatically
# Check the Actions tab for any validation errors
```

## Post-Merge Testing Plan

### Phase 1: Dry Run Simulation (Before First Real Release)

**Objective**: Verify the release script works correctly without making real changes

**Steps**:
1. Checkout a test branch from main
2. Manually simulate what the script does:
   ```bash
   # Simulate version bump
   cd packages/tyler
   CURRENT=$(grep 'version = "' pyproject.toml | sed 's/.*version = "\([^"]*\)".*/\1/')
   echo "Current version: $CURRENT"
   
   # Calculate new version (minor bump: 2.1.0 → 2.2.0)
   NEW_VERSION="2.2.0"
   echo "Would bump to: $NEW_VERSION"
   
   # Test sed command (without .bak suffix for testing)
   sed "s/version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml | grep version
   ```

3. Verify git-cliff output:
   ```bash
   # Generate test changelogs to review format
   git cliff --include-path "packages/tyler/**" --unreleased
   git cliff --include-path "packages/narrator/**" --unreleased
   git cliff --include-path "packages/space-monkey/**" --unreleased
   git cliff --include-path "packages/lye/**" --unreleased
   ```

4. Review output for quality and accuracy

**Expected Results**:
- Version calculations correct
- CHANGELOG format appropriate
- No syntax errors

### Phase 2: First Real Release (v2.2.0)

**⚠️ CRITICAL: This is the first synchronized release**

**Pre-Release Checklist**:
- [ ] All tests from `test_release_process.sh` passing
- [ ] No pending PRs that would conflict
- [ ] Team notified of upcoming synchronized version jump
- [ ] Backup plan documented (see Rollback section below)

**Execution Steps**:

1. **Run Release Script**
   ```bash
   ./scripts/release.sh minor
   ```

2. **Review Generated PR Carefully**
   Check that the PR includes:
   - [ ] All 4 packages bumped to 2.2.0
   - [ ] Version updated in `pyproject.toml` for all packages
   - [ ] Version updated in `__init__.py` for all packages
   - [ ] Inter-package constraints removed
   - [ ] CHANGELOGs generated for all packages
   - [ ] Single commit with all changes
   - [ ] PR has "release" label
   - [ ] Branch name is `release/v2.2.0`

3. **Review CHANGELOGs**
   - [ ] Each package CHANGELOG has appropriate entries
   - [ ] Conventional commits parsed correctly (feat:, fix:, etc.)
   - [ ] No sensitive information in changelogs
   - [ ] Format is readable

4. **Verify No Breaking Changes**
   - [ ] Review the changes in each package
   - [ ] Confirm this is truly a minor release (no breaking changes)
   - [ ] If breaking changes exist, should be major version instead

5. **Merge the Release PR**
   - Merge when all checks pass
   - Do NOT squash (keep the commit structure)

6. **Monitor Workflow Execution**
   Watch: `https://github.com/adamwdraper/slide/actions/workflows/release.yml`
   
   Expected sequence:
   - [ ] Workflow triggers on PR merge
   - [ ] `check-release` job validates conditions
   - [ ] `publish-all` job starts
   - [ ] Version verification passes (all at 2.2.0)
   - [ ] 4 git tags created successfully
   - [ ] All 4 packages build successfully
   - [ ] All 4 packages publish to PyPI successfully
   - [ ] 4 GitHub releases created

7. **Post-Release Verification**
   ```bash
   # Test installations
   python3 -m venv test-env
   source test-env/bin/activate
   
   # Install all packages at new version
   pip install slide-tyler==2.2.0
   pip install slide-narrator==2.2.0
   pip install slide-space-monkey==2.2.0
   pip install slide-lye==2.2.0
   
   # Verify imports work
   python -c "from tyler import Agent; print('Tyler OK')"
   python -c "from narrator import Thread; print('Narrator OK')"
   python -c "from space_monkey import SlackApp; print('Space Monkey OK')"
   python -c "from lye import WEB_TOOLS; print('Lye OK')"
   
   # Test inter-package imports
   python -c "from tyler import Agent; a = Agent(); print('Inter-package OK')"
   
   deactivate
   rm -rf test-env
   ```

8. **Verify on PyPI**
   - [ ] https://pypi.org/project/slide-tyler/2.2.0/
   - [ ] https://pypi.org/project/slide-narrator/2.2.0/
   - [ ] https://pypi.org/project/slide-space-monkey/2.2.0/
   - [ ] https://pypi.org/project/slide-lye/2.2.0/

9. **Verify GitHub Releases**
   - [ ] https://github.com/adamwdraper/slide/releases/tag/tyler-v2.2.0
   - [ ] https://github.com/adamwdraper/slide/releases/tag/narrator-v2.2.0
   - [ ] https://github.com/adamwdraper/slide/releases/tag/space-monkey-v2.2.0
   - [ ] https://github.com/adamwdraper/slide/releases/tag/lye-v2.2.0

**Success Criteria**:
- ✅ All packages at version 2.2.0
- ✅ All packages installable from PyPI
- ✅ No import errors
- ✅ Inter-package dependencies work
- ✅ GitHub releases created
- ✅ No issues reported

### Phase 3: Second Release Validation

**Objective**: Confirm repeatability and smooth operation

**Timeline**: Within 1-2 weeks of first release

**Steps**:
1. Run `./scripts/release.sh patch` (creates 2.2.1)
2. Verify process is smooth and requires no manual intervention
3. Confirm all checks from Phase 2 still pass

**Success Criteria**:
- Process completes without issues
- No manual fixes needed
- Team confidence high

## Rollback Procedures

### Scenario A: Release Script Fails (Before PR Merge)

**Symptoms**: Script exits with error, no PR created

**Recovery**:
1. Review error message
2. Fix issue (could be: network, auth, git state)
3. Delete the release branch if partially created:
   ```bash
   git branch -D release/v2.2.0
   git push origin --delete release/v2.2.0
   ```
4. Re-run release script

**Impact**: None - nothing published yet

### Scenario B: Release PR Created But Has Issues

**Symptoms**: PR created but versions wrong, changelogs bad, etc.

**Recovery**:
1. Close the PR (don't merge)
2. Delete the branch:
   ```bash
   git push origin --delete release/v2.2.0
   ```
3. Fix the issue in the script
4. Re-run release script

**Impact**: None - nothing published yet

### Scenario C: Workflow Fails After PR Merge

**Symptoms**: PR merged but workflow fails (tag creation, build, or publish)

**Recovery Options**:

**Option 1 - Retry Workflow** (if transient failure):
```bash
# Re-run the failed workflow from GitHub UI
# GitHub Actions > Failed workflow > Re-run all jobs
```

**Option 2 - Manual Recovery** (if workflow can't be fixed):
```bash
# Manually create tags
git checkout main
git pull origin main
for pkg in tyler narrator space-monkey lye; do
  git tag -a "$pkg-v2.2.0" -m "Release $pkg version 2.2.0"
  git push origin "$pkg-v2.2.0"
done

# Manually build and publish (from each package directory)
cd packages/tyler && uv tool run hatch build && uv tool run hatch publish
cd ../narrator && uv tool run hatch build && uv tool run hatch publish
cd ../space-monkey && uv tool run hatch build && uv tool run hatch publish
cd ../lye && uv tool run hatch build && uv tool run hatch publish

# Manually create GitHub releases
gh release create tyler-v2.2.0 --title "Tyler v2.2.0" --notes "..." packages/tyler/dist/*
# (repeat for other packages)
```

**Option 3 - Roll Forward** (if partial publish):
```bash
# If some packages published but not others:
# 1. Identify which packages published
# 2. Manually publish remaining packages (as in Option 2)
# 3. Create GitHub releases for all
```

**Impact**: Partial - may have incomplete state, need manual intervention

### Scenario D: Published Packages Have Critical Bug

**Symptoms**: Packages on PyPI but contain critical bug

**Recovery**:
```bash
# Yank the versions on PyPI (makes them unavailable for new installs)
# Via PyPI web UI or:
# pip install twine
# twine upload --skip-existing --repository pypi dist/*

# Then create patch release with fix
./scripts/release.sh patch  # Creates 2.2.1
```

**Impact**: High - users may have installed buggy version
**Note**: Cannot delete from PyPI, only yank (hide from pip install)

## Monitoring & Alerting

### Key Metrics to Track

1. **Release Success Rate**
   - Target: >95% after stabilization
   - Track in: GitHub Actions

2. **Release Duration**
   - Target: <5 minutes from PR merge to PyPI publish
   - Track in: GitHub Actions workflow run time

3. **Installation Success Rate**
   - Manual testing after each release
   - User reports of installation issues

### Alerts

- **GitHub Actions failures**: Automatic email notification
- **PyPI publish failures**: Check workflow logs
- **User reports**: Monitor GitHub issues and Discord/Slack

## Communication Plan

### Before First Release
- [ ] Team notified about unified release process
- [ ] Explain version synchronization (all packages → 2.2.0)
- [ ] Share this testing plan

### After First Release
- [ ] Announce in Discord/Slack
- [ ] Update README with version sync note
- [ ] Create release announcement with:
  - Explanation of synchronized versioning
  - Benefits (compatibility guaranteed)
  - Migration notes (update all packages together)

### After Second Release
- [ ] Team retrospective
- [ ] Document lessons learned
- [ ] Update process if needed

## Success Criteria Summary

The unified release process is considered **production-ready** when:

1. ✅ First release (v2.2.0) completes successfully
2. ✅ All packages installable and functional
3. ✅ No manual intervention required
4. ✅ Second release (v2.2.1) completes smoothly
5. ✅ Team comfortable with new process
6. ✅ No outstanding issues or bugs

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|---------|------------|
| Version mismatch in first release | Low | High | Automated tests + manual review |
| Workflow fails mid-publish | Low | Medium | Rollback procedures documented |
| CHANGELOG quality poor | Medium | Low | Review before merge + can edit |
| User confusion about versions | Medium | Low | Clear communication + docs |
| PyPI publish failures | Low | High | Retry mechanisms + manual fallback |

## Contact & Support

**Issues during release?**
- Check workflow logs: https://github.com/adamwdraper/slide/actions
- Review this testing plan
- Consult TDR: `/directive/specs/unified-release/tdr.md`

**Emergency rollback needed?**
- Follow procedures in "Rollback Procedures" section above
- Document incident for post-mortem

---

**Last Updated**: 2025-10-13  
**Status**: Ready for First Release  
**Next Review**: After second successful release

