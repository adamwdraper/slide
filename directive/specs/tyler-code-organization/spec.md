# Spec — Tyler Code Organization & Maintainability Refactor

**Feature name**: Tyler Code Organization & Maintainability Refactor  
**One-line summary**: Restructure Tyler's core codebase to improve maintainability, testability, and developer experience without changing external APIs or behavior.

---

## Problem

The Tyler package has grown organically and now suffers from:
1. **Large, monolithic classes** — The `Agent` class is 1,598 lines with multiple responsibilities (LLM communication, tool management, streaming, delegation, message creation)
2. **Code duplication** — Streaming and non-streaming implementations share ~70% logic but are implemented separately, leading to maintenance burden and potential bugs
3. **Complex tool registration** — Tool loading has nested conditionals and repetitive logic that's hard to maintain and extend
4. **Inconsistent patterns** — Tool calls are handled as both dicts and objects, requiring normalization in multiple places
5. **Limited extensibility** — Adding new protocol adapters or tool types requires significant code changes

This technical debt increases the risk of bugs, slows feature development, and makes onboarding new contributors difficult.

## Goal

Refactor Tyler's internal architecture to create a cleaner, more maintainable codebase while:
- Maintaining 100% backward compatibility with existing APIs
- Keeping all existing tests passing
- Improving code organization and separation of concerns
- Reducing code duplication
- Making the codebase easier to understand and extend

## Success Criteria

- [ ] All existing tests pass without modification
- [ ] Test coverage remains at or above current levels (>80%)
- [ ] No breaking changes to public APIs
- [ ] Code complexity metrics improve (reduced cyclomatic complexity, shorter methods)
- [ ] Developer feedback: easier to understand and navigate the codebase
- [ ] Documentation updated to reflect new structure
- [ ] Performance benchmarks show no regression

## User Story

As a **Tyler framework maintainer or contributor**, I want **a well-organized, modular codebase with clear separation of concerns**, so that **I can quickly understand the code, fix bugs confidently, and add new features without breaking existing functionality**.

As a **Tyler user**, I want **the framework to remain stable and backward-compatible**, so that **I can upgrade to new versions without changing my code**.

## Flow / States

### Happy Path: Safe Refactoring Process
1. **Pre-refactor**: Run full test suite, capture baseline metrics
2. **Refactor Phase 1**: Extract smaller classes from Agent (e.g., MessageFactory, ToolManager)
3. **Test**: All tests pass, no behavior changes
4. **Refactor Phase 2**: Reduce duplication in streaming logic
5. **Test**: All tests pass, no behavior changes
6. **Refactor Phase 3**: Continue with remaining improvements
7. **Final validation**: Full test suite, integration tests, performance benchmarks

### Edge Case: Discovering Missing Test Coverage
1. Refactor reveals untested code path
2. Add test to cover the gap BEFORE completing refactor
3. Verify test fails appropriately
4. Complete refactor
5. Verify test passes

## UX Links

- Current codebase: `/packages/tyler/tyler/models/agent.py` (1,598 lines)
- Analysis document: (in this PR description)
- Architecture diagrams: (to be created in TDR)

## Requirements

### Must
- Maintain 100% backward compatibility for all public APIs
- Keep all existing tests passing
- Maintain or improve test coverage
- Use type hints consistently throughout refactored code
- Follow existing code style and conventions
- Document all new internal interfaces
- Ensure no performance regression

### Must Not
- Change any public API signatures
- Break existing user code
- Remove functionality
- Introduce new external dependencies
- Change observable behavior (except for internal implementation details)

## Acceptance Criteria

**Test Safety**
- Given the current test suite, when running all tests after each refactoring step, then all tests must pass without modification
- Given the test coverage report, when comparing before/after refactoring, then coverage must remain ≥80% and not decrease
- Given any discovered untested code, when identified during refactoring, then tests must be added before proceeding

**Code Organization**
- Given the Agent class, when refactored, then it should be <500 lines with clear single responsibility
- Given tool registration logic, when refactored, then each tool type handler should be in its own strategy class
- Given message creation logic, when refactored, then it should be centralized in a MessageFactory class
- Given streaming vs non-streaming logic, when refactored, then shared code should be extracted to common methods (reducing duplication by >50%)

**Backward Compatibility**
- Given existing Tyler user code, when upgrading to refactored version, then no code changes should be required
- Given all public API signatures, when comparing before/after, then they must be identical
- Given integration tests, when running against refactored code, then all must pass without modification

**Performance**
- Given performance benchmarks, when comparing before/after refactoring, then execution time must not increase by >5%
- Given memory usage metrics, when comparing before/after, then memory consumption must not increase significantly

**Documentation**
- Given the refactored code, when reviewing, then all new internal classes and methods must have docstrings
- Given the architecture, when reviewing, then a diagram must show the new component relationships
- Given the codebase, when onboarding a new developer, then they should understand the structure in <2 hours (measured via feedback)

**Negative Cases**
- Given malformed tool calls, when processed by refactored code, then errors should be handled identically to original
- Given edge cases in streaming, when processing, then behavior must match original implementation exactly
- Given concurrent tool execution, when running, then race conditions must not be introduced

## Non-Goals

### Not in this refactor
- Changing external APIs or adding new features
- Rewriting narrator or lye packages
- Changing the LLM provider integration
- Modifying the MCP or A2A protocol implementations
- Performance optimizations beyond maintaining current performance
- Adding new observability beyond what exists
- Changing the CLI interface
- Modifying database schemas or storage

### Future work (not this PR)
- Adding new tool types
- Improving error messages
- Performance optimizations
- Additional observability features
- New protocol adapters

