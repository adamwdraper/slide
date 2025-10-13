# Spec: Python 3.11 Minimum Version Consistency

**Feature name**: Python 3.11 Minimum Version Consistency  
**One-line summary**: Standardize all Slide packages to require Python 3.11+ based on actual code dependencies  

---

## Problem

Users attempting to install Slide packages are encountering dependency resolution errors because:
1. Package metadata specified inconsistent Python version requirements (3.11 for narrator, 3.13 for tyler/lye/space-monkey)
2. The actual code requirement is Python 3.11+ (due to `datetime.UTC` usage throughout the codebase)
3. Documentation incorrectly stated Python 3.13+ as the requirement
4. When users ran `uv init` without specifying Python version, it defaulted to 3.11, causing install failures

This creates a poor onboarding experience and prevents users from installing packages even when they have compatible Python versions (3.11 or 3.12).

## Goal

All Slide packages should consistently require Python 3.11+ in:
- Package metadata (`pyproject.toml` files)
- Documentation (README, quickstart, guides)
- Code generation (CLI init command)
- Internal reference documents

## Success Criteria

- [x] Users with Python 3.11+ can successfully install all Slide packages without version conflicts
- [x] All documentation accurately reflects Python 3.11+ requirement
- [x] Package classifiers correctly list supported Python versions (3.11, 3.12, 3.13)
- [x] No conflicting version requirements across the monorepo

## User Story

As a developer wanting to use Slide, I want to install the packages with Python 3.11+, so that I don't encounter confusing dependency resolution errors when I have a compatible Python version.

## Flow / States

**Happy Path:**
1. User has Python 3.11, 3.12, or 3.13 installed
2. User runs `uv init my-project` (defaults to their Python version)
3. User runs `uv add slide-tyler slide-lye slide-narrator`
4. Packages install successfully without errors

**Edge Case - Older Python:**
1. User has Python 3.10 or earlier
2. User attempts to install Slide packages
3. Clear error message indicates Python 3.11+ is required
4. Error message explains why (references documentation)

## UX Links

- User error report: Customer attempted installation with Python 3.11 and received "No solution found" errors
- Documentation affected: 
  - `/docs/quickstart.mdx`
  - `/docs/guides/your-first-agent.mdx`
  - `/README.md`

## Requirements

**Must:**
- Update all package `requires-python` fields to `>=3.11`
- Update all package classifiers to include Python 3.11, 3.12, 3.13
- Update all user-facing documentation to state Python 3.11+ requirement
- Update CLI init command to generate projects with Python 3.11+ requirement
- Maintain consistency across all four packages (tyler, lye, narrator, space-monkey)
- Update CI workflows to test against Python 3.11, 3.12, and 3.13 using matrix strategy

**Must not:**
- Break existing users on Python 3.11+
- Introduce new Python 3.13-specific features without evaluation
- Create version mismatches between packages

## Acceptance Criteria

**AC-1: Package Metadata Consistency**
- Given all four packages (tyler, lye, narrator, space-monkey)
- When examining their `pyproject.toml` files
- Then all should have `requires-python = ">=3.11"`
- And all should list Python 3.11, 3.12, 3.13 in classifiers

**AC-2: Documentation Accuracy**
- Given documentation files (README, quickstart, guides)
- When users read installation instructions
- Then Python 3.11+ should be clearly stated as the requirement
- And installation commands should not force Python 3.13

**AC-3: CLI Generated Projects**
- Given a user runs `tyler init my-project`
- When the pyproject.toml is generated
- Then it should specify `requires-python = ">=3.11"`

**AC-4: User Can Install with Python 3.11**
- Given a user has Python 3.11 installed
- When they run `uv init . && uv add slide-tyler slide-lye slide-narrator`
- Then packages install without version conflict errors

**AC-5: Code Compatibility Verification**
- Given the codebase uses `datetime.UTC`
- When analyzing Python version requirements
- Then Python 3.11 is confirmed as the actual minimum (UTC added in 3.11)
- And no Python 3.12+ or 3.13+ exclusive features are used

**AC-6: CI Tests All Supported Versions**
- Given the CI workflows (test.yml, test-examples.yml)
- When tests run on pull requests
- Then all three Python versions (3.11, 3.12, 3.13) are tested using matrix strategy
- And test failures on any version prevent merge

## Non-Goals

- Refactoring code to support Python 3.10 or earlier
- Creating a meta-package for Slide
- Changing the actual code's Python version dependencies
- Testing Python versions beyond 3.13

