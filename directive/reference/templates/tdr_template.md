# Technical Design Review (TDR) — <Feature Name>

**Author**: <agent or engineer>  
**Date**: <YYYY-MM-DD>  
**Links**: Spec (`/directive/specs/<feature>/spec.md`), Impact (`/directive/specs/<feature>/impact.md`), related issues/PRs, designs

---

## 1. Summary
What we are building and why (1–2 short paragraphs).

## 2. Decision Drivers & Non‑Goals
- Drivers: <performance target, security constraints, deadlines, costs>
- Non‑Goals: <explicitly out of scope for this iteration>

## 3. Current State — Codebase Map (concise)
Purpose: brief orientation so the design references real modules, contracts, and tests.
- Key modules/services relevant to this feature
- Existing data models/tables & hotspots
- External contracts (APIs, events) in scope
- Observability currently available (logs/metrics/dashboards)

## 4. Proposed Design (high level, implementation‑agnostic)
- Overall approach & responsibilities per component
- Interfaces & data contracts (schemas, examples)
- Error handling, idempotency, retries
- Performance expectations and back‑pressure behavior

## 5. Alternatives Considered
- Option A — pros/cons  
- Option B — pros/cons  
- Why the chosen option

## 6. Data Model & Contract Changes
- Tables/collections & migrations (high level; examples)  
- API/event changes (request/response, topics, versions)  
- Backward compatibility & deprecation plan

## 7. Security, Privacy, Compliance
- AuthN/AuthZ model affected?  
- Secrets management & PII handling  
- Threat model notes and mitigations

## 8. Observability & Operations
- Logs/metrics/traces to add  
- Dashboards/alerts to create or update  
- Runbooks & SLOs (targets and alert thresholds)

## 9. Rollout & Migration
- Feature flags & guardrails  
- Data backfill or sync strategy  
- Revert plan and blast radius

## 10. Test Strategy & Spec Coverage (TDD)
- TDD commitment: write failing tests before implementation; confirm failure; implement; refactor.  
- Spec→Test mapping: list each Spec Card acceptance criterion and the planned test ID(s).  
- Test tiers: unit, contract, integration, E2E as appropriate.  
- Negative & edge cases: list explicitly.  
- Performance tests: targets & harness.  
- CI: all tests must run in CI and block merge.

## 11. Risks & Open Questions
- Known risks and their mitigations  
- Open questions + proposed paths to resolve

## 12. Milestones / Plan (post‑approval)
- Task breakdown with DoD per task (tests passing, lint/format, spec criteria met)  
- Dependencies/owners

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved in the PR.
