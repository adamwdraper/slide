# AI Agent Technical Context

This file provides persistent technical guidance.  
Attach this file + the feature spec to the agent for every build.  

---

## Languages & Frameworks
- Backend: Python (3.13+) 
- Package management: uv (Python)

## Project Conventions


## Security & Privacy
- Secrets in env vars only, never hardcoded  
- Input validation on all external interfaces  
- No PII in logs  

## Performance & Reliability


## Dependencies
- Use only approved packages  
- Pin versions in `pyproject.toml` / `package.json`  
- Justify any new external dependency in PR description  

## Architecture Guidelines
- Follow layered architecture (API → service → data)  
- Reuse existing utilities before adding new ones  
- Write modular, testable code  

## Documentation
- Docstrings for all public functions/classes  
- Update README if setup/usage changes  
- Add inline comments for non-obvious logic  

## Commit & PR Conventions
- Conventional commits (`feat:`, `fix:`, `chore:`)  
- Every PR must include a Spec Card (`directive/specs/feature-name.md`)  

---

*This file is the persistent guidance. Do not repeat it in specs; keep specs outcome-focused.*  

## Test-Driven Development (TDD) Rules

1) **Write a failing test first** for each acceptance criterion.  
2) **Confirm failure** to validate the test’s effectiveness.  
3) **Implement minimal code** to pass.  
4) **Refactor** keeping the suite green.  

**Standards**  
- Backend tests: pytest; Frontend: Jest/Playwright  
- Naming: map tests to Spec acceptance criteria (e.g., `AC-3`)  
- Commit order per task: `test:` → `feat:` → `refactor:`  
- CI blocks merge unless all tests pass  


