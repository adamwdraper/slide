# Technical Design Review (TDR) — Auto-Set Minimum Version Constraints in Release Script

**Author**: AI Agent  
**Date**: 2025-10-15  
**Links**: 
- Spec: `/directive/specs/preserve-minimum-version-constraints/spec.md`
- Impact: `/directive/specs/preserve-minimum-version-constraints/impact.md`
- Release Script: `/scripts/release.sh`
- PR #76: https://github.com/adamwdraper/slide/pull/76 (needs to be redone with this fix)

---

## 1. Summary

We are fixing the unified release script to automatically set minimum version constraints for inter-package dependencies instead of removing them. Currently, the script removes ALL version constraints (lines 119-145), which creates compatibility issues where users can install incompatible package combinations (e.g., Tyler 3.1.0 with Narrator 1.0.2, causing Pydantic validation errors).

The fix is simple: replace the constraint-removal logic with constraint-setting logic that automatically applies `>=NEW_VERSION` to all inter-package dependencies (Tyler→Narrator, Tyler→Lye, Space-monkey→Tyler, Space-monkey→Narrator). This ensures that packages released together are guaranteed compatible while allowing future versions to be installed.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **Bug fix urgency**: Version 3.1.0 was released with this bug; users are hitting errors in production
- **Automated correctness**: Eliminate manual constraint management (error-prone)
- **Unified release philosophy**: Since we release all packages together, they should declare compatibility automatically
- **User experience**: Prevent `pip install` from creating broken combinations
- **Maintainability**: Preserve modularity - narrator and lye are standalone packages that should remain installable independently

### Non‑Goals
- Independent version releases per package (we're committed to unified versioning)
- Setting constraints on narrator or lye (they have no internal Slide dependencies)
- Backporting constraint fixes to already-published versions (can't modify published PyPI packages)
- Complex constraint resolution logic (simple `>=` is sufficient for our use case)
- Supporting exact version pins (`==`) - we don't use them and they conflict with unified releases

## 3. Current State — Codebase Map (concise)

### Key modules
- **`scripts/release.sh`** (241 lines):
  - Lines 1-48: Setup, validation, tool checks
  - Lines 50-76: Version bumping logic
  - Lines 94-115: Version updates in pyproject.toml and __init__.py
  - **Lines 117-145: Constraint removal logic** ← **THIS IS THE BUG**
  - Lines 147-166: CHANGELOG generation via git-cliff
  - Lines 169-184: Git commit and push
  - Lines 186-241: PR creation via gh CLI

### Current constraint removal logic (buggy)
```bash
# Lines 119-145 of release.sh
echo ""
echo -e "${BLUE}Removing inter-package version constraints...${NC}"

# Tyler: slide-narrator>=X.Y.Z -> slide-narrator
if grep -q '"slide-narrator>=.*"' packages/tyler/pyproject.toml; then
    sed -i.bak 's/"slide-narrator>=.*"/"slide-narrator"/g' packages/tyler/pyproject.toml
    echo -e "  ${GREEN}✓${NC} Tyler: slide-narrator constraint removed"
fi

if grep -q '"slide-lye>=.*"' packages/tyler/pyproject.toml; then
    sed -i.bak 's/"slide-lye>=.*"/"slide-lye"/g' packages/tyler/pyproject.toml
    echo -e "  ${GREEN}✓${NC} Tyler: slide-lye constraint removed"
fi

# Space Monkey: similar removal logic
# ...

# Clean up backup files
rm -f packages/tyler/pyproject.toml.bak
rm -f packages/space-monkey/pyproject.toml.bak
```

### Existing data models
- **pyproject.toml format** (standard Python packaging):
  ```toml
  [project]
  dependencies = [
      "slide-narrator>=3.1.0",  # Minimum version constraint
      "slide-lye",              # No constraint (any version)
      "litellm>=1.63.0",        # External package constraint
  ]
  ```

### External contracts
- **PyPI package metadata**: Constraints in pyproject.toml are published to PyPI
- **pip/uv dependency resolver**: Uses constraints to determine compatible versions
- **git-cliff**: Generates CHANGELOGs (unaffected by this change)
- **GitHub CLI (`gh`)**: Creates PRs (unaffected)

### Observability currently available
- Script outputs colored status messages to terminal
- Git commit shows constraint changes in diff
- Generated PR shows all changes for human review

## 4. Proposed Design (high level, implementation‑agnostic)

### Overall approach
Replace lines 117-145 (constraint removal) with new constraint-setting logic that applies `>=NEW_VERSION` to all inter-package dependencies.

### Pseudo-code
```bash
# NEW section replacing lines 117-145
echo ""
echo -e "${BLUE}Setting inter-package minimum version constraints...${NC}"

# Tyler: Set narrator and lye to >=NEW_VERSION
sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
    packages/tyler/pyproject.toml
echo -e "  ${GREEN}✓${NC} Tyler: slide-narrator>=$NEW_VERSION"

sed -i.bak "s/\"slide-lye[^\"]*\"/\"slide-lye>=$NEW_VERSION\"/g" \
    packages/tyler/pyproject.toml
echo -e "  ${GREEN}✓${NC} Tyler: slide-lye>=$NEW_VERSION"

# Space Monkey: Set tyler and narrator to >=NEW_VERSION
sed -i.bak "s/\"slide-tyler[^\"]*\"/\"slide-tyler>=$NEW_VERSION\"/g" \
    packages/space-monkey/pyproject.toml
echo -e "  ${GREEN}✓${NC} Space Monkey: slide-tyler>=$NEW_VERSION"

sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
    packages/space-monkey/pyproject.toml
echo -e "  ${GREEN}✓${NC} Space Monkey: slide-narrator>=$NEW_VERSION"

# Clean up backup files
rm -f packages/tyler/pyproject.toml.bak
rm -f packages/space-monkey/pyproject.toml.bak
```

### Regex pattern explanation
- Pattern: `"slide-narrator[^\"]*"` matches any of:
  - `"slide-narrator"` (no constraint)
  - `"slide-narrator>=3.0.0"` (existing constraint)
  - `"slide-narrator==3.0.0"` (exact pin, theoretical)
- Replacement: `"slide-narrator>=$NEW_VERSION"` sets the new constraint
- The `[^\"]*` matches any characters except quotes (greedy within the string)

### Interface changes
**Input**: Same as current script
- `$NEW_VERSION` variable (e.g., "3.1.1")
- Package pyproject.toml files with inter-package dependencies

**Output**: 
- Modified pyproject.toml files with `>=NEW_VERSION` constraints
- Terminal output showing which constraints were set
- No change to PR creation or CHANGELOG generation

**Behavior change**:
- Old: Constraints removed → packages can install any version
- New: Constraints set → packages must install >= release version

### Error handling
No new error handling needed:
- `sed` failures already cause script to exit (due to `set -e` at line 2)
- Backup files (`.bak`) cleaned up regardless of success/failure
- If constraint already exists, sed simply replaces it (idempotent)

### Performance expectations
- Minimal impact: 4 additional `sed` commands (~50ms total)
- Same overall script execution time (~30-60 seconds)

## 5. Alternatives Considered

### Option A: Preserve manually-set constraints (original spec approach)
**Approach**: Parse existing constraints and preserve them if they exist.

**Pros**:
- Gives developers explicit control
- Could have different constraints per package

**Cons**:
- Complex parsing logic (multiple constraint formats)
- Requires developers to remember to add constraints
- Error-prone (what if developer forgets?)
- Doesn't solve the root problem (constraints were removed)

**Why not chosen**: Too complex for the benefit; auto-setting is simpler and more reliable.

---

### Option B: Use exact version pins (`==`)
**Approach**: Set `"slide-narrator==3.1.1"` instead of `>=3.1.1`.

**Pros**:
- Absolute guarantee of version compatibility
- No ambiguity

**Cons**:
- Prevents installing newer narrator with older tyler
- Creates unnecessary upgrade coupling
- Conflicts with unified release philosophy (we want to allow forward compatibility)
- Makes development harder (can't test tyler with unreleased narrator)

**Why not chosen**: Too strict; `>=` allows flexibility while ensuring minimum compatibility.

---

### Option C: Merge packages into one (discussed earlier)
**Approach**: Combine narrator, lye, and tyler into a single package.

**Pros**:
- Eliminates all cross-dependency issues
- Single version, single install

**Cons**:
- Loses modularity (narrator and lye are useful standalone)
- Larger installation footprint for users who only want parts
- Breaking change for existing users

**Why not chosen**: We determined narrator and lye have standalone value; preserving modularity is important.

---

### Option D: Do nothing (document workaround)
**Approach**: Document that users must upgrade all packages together.

**Pros**:
- No code changes

**Cons**:
- Poor user experience (error-prone manual upgrades)
- Doesn't prevent broken installations
- Users still hit Pydantic errors
- Maintenance burden (answering support questions)

**Why not chosen**: This is a real bug causing production issues; must fix properly.

---

### **Chosen Option: Auto-set minimum constraints (`>=NEW_VERSION`)**

**Why this is best**:
1. ✅ Simple implementation (replace ~27 lines of bash)
2. ✅ Automated (no manual management needed)
3. ✅ Reliable (guaranteed correct for every release)
4. ✅ Flexible (allows future versions via `>=`)
5. ✅ Preserves modularity (narrator/lye remain standalone)
6. ✅ Fixes the bug completely
7. ✅ Aligns with unified release philosophy

## 6. Data Model & Contract Changes

### No database changes
This is a build/release tooling change; no runtime data models affected.

### Package metadata changes (PyPI)

**Before (current broken state in 3.1.0)**:
```toml
# packages/tyler/pyproject.toml
dependencies = [
    "slide-narrator",  # ← No constraint, any version allowed
    "slide-lye",       # ← No constraint, any version allowed
]
```

**After (fixed behavior for 3.1.1+)**:
```toml
# packages/tyler/pyproject.toml
dependencies = [
    "slide-narrator>=3.1.1",  # ← Minimum version enforced
    "slide-lye>=3.1.1",       # ← Minimum version enforced
]
```

**Impact on users**:
- Installing `slide-tyler==3.1.1` will automatically install `slide-narrator>=3.1.1`
- If user has narrator 3.0.0, pip will upgrade to 3.1.1+ or fail with conflict
- If user has narrator 3.2.0, no change (already satisfies >=3.1.1)

### Backward compatibility
- **Published packages**: Cannot change (PyPI doesn't allow edits)
  - Tyler 3.1.0 is broken (has no constraints) - users must upgrade to 3.1.1
- **Future releases**: All releases from 3.1.1 forward will have correct constraints
- **No breaking changes**: This enforces existing compatibility requirements (doesn't introduce new restrictions)

## 7. Security, Privacy, Compliance

### AuthN/AuthZ
- Not applicable (build-time script, no user authentication)

### Secrets management
- Not applicable (no secrets involved)
- Script uses `GITHUB_TOKEN` (implicit via `gh` CLI) - no changes

### PII handling
- Not applicable (no user data)

### Threat model
**Risk: Malicious sed injection**
- Threat: If `$NEW_VERSION` contains shell metacharacters, could modify unintended files
- Likelihood: Very low (version is generated from existing version in git)
- Mitigation: Version validation at lines 22-26 already ensures format is `X.Y.Z`
- Example: Regex `^(major|minor|patch)$` ensures valid input

**Risk: Accidental constraint on external packages**
- Threat: Regex could match external packages (e.g., `"slide-sdk"` from third party)
- Likelihood: Low (we control package naming: slide-narrator, slide-lye, slide-tyler, slide-space-monkey)
- Mitigation: Specific package names in regex (not wildcards)

### Compliance
- Not applicable (no regulatory requirements for build scripts)

## 8. Observability & Operations

### Logs
**Current**: Script outputs:
```
🚀 Unified Release Script
=========================
...
Tyler: slide-narrator constraint removed ✓
```

**New**: Script will output:
```
🚀 Unified Release Script
=========================
...
Setting inter-package minimum version constraints...
  ✓ Tyler: slide-narrator>=3.1.1
  ✓ Tyler: slide-lye>=3.1.1
  ✓ Space Monkey: slide-tyler>=3.1.1
  ✓ Space Monkey: slide-narrator>=3.1.1
```

**Change**: More descriptive output showing actual constraints set

### Metrics
- Not applicable (no metrics for build scripts)

### Dashboards/Alerts
- Not applicable (human-reviewed PR process)

### Runbooks
**Manual verification** (add to release checklist):
```bash
# After release script runs, verify constraints:
grep "slide-narrator\|slide-lye\|slide-tyler" packages/*/pyproject.toml

# Expected output should show >=X.Y.Z for inter-package deps
# Example for 3.1.1 release:
#   packages/tyler/pyproject.toml:    "slide-narrator>=3.1.1",
#   packages/tyler/pyproject.toml:    "slide-lye>=3.1.1",
#   packages/space-monkey/pyproject.toml:    "slide-tyler>=3.1.1",
#   packages/space-monkey/pyproject.toml:    "slide-narrator>=3.1.1",
```

## 9. Rollout & Migration

### Feature flags
- Not applicable (build script, not runtime feature)

### Migration strategy

**Step 1: Fix the script (this PR)**
- Modify `scripts/release.sh` lines 117-145
- Add test coverage (manual or automated)
- Merge to main

**Step 2: Handle PR #76 (current broken release PR)**

**Option A (Recommended)**: Close and recreate
1. Close PR #76 (broken constraints)
2. Checkout main (has the fix)
3. Re-run `./scripts/release.sh patch`
4. Create new PR for 3.1.1 (with correct constraints)
5. Merge and publish

**Option B**: Manual fix PR #76
1. Checkout release/v3.1.1 branch
2. Manually edit pyproject.toml files to add constraints
3. Commit with message: "fix: Add minimum version constraints"
4. Push to update PR #76
5. Merge and publish

**Recommendation**: Option A is cleaner and tests the fixed script

**Step 3: Publish 3.1.1**
- Merge PR → unified release workflow runs
- Tags created, packages published to PyPI
- Users can `pip install slide-tyler==3.1.1` with correct constraints

### Data backfill
- Not applicable (no data to migrate)

### Revert plan
If published 3.1.1 has issues:
- **Can't unpublish** PyPI packages (per PyPI policy)
- **Mitigation**: Publish 3.1.2 with fix
- **Script revert**: Revert this PR in git, use old script for next release
- **Blast radius**: Only affects new installations (existing installations unaffected)

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
We will write tests **before** modifying the release script. For bash scripts, testing options:
1. **Manual testing** with test pyproject.toml files
2. **Automated testing** with a test harness (preferred)
3. **Integration testing** by running the full script in a test branch

### Spec→Test Mapping

| Spec AC | Test ID | Test Description | Test Type |
|---------|---------|------------------|-----------|
| AC1: Auto-set Tyler constraints | `test_tyler_constraints_set` | Verify Tyler gets narrator>=X.Y.Z and lye>=X.Y.Z | Unit |
| AC2: Auto-set Space-monkey constraints | `test_space_monkey_constraints_set` | Verify Space-monkey gets tyler>=X.Y.Z and narrator>=X.Y.Z | Unit |
| AC3: Override existing constraints | `test_override_existing_constraint` | Start with narrator>=3.0.0, verify updated to >=3.1.1 | Unit |
| AC4: Don't affect external deps | `test_external_deps_unchanged` | Verify litellm>=1.63.0 remains unchanged | Unit |
| AC5: Prevent old version install | `test_pip_install_enforcement` | Attempt to install Tyler 3.1.1 with Narrator 3.0.0 pinned | Integration |

### Test Implementation

**Test Harness** (create `scripts/test_release.sh`):
```bash
#!/bin/bash
# Test harness for release script constraint logic

# Setup test fixtures
mkdir -p test_packages/{tyler,space-monkey}

# Test 1: Tyler constraints set
cat > test_packages/tyler/pyproject.toml << 'EOF'
[project]
dependencies = [
    "slide-narrator",
    "slide-lye",
    "litellm>=1.63.0",
]
EOF

# Run constraint-setting logic (extract from release.sh)
NEW_VERSION="3.1.1"
sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
    test_packages/tyler/pyproject.toml
sed -i.bak "s/\"slide-lye[^\"]*\"/\"slide-lye>=$NEW_VERSION\"/g" \
    test_packages/tyler/pyproject.toml

# Assertions
if grep -q "slide-narrator>=3.1.1" test_packages/tyler/pyproject.toml; then
    echo "✓ AC1: Tyler narrator constraint set correctly"
else
    echo "✗ AC1 FAILED"
    exit 1
fi

if grep -q "slide-lye>=3.1.1" test_packages/tyler/pyproject.toml; then
    echo "✓ AC1: Tyler lye constraint set correctly"
else
    echo "✗ AC1 FAILED"
    exit 1
fi

if grep -q "litellm>=1.63.0" test_packages/tyler/pyproject.toml; then
    echo "✓ AC4: External deps unchanged"
else
    echo "✗ AC4 FAILED"
    exit 1
fi

# Test 2: Override existing constraint
cat > test_packages/tyler/pyproject.toml << 'EOF'
[project]
dependencies = [
    "slide-narrator>=3.0.0",
]
EOF

sed -i.bak "s/\"slide-narrator[^\"]*\"/\"slide-narrator>=$NEW_VERSION\"/g" \
    test_packages/tyler/pyproject.toml

if grep -q "slide-narrator>=3.1.1" test_packages/tyler/pyproject.toml; then
    echo "✓ AC3: Existing constraint overridden"
else
    echo "✗ AC3 FAILED"
    exit 1
fi

# Cleanup
rm -rf test_packages

echo ""
echo "All tests passed! ✓"
```

**Usage**:
```bash
chmod +x scripts/test_release.sh
./scripts/test_release.sh
```

### Negative & Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| No constraint exists | `"slide-narrator"` → `"slide-narrator>=3.1.1"` ✓ |
| Old constraint exists | `"slide-narrator>=3.0.0"` → `"slide-narrator>=3.1.1"` ✓ |
| Exact pin exists (theoretical) | `"slide-narrator==3.0.0"` → `"slide-narrator>=3.1.1"` ✓ |
| External package | `"litellm>=1.63.0"` → unchanged ✓ |
| Malformed version | Script validation rejects (lines 22-26) ✓ |
| sed failure | Script exits with error (`set -e`) ✓ |

### Performance Tests
- Not applicable (script execution time not critical)
- Expected impact: +1-2 seconds for 4 additional sed operations (negligible)

### CI Integration
**Current state**: No CI for release script (runs manually)

**Recommendation**: Add test to CI
```yaml
# .github/workflows/test-release-script.yml
name: Test Release Script
on: [push, pull_request]
jobs:
  test-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run release script tests
        run: ./scripts/test_release.sh
```

**Alternative**: Manual testing is acceptable for release scripts (low change frequency, high review)

## 11. Risks & Open Questions

### Known Risks

**Risk 1: Regex doesn't match all edge cases**
- **Likelihood**: Low
- **Impact**: Medium (constraint not set correctly)
- **Mitigation**: Test with multiple input formats (done in test harness)
- **Fallback**: Manual verification in PR review

**Risk 2: Constraint too strict for some users**
- **Likelihood**: Medium (users with pinned old versions)
- **Impact**: Low (installation fails with clear error message)
- **Mitigation**: 
  - Document in CHANGELOG: "Upgrade all Slide packages together"
  - Error message from pip is clear: "requires slide-narrator>=3.1.1 but you have 3.0.0"
- **Workaround**: Users can explicitly pin both packages to old versions if needed

**Risk 3: Future package renames**
- **Likelihood**: Low
- **Impact**: Low (constraint not applied to renamed package)
- **Mitigation**: Update script when package names change
- **Prevention**: Keep package naming consistent

### Open Questions

**Q1: Should we apply constraints retroactively to older versions?**
- **Answer**: No, we can't (PyPI doesn't allow editing published packages)
- **Resolution**: Only applies to 3.1.1 forward; users on 3.1.0 must upgrade

**Q2: Should we set constraints for Narrator→Tyler or Lye→Tyler?**
- **Answer**: No, narrator and lye don't depend on tyler (they're lower-level libraries)
- **Resolution**: Only set constraints in the "upward" direction (tyler→narrator, tyler→lye)

**Q3: What if a user wants Tyler 3.1.1 with Narrator 3.2.0?**
- **Answer**: That's fine! `>=3.1.1` allows 3.2.0 (and any future version)
- **Resolution**: Design explicitly supports this (that's why we use `>=` not `==`)

**Q4: Should we test the change in a dry-run mode first?**
- **Answer**: Yes, good idea
- **Resolution**: Run `./scripts/release.sh patch` in a test branch, review generated PR before merging script fix

## 12. Milestones / Plan (post‑approval)

### Task Breakdown

**Task 1: Create test harness** 
- **Owner**: Agent
- **Estimate**: 30 minutes
- **DoD**: 
  - [ ] Create `scripts/test_release.sh`
  - [ ] Tests cover AC1, AC2, AC3, AC4
  - [ ] All tests pass
  - [ ] Document how to run tests in scripts/README.md

**Task 2: Modify release script**
- **Owner**: Agent
- **Estimate**: 30 minutes
- **DoD**:
  - [ ] Replace lines 117-145 in `scripts/release.sh`
  - [ ] Update terminal output messages
  - [ ] Preserve backup file cleanup logic
  - [ ] Run test harness successfully

**Task 3: Manual validation**
- **Owner**: Agent + Human reviewer
- **Estimate**: 30 minutes
- **DoD**:
  - [ ] Run release script in test branch: `git checkout -b test-release-fix && ./scripts/release.sh patch`
  - [ ] Verify constraints in generated files
  - [ ] Check PR description and diff
  - [ ] Don't merge (just testing)

**Task 4: Update documentation**
- **Owner**: Agent
- **Estimate**: 15 minutes
- **DoD**:
  - [ ] Update `scripts/README.md` with constraint-setting behavior
  - [ ] Add manual verification steps to release checklist
  - [ ] Document rationale in commit message

**Task 5: Handle PR #76**
- **Owner**: Human
- **Estimate**: 10 minutes
- **DoD**:
  - [ ] Close PR #76 (or manually fix if preferred)
  - [ ] Re-run release script with fixed version
  - [ ] Verify new PR has correct constraints

**Task 6: Release 3.1.1**
- **Owner**: Human
- **Estimate**: 5 minutes
- **DoD**:
  - [ ] Merge release PR
  - [ ] Verify CI publishes to PyPI
  - [ ] Test install: `pip install slide-tyler==3.1.1`
  - [ ] Verify narrator>=3.1.1 is installed

### Dependencies
- No external dependencies
- No coordination with other teams
- No feature flags needed

### Total Estimated Time
- **Development**: ~2 hours
- **Testing**: ~30 minutes
- **Review**: ~30 minutes
- **Release**: ~15 minutes
- **Total**: ~3-4 hours

---

## Approval Gate

**Status**: ✅ Ready for review

**Reviewers**: Please approve if:
1. The approach (auto-set constraints to `>=NEW_VERSION`) makes sense
2. The test strategy adequately covers the spec acceptance criteria
3. The risk mitigations are acceptable
4. No major concerns with bash script modification

**Do not start coding until this TDR is approved.**

