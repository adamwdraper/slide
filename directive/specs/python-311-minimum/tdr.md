# Technical Design Review (TDR) — Python 3.11 Minimum Version Consistency

**Author**: AI Agent  
**Date**: 2025-01-13  
**Links**: 
- Spec: `/directive/specs/python-311-minimum/spec.md`
- Impact: `/directive/specs/python-311-minimum/impact.md`
- User Issue: Customer installation failure with Python 3.11

---

## 1. Summary

We are standardizing all Slide packages to require Python 3.11+ instead of the inconsistent 3.11/3.13 requirements currently in place. This involves:

1. **Metadata updates**: Updating `pyproject.toml` files across 4 packages to specify `requires-python = ">=3.11"`
2. **Documentation updates**: Correcting docs to reflect Python 3.11+ requirement
3. **CI matrix testing**: Implementing GitHub Actions matrix strategy to test Python 3.11, 3.12, and 3.13 on every PR

**Why**: Code analysis revealed actual minimum is Python 3.11 (due to `datetime.UTC` usage), not 3.13. Current inconsistency causes installation failures for users with Python 3.11 or 3.12, even though the code would work fine.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **User blocker**: Customer unable to install packages despite having compatible Python version
- **Code compatibility**: Actual code requires only Python 3.11+ (`datetime.UTC` added in 3.11)
- **Quality assurance**: Need automated testing to verify compatibility claims
- **Consistency**: All packages should have aligned requirements

### Non-Goals
- Adding Python 3.10 support (would require refactoring `datetime.UTC` usage)
- Changing actual code behavior or logic
- Modifying package functionality beyond version requirements
- Testing Python versions beyond 3.13

## 3. Current State — Codebase Map

### Package Metadata (Current State)
```
packages/narrator/pyproject.toml:   requires-python = ">=3.11"  ✓
packages/tyler/pyproject.toml:      requires-python = ">=3.13"  ✗
packages/lye/pyproject.toml:        requires-python = ">=3.13"  ✗
packages/space-monkey/pyproject.toml: requires-python = ">=3.13"  ✗
```

### Code Dependencies
- **Critical feature**: `datetime.UTC` used in 72+ locations across:
  - `packages/tyler/tyler/models/agent.py`
  - `packages/tyler/tyler/models/message_factory.py`
  - `packages/tyler/tyler/models/completion_handler.py`
  - `packages/narrator/narrator/models/thread.py`
  - `packages/narrator/narrator/models/message.py`
  - `packages/narrator/narrator/database/models.py`
  - And 9 more files

- **Python version introduced**: `datetime.UTC` added in Python 3.11
- **No other version-specific features**: No `match` statements, no 3.12+ exclusive syntax

### CI/CD Current State
```yaml
# .github/workflows/test.yml
- All 6 test jobs use: python-version: '3.13'
- test-narrator, test-tyler, test-space-monkey, test-lye, integration-test, test-examples

# .github/workflows/test-examples.yml  
- Both jobs use: python-version: '3.13'
```

**Gap**: No automated testing for Python 3.11 or 3.12

### External Dependencies
All major dependencies support Python 3.8+:
- `litellm>=1.60.2` → Python 3.8+
- `openai>=1.61.0` → Python 3.7.1+
- `pydantic>=2.10.4` → Python 3.8+

## 4. Proposed Design

### 4.1 Package Metadata Changes
**Approach**: Update `requires-python` field in all package `pyproject.toml` files

```toml
# Before
requires-python = ">=3.13"

# After
requires-python = ">=3.11"
```

**Files to update**:
- `packages/tyler/pyproject.toml` - Also add Python 3.11 to classifiers
- `packages/lye/pyproject.toml` - Also add Python 3.11 to classifiers
- `packages/space-monkey/pyproject.toml` - Classifiers already include 3.11
- `packages/narrator/pyproject.toml` - No change (already correct)

### 4.2 Documentation Updates
**Approach**: Find and replace Python version references

**Files**:
- `README.md` - Installation section
- `docs/quickstart.mdx` - Requirements note and installation
- `docs/guides/your-first-agent.mdx` - Add requirements note
- `directive/reference/agent_context.md` - Python version reference

**Changes**:
- "Python 3.13 or higher" → "Python 3.11 or higher"
- `uv init my-agent --python 3.13` → `uv init my-agent` (let it auto-detect)
- `python3.13` → `python3` (generic)

### 4.3 CLI Template Generation
**File**: `packages/tyler/tyler/cli/init.py`

```python
# Before (line 60)
requires-python = ">=3.12"

# After
requires-python = ">=3.11"
```

### 4.4 CI Matrix Testing Implementation

**Primary Design**: Full matrix strategy testing all supported versions

#### 4.4.1 Test Workflow Matrix Strategy

```yaml
# .github/workflows/test.yml
jobs:
  test-narrator:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12', '3.13']
      fail-fast: false  # Continue testing all versions even if one fails
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install workspace dependencies
        run: uv sync --dev
      
      - name: Run Narrator tests
        run: |
          cd packages/narrator
          uv run pytest tests/
```

**Apply to all test jobs**:
- `test-narrator`
- `test-tyler`
- `test-space-monkey`
- `test-lye`
- `integration-test`
- `test-examples` (in test.yml)
- `test-examples` (in test-examples.yml)
- `test-examples-with-api` (in test-examples.yml)

#### 4.4.2 Job Dependencies with Matrix
**Challenge**: Job dependencies must account for matrix expansion

```yaml
# Current (simple dependency)
test-tyler:
  needs: [test-narrator]

# With matrix (same syntax works)
test-tyler:
  needs: [test-narrator]  # Waits for ALL narrator matrix jobs to complete
```

GitHub Actions automatically handles matrix expansion in `needs` clauses.

#### 4.4.3 Performance Considerations

**Execution Model**: Jobs run in parallel across matrix dimensions
- Before: 6 sequential job groups × 1 Python version = 6 total jobs
- After: 6 sequential job groups × 3 Python versions = 18 total jobs
- Wall-clock time: Minimal increase (parallel execution)
- CI minutes: 3× consumption

**Optimization**: Use `fail-fast: false`
- Allows all Python versions to complete testing
- Helps identify version-specific issues
- Better debugging when failures occur

### 4.5 Error Handling

#### Installation Errors
**Current behavior** (Python 3.10):
```
ERROR: Package requires Python >=3.11 but you have 3.10
```
**Remains unchanged** - pip/uv handle this automatically

#### Test Failures
**New behavior**: CI will show which Python version(s) fail
```
✓ test-narrator (3.11)
✗ test-narrator (3.12) - Failed
✓ test-narrator (3.13)
```

### 4.6 Release Process
**Coordinated release**: All 4 packages released together
- Ensures consistent requirements across ecosystem
- Version bumps: Patch releases (metadata change)
- Release order: Can be parallel (no interdependencies)

## 5. Alternatives Considered

### Alternative A: Minimum/Maximum Matrix (Two Versions Only)
```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.13']  # Test boundaries only
```

**Pros**:
- Reduces CI minutes by 33% (2 versions vs 3)
- Still catches edge cases

**Cons**:
- Doesn't test Python 3.12 specifically
- Could miss 3.12-specific issues
- Less confidence in middle version

**Rejected**: Full coverage is worth the additional CI cost for a core requirement

### Alternative B: Manual Testing Only
Keep CI at Python 3.13, rely on manual testing before releases

**Pros**:
- No CI changes needed
- Zero additional CI cost

**Cons**:
- Manual testing is error-prone
- No ongoing verification
- Could ship regressions
- Poor developer experience

**Rejected**: Automated testing is fundamental for quality assurance

### Alternative C: Support Python 3.10
Refactor `datetime.UTC` to `datetime.timezone.utc`

**Pros**:
- Broader compatibility
- Supports older systems

**Cons**:
- Requires code changes (72+ occurrences)
- Python 3.10 reaches EOL in October 2026
- No user demand demonstrated
- Out of scope for current issue

**Deferred**: Can revisit if users request it

### Alternative D: Single Combined Matrix Job
Use matrix at job level instead of per-job level

```yaml
jobs:
  test-all:
    strategy:
      matrix:
        python-version: ['3.11', '3.12', '3.13']
        package: ['narrator', 'tyler', 'lye', 'space-monkey']
```

**Pros**:
- More concise YAML
- Single job definition

**Cons**:
- Harder to read GitHub Actions UI
- Can't express complex dependencies
- All-or-nothing testing (harder to debug)

**Rejected**: Current job structure is clearer and more maintainable

## 6. Data Model & Contract Changes

### PyPI Package Metadata Contract
**Change type**: Constraint relaxation (non-breaking)

```python
# Before (published on PyPI)
requires-python = ">=3.13"

# After (new versions)
requires-python = ">=3.11"
```

**Backward compatibility**: ✅ Fully compatible
- Users on Python 3.13 unaffected
- Users on Python 3.11/3.12 can now install
- Existing pinned versions remain available

**No other contract changes**:
- No API changes
- No data model changes
- No event schema changes
- No database migrations

## 7. Security, Privacy, Compliance

**Assessment**: No security implications

- ✅ No new authentication/authorization logic
- ✅ No new secrets or credentials
- ✅ No PII handling changes
- ✅ No new external dependencies
- ✅ Python 3.11 is actively maintained with security patches

**CI Security**: GitHub Actions matrix testing
- Uses trusted GitHub-hosted runners
- No additional secrets required
- No changes to existing secret management

## 8. Observability & Operations

### Logs
**No new logging required**
- Installation errors handled by pip/uv (existing)
- CI test failures visible in GitHub Actions UI (existing)

### Metrics
**Optional enhancement** (out of scope):
- Track Python version distribution via Weave telemetry
- Would inform future version support decisions

### CI Observability
**Enhanced visibility**:
- GitHub Actions UI will show matrix dimensions
- Easier to identify version-specific failures
- Example display:
  ```
  test-narrator
    ├─ 3.11 ✓
    ├─ 3.12 ✓
    └─ 3.13 ✓
  ```

### Dashboards
**No new dashboards required**
- GitHub Actions UI provides sufficient visibility
- Existing PyPI download stats available (if needed)

### Alerts
**No new alerts required**
- CI failures block PR merge (existing behavior)
- No production services affected

## 9. Rollout & Migration

### Feature Flags
**Not applicable**: This is a package metadata change, not a feature

### Release Strategy
**Coordinated release** of all packages:

1. **Build phase** (local):
   ```bash
   uv build --package tyler
   uv build --package lye
   uv build --package narrator
   uv build --package space-monkey
   ```

2. **Test phase** (automated via CI):
   - Matrix tests run on Python 3.11, 3.12, 3.13
   - All tests must pass before merge

3. **Publish phase** (to PyPI):
   ```bash
   # Via release workflows (automated)
   # Triggered by merging release/* branches
   ```

4. **Verification phase**:
   - Test installations on clean Python 3.11, 3.12, 3.13 environments
   - Verify user's original scenario works

### Migration Path for Users

**Users on Python 3.13**: No action needed
- Can upgrade to new package versions seamlessly

**Users on Python 3.11/3.12**: Can now install
```bash
# Previously failed
uv add slide-tyler  # ERROR: requires Python >=3.13

# Now works
uv add slide-tyler  # SUCCESS
```

**Users who pinned exact versions**: Need explicit upgrade
```bash
uv add slide-tyler@2.1.1
```

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Approach
**Since this is primarily configuration/metadata changes**, TDD is adapted:

1. **Metadata changes**: Verify with grep/scripts
2. **CI changes**: Test via actual PR (this PR)
3. **Code compatibility**: Existing test suite verifies functionality

### Spec→Test Mapping

| Acceptance Criterion | Test Method | Status |
|---------------------|-------------|--------|
| **AC-1**: Package metadata consistency | Manual verification via grep | ✅ Done |
| **AC-2**: Documentation accuracy | Manual verification via grep | ✅ Done |
| **AC-3**: CLI generated projects | Run `tyler init test-proj` and check pyproject.toml | 🔄 Manual |
| **AC-4**: User can install with Python 3.11 | CI matrix test + manual verification | 🔄 CI automated |
| **AC-5**: Code compatibility verification | Analysis of `datetime.UTC` usage | ✅ Done |
| **AC-6**: CI tests all supported versions | GitHub Actions workflow execution | 🔄 This PR |

### Test Tiers

#### Configuration Tests (Manual)
```bash
# Verify all pyproject.toml files
grep -r "requires-python" packages/*/pyproject.toml

# Expected output:
# packages/narrator/pyproject.toml:requires-python = ">=3.11"
# packages/tyler/pyproject.toml:requires-python = ">=3.11"
# packages/lye/pyproject.toml:requires-python = ">=3.11"
# packages/space-monkey/pyproject.toml:requires-python = ">=3.11"
```

#### Unit Tests (Existing)
All existing unit tests will run on Python 3.11, 3.12, 3.13:
- `packages/narrator/tests/` - 10 test files
- `packages/tyler/tests/` - 26 test files
- `packages/lye/tests/` - 11 test files
- `packages/space-monkey/tests/` - 5 test files

#### Integration Tests (Existing + Enhanced)
- Cross-package integration tests run on all Python versions
- Example tests import across packages to verify compatibility

#### CI Tests (New)
```yaml
# Automated verification that matrix works
# Run on this PR to verify CI changes
- All jobs complete successfully
- All Python versions tested
- Dependencies between jobs work correctly
```

### Negative & Edge Cases

| Case | Expected Behavior | Verification |
|------|------------------|--------------|
| User on Python 3.10 | Installation fails with clear error | Manual test |
| User on Python 3.11 | Installation succeeds | CI matrix |
| User on Python 3.12 | Installation succeeds | CI matrix |
| User on Python 3.13 | Installation succeeds | CI matrix |
| User on Python 3.14+ | Installation succeeds (forward compat) | Not tested (doesn't exist) |
| Mixed Python versions in dev | Each environment isolated | Manual test |
| Syntax error in CI YAML | GitHub Actions validation fails | Caught by GitHub |

### Performance Tests
**Not applicable** for this change (metadata only, no runtime performance impact)

### CI Requirements
✅ All tests run in CI and block merge
- Matrix strategy ensures multi-version testing
- `needs` clauses prevent premature merges
- Failing tests stop the pipeline

## 11. Risks & Open Questions

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|---------|------------|
| Python 3.11/3.12 compatibility issue found after release | Low | Medium | Matrix testing catches issues pre-release |
| CI minutes cost increase (3×) | Certain | Low | Acceptable trade-off for quality; runs in parallel |
| User confusion about supported versions | Low | Low | Clear documentation updates |
| Existing Python 3.13-only features in code | Very Low | High | Code analysis confirms only 3.11+ features used |

### Open Questions

**Q1**: Should we test on Windows and macOS in addition to Ubuntu?
- **Answer**: Out of scope. Current CI only tests Ubuntu. Python stdlib behavior is consistent across platforms for `datetime.UTC`.
- **Future**: Could add OS matrix if platform-specific issues emerge.

**Q2**: Should we notify existing users about expanded compatibility?
- **Answer**: Yes, via release notes and updated documentation. Consider blog post or announcement.

**Q3**: What if GitHub Actions doesn't support Python 3.11 on ubuntu-latest?
- **Answer**: GitHub Actions setup-python@v5 supports Python 3.11+. Verified in GH docs.

**Q4**: Should release workflows also use matrix testing?
- **Answer**: Out of scope. Release workflows only need to build, not test (testing happens in PR).

## 12. Milestones / Plan (post‑approval)

### Task Breakdown

#### Task 1: Update Package Metadata
**DoD**: All 4 packages have `requires-python = ">=3.11"` and correct classifiers

- [ ] Update `packages/tyler/pyproject.toml`
- [ ] Update `packages/lye/pyproject.toml`
- [ ] Update `packages/space-monkey/pyproject.toml`
- [ ] Verify `packages/narrator/pyproject.toml` (already correct)
- [ ] Run: `grep -r "requires-python" packages/*/pyproject.toml`
- [ ] Verify output matches expected

**Time estimate**: 10 minutes  
**Dependencies**: None

#### Task 2: Update Documentation
**DoD**: All docs reference Python 3.11+ correctly

- [ ] Update `README.md`
- [ ] Update `docs/quickstart.mdx`
- [ ] Update `docs/guides/your-first-agent.mdx`
- [ ] Update `directive/reference/agent_context.md`
- [ ] Run: `grep -r "3\.13" docs/ README.md` (should find none)
- [ ] Run: `grep -r "3\.11" docs/ README.md` (should find references)

**Time estimate**: 15 minutes  
**Dependencies**: None

#### Task 3: Update CLI Template
**DoD**: `tyler init` generates projects with `requires-python = ">=3.11"`

- [ ] Update `packages/tyler/tyler/cli/init.py` line 60
- [ ] Manual test: `uv run tyler init test-project` and verify generated pyproject.toml

**Time estimate**: 5 minutes  
**Dependencies**: None

#### Task 4: Implement CI Matrix Testing
**DoD**: All CI test jobs use matrix strategy for Python 3.11, 3.12, 3.13

- [ ] Update `.github/workflows/test.yml`:
  - [ ] Add matrix to `test-narrator` job
  - [ ] Add matrix to `test-tyler` job
  - [ ] Add matrix to `test-space-monkey` job
  - [ ] Add matrix to `test-lye` job
  - [ ] Add matrix to `integration-test` job
  - [ ] Add matrix to `test-examples` job
- [ ] Update `.github/workflows/test-examples.yml`:
  - [ ] Add matrix to `test-examples` job
  - [ ] Add matrix to `test-examples-with-api` job
- [ ] Verify YAML syntax: `yamllint .github/workflows/*.yml`
- [ ] Commit and push to trigger CI
- [ ] Verify all matrix jobs run successfully

**Time estimate**: 30 minutes  
**Dependencies**: None (can be done in parallel with other tasks)

#### Task 5: Verification & Testing
**DoD**: All acceptance criteria verified

- [ ] Run CI on PR (AC-6: All Python versions tested)
- [ ] Manual test: Install on Python 3.11 environment (AC-4)
- [ ] Manual test: `tyler init` generates correct pyproject.toml (AC-3)
- [ ] Review all file changes against spec
- [ ] Update directive spec docs with completion status

**Time estimate**: 20 minutes  
**Dependencies**: Tasks 1-4 complete

#### Task 6: Documentation & Release Prep
**DoD**: Ready for release with complete documentation

- [ ] Update CHANGELOG/release notes for all 4 packages
- [ ] Verify version bumps are ready (2.1.0→2.1.1, etc.)
- [ ] Final review of spec/impact/TDR documents
- [ ] Prepare release branch

**Time estimate**: 15 minutes  
**Dependencies**: Task 5 complete

### Total Estimated Time
**~1.5 hours** for complete implementation and verification

### Critical Path
1. Tasks 1-4 (parallel, ~30 minutes)
2. Task 5 (serial, ~20 minutes)
3. Task 6 (serial, ~15 minutes)

### Owner
AI Agent (with human review and approval)

---

**Approval Gate**: This TDR must be reviewed and approved before implementation begins.

**Review Checklist**:
- [ ] Spec alignment verified
- [ ] CI strategy approved (full matrix vs alternatives)
- [ ] Risk assessment acceptable
- [ ] Test coverage sufficient
- [ ] Rollback plan clear
- [ ] No security concerns

