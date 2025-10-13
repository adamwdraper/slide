# Impact Analysis — Python 3.11 Minimum Version Consistency

## Modules/packages likely touched

### Package Metadata
- `/packages/tyler/pyproject.toml` - Update `requires-python` from `>=3.13` to `>=3.11`
- `/packages/lye/pyproject.toml` - Update `requires-python` from `>=3.13` to `>=3.11`
- `/packages/space-monkey/pyproject.toml` - Update `requires-python` from `>=3.13` to `>=3.11`
- `/packages/narrator/pyproject.toml` - Already correct at `>=3.11` (no change needed)

### Package Classifiers
- `/packages/tyler/pyproject.toml` - Add `Programming Language :: Python :: 3.11` to classifiers
- `/packages/lye/pyproject.toml` - Add `Programming Language :: Python :: 3.11` to classifiers
- `/packages/space-monkey/pyproject.toml` - Classifiers already include 3.11 (verify consistency)

### Documentation
- `/README.md` - Update installation instructions (Python 3.13 → 3.11)
- `/docs/quickstart.mdx` - Update requirements note and installation steps
- `/docs/guides/your-first-agent.mdx` - Add Python 3.11 requirement note
- `/directive/reference/agent_context.md` - Update Python version reference

### Code Generation
- `/packages/tyler/tyler/cli/init.py` - Update generated `pyproject.toml` template from `>=3.12` to `>=3.11`

### CI/CD Workflows
- `/.github/workflows/test.yml` - Add Python version matrix (3.11, 3.12, 3.13) to all test jobs
- `/.github/workflows/test-examples.yml` - Add Python version matrix to example tests

## Contracts to update (APIs, events, schemas, migrations)

### PyPI Package Metadata
**Breaking Change Classification**: This is a **relaxation** of constraints, not a breaking change
- Previous: Required Python 3.13+
- New: Requires Python 3.11+
- Impact: Users with Python 3.11 and 3.12 can now install packages (expands compatibility)

### Dependency Resolution
- **Narrator** already requires `>=3.11` - no contract change
- **Tyler, Lye, Space Monkey** currently require `>=3.13` on PyPI
  - Next published version will allow `>=3.11`
  - Existing published versions (with 3.13 requirement) remain unchanged on PyPI
  - This is backward compatible - users on 3.13 are unaffected

### Generated Project Templates
- `tyler init` command generates projects with new Python requirement
- Existing projects generated with old CLI are unaffected
- Users can manually update their `requires-python` if desired

## Risks

### Security
**Risk Level**: Low
- No security implications from Python version change
- Python 3.11 is a maintained Python version with security updates
- No new dependencies or code changes introduced

**Mitigation**: None needed

### Performance/Availability
**Risk Level**: None
- No performance impact - same code runs on all Python 3.11+ versions
- `datetime.UTC` performance is identical across supported versions
- No new runtime dependencies added

### Data integrity
**Risk Level**: None
- No data model changes
- No database migrations required
- No changes to serialization/deserialization logic

### Compatibility
**Risk Level**: Low

**Potential Issues:**
1. **PyPI Version Constraints**: Existing published packages on PyPI will retain their 3.13 requirement until new versions are published
   - **Impact**: Users must wait for new package releases to benefit from relaxed constraint
   - **Mitigation**: Document the version numbers where 3.11 support begins

2. **User Workspace Dependencies**: Users who pinned to exact versions may not see the update
   - **Impact**: May need to explicitly update package versions
   - **Mitigation**: Include upgrade instructions in release notes

3. **CI Execution Time**: Matrix testing across 3 Python versions will increase CI time
   - **Impact**: Test suite will run 3x (once per version)
   - **Mitigation**: Jobs run in parallel, so wall-clock time increase is minimal
   - **Benefit**: Catches version-specific issues before they reach users

### Documentation Consistency
**Risk Level**: Low
- Risk of missed documentation references
- **Mitigation**: Grep search for "3.13" and "3.12" references across docs to ensure completeness

## Observability needs

### Logs
- No new logging required
- Installation errors should already be captured by package managers (uv/pip)

### Metrics
- **Recommended** (not required for this change): Track Python version distribution in Weave telemetry
  - Would help understand actual user Python version adoption
  - Could inform future Python version decisions
  - Implementation: Out of scope for this change

### Alerts
- No new alerts needed
- Package installation failures are client-side, not server-side

## Verification Plan

### Pre-Release Testing
1. **Test Installation on Python 3.11**
   ```bash
   # Clean environment test
   python3.11 -m venv test-env-311
   source test-env-311/bin/activate
   pip install dist/slide-tyler-*.whl dist/slide-lye-*.whl dist/slide-narrator-*.whl
   python -c "from tyler import Agent; from lye import WEB_TOOLS; from narrator import Thread; print('Success')"
   ```

2. **Test Installation on Python 3.12**
   ```bash
   # Clean environment test
   python3.12 -m venv test-env-312
   source test-env-312/bin/activate
   pip install dist/slide-tyler-*.whl dist/slide-lye-*.whl dist/slide-narrator-*.whl
   python -c "from tyler import Agent; from lye import WEB_TOOLS; from narrator import Thread; print('Success')"
   ```

3. **Test Installation on Python 3.13**
   ```bash
   # Clean environment test (ensure we didn't break existing)
   python3.13 -m venv test-env-313
   source test-env-313/bin/activate
   pip install dist/slide-tyler-*.whl dist/slide-lye-*.whl dist/slide-narrator-*.whl
   python -c "from tyler import Agent; from lye import WEB_TOOLS; from narrator import Thread; print('Success')"
   ```

4. **Test with uv workflow** (reproducing user's scenario)
   ```bash
   mkdir test-uv-install
   cd test-uv-install
   uv init .  # Should detect system Python (could be 3.11, 3.12, or 3.13)
   uv add slide-tyler slide-lye slide-narrator
   # Should succeed regardless of detected Python version (3.11+)
   ```

### Post-Release Monitoring
- Monitor GitHub issues for installation problems
- Check PyPI download statistics by Python version (if available)
- Respond to any reported incompatibilities within 24 hours

### Automated Testing via CI Matrix
All Python versions (3.11, 3.12, 3.13) will be tested automatically in CI on every PR.

## Release Coordination

### Version Bumps Required
All packages should be released together to maintain consistency:
- `slide-tyler`: 2.1.0 → 2.1.1 (patch - metadata fix)
- `slide-lye`: 1.0.1 → 1.0.2 (patch - metadata fix)  
- `slide-narrator`: 1.0.2 → 1.0.3 (patch - consistency update)
- `slide-space-monkey`: 1.0.0 → 1.0.1 (patch - metadata fix)

### Release Notes
Include in all package release notes:
```markdown
## Changed
- Relaxed Python version requirement from 3.13+ to 3.11+ to reflect actual code dependencies
- Updated package classifiers to indicate Python 3.11, 3.12, 3.13 support

## Fixed
- Installation errors for users with Python 3.11 or 3.12
- Documentation inconsistencies regarding minimum Python version
```

### Communication
- Update main README.md with prominent note about version compatibility
- Consider blog post or announcement about improved Python version support
- Update quickstart guide with clear Python version requirements

