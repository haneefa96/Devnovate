# MUNSHI — AI CODING ASSISTANT CREDIT USAGE PLAN

## 1. Purpose

This document defines how the team should use AI coding assistants such as Claude, Gemini, Kiro and other coding agents with limited free-tier credits.

The goal is to complete Munshi without wasting credits on repeated explanations, unnecessary code generation or unrelated modifications.

## 2. Core Strategy

Do not ask an AI coding assistant to build the entire application in one prompt.

Instead:

- Give it the project documentation.
- Assign one module at a time.
- Define the files it can modify.
- Give it explicit input and output contracts.
- Require tests before completion.
- Save implementation progress in Git.
- Maintain a short progress document.

One AI task should produce one verifiable result.

## 3. Recommended AI Tools

Use whichever coding assistant is currently available.

| Task | Suitable tool |
|---|---|
| Architecture review | Claude / Gemini |
| Backend implementation | Claude / Gemini / Kiro |
| Frontend implementation | Kiro / Claude / Gemini |
| Debugging | Any available coding assistant |
| Documentation | Any available coding assistant |
| Code review | A different AI assistant if available |

Do not depend on one particular model or subscription.

## 4. Development Order

### Phase 1: Technical verification

Priority: Critical.

Tasks:
1. Set up Python and Node environments.
2. Verify Hindsight SDK.
3. Verify Groq models.
4. Verify Band SDK.
5. Test one customer memory flow.
6. Verify timestamps and evidence IDs.

AI usage:
Use one focused task per dependency.

Do not ask AI to generate the complete application yet.

Deliverable:
A working technical proof of concept.

### Phase 2: Backend foundation

Implement:
- Configuration.
- Database connection.
- SQLModel entities.
- Database seed data.
- Base FastAPI application.
- Error handling.

Tests:
- Database creation.
- Table relationships.
- CRUD operations.
- Seed data.

Deliverable:
A functioning backend foundation.

### Phase 3: Business rules and readiness

Implement:
- GSTIN validation.
- Invoice validation.
- PO checks.
- Duplicate checks.
- Document checks.
- Readiness result combination.

Tests:
- Each R1–R9 rule.
- READY.
- BLOCKER.
- CONFLICT.
- UNCERTAIN.

Deliverable:
A working invoice readiness engine without requiring an LLM.

### Phase 4: Memory and agents

Implement:
- Hindsight client.
- Bank setup.
- Retain templates.
- Recall.
- Reflect.
- Evidence parsing.
- Collector.
- Risk agent.
- Memory retry queue.

Tests:
- Event retention.
- Customer isolation.
- Evidence retrieval.
- Belief changes.
- Risk changes.

Deliverable:
A working memory-driven decision engine.

### Phase 5: Simulator and evaluation

Implement:
- Customer profiles.
- Hidden traits.
- Deterministic payment outcomes.
- Template replies.
- Scenario files.
- Evaluation A/B/C.
- Metrics and charts.

Tests:
- Same seed produces same outcomes.
- All simulation rules work.
- Evaluation versions use the same scenarios.
- Results are reproducible.

Deliverable:
A working evaluation system.

### Phase 6: API and Band integration

Implement:
- All planned API endpoints.
- Approval workflow.
- Inbound messages.
- Payments.
- Risk alerts.
- Simulation endpoints.
- Band bridge.
- Band command parsing.

Deliverable:
All backend modules communicate correctly.

### Phase 7: Frontend

Implement screens in this order:

1. Dashboard.
2. Customer page.
3. New invoice and readiness.
4. Approvals inbox.
5. Risk alerts.
6. Simulation console.
7. Evaluation.

Develop shared components before duplicating UI code.

Deliverable:
A complete application interface connected to the backend.

### Phase 8: Integration and final testing

Tasks:
- Run the complete application.
- Execute the golden scenario.
- Test invoice readiness.
- Test approval workflow.
- Test customer contact changes.
- Test payment behaviour changes.
- Test Hindsight memory updates.
- Test evaluation charts.
- Rehearse the demo.

Deliverable:
A stable hackathon demonstration.

## 5. Rules for Saving AI Credits

### Rule 1: Avoid repeated project explanations

Always start an AI coding session with:
- README.md
- AGENTS.md
- Relevant module contract.
- Current progress information.

Do not repeatedly paste the entire project document when a specific module is being implemented.

### Rule 2: Ask for inspection before modification

First ask the AI to inspect:
- Existing folders.
- Existing files.
- Installed dependencies.
- Current implementation.
- Existing tests.

It must not recreate working files unnecessarily.

### Rule 3: Use small implementation tasks

Bad request:
"Build the entire backend with all features."

Better request:
"Implement only GSTIN format and checksum validation in checks/gstin.py. Add unit tests for valid and invalid examples. Do not modify other modules."

### Rule 4: Require test results

Every implementation task must end with:
- Files created.
- Files modified.
- Tests executed.
- Test results.
- Remaining issues.
- Next recommended task.

### Rule 5: Maintain progress between sessions

Maintain `docs/AI_PROGRESS.md`.

Update it after every completed task.

Record:
- Completed modules.
- Pending modules.
- Current errors.
- Dependencies verified.
- Git commit hash.
- Next exact task.

### Rule 6: Avoid unnecessary model calls

- Use template customer replies during evaluation.
- Use LLM-generated replies only when needed for the interactive demo.
- Cache Groq responses.
- Do not regenerate unchanged prompts.
- Do not repeatedly run the full evaluation.
- Do not use an LLM for deterministic calculations.

## 6. Evaluation Credit Strategy

The evaluation can generate significant LLM usage.

The full evaluation is expected to involve approximately:
- 12 customers.
- 6 simulated months.
- 140 invoices.
- 600 retained events per seed for version C.
- Several hundred reflect calls.

Recommended approach:

**First run:**
- 6 customers.
- 1 seed.
- Verify all three versions.

**Second run:**
- Full 12-customer evaluation.
- Seeds 1, 2 and 3.
- Template replies.
- Run one seed at a time.
- Keep the cache.

Run the full evaluation at most twice, preferably overnight.

If API limits are restrictive:
- Reduce to 8 customers.
- Use 2 seeds.
- Clearly document the reduced evaluation configuration.

Never present a reduced evaluation as the original full evaluation.

## 7. Git and Progress Management

After each independently tested module:

1. Review the changes.
2. Run relevant tests.
3. Commit the working implementation.
4. Update AI_PROGRESS.md.
5. Move to the next task.

Suggested commit names:

- `setup: initialize backend and frontend`
- `feat(db): add SQLModel entities`
- `feat(checks): implement invoice readiness`
- `feat(memory): add Hindsight adapter`
- `feat(agents): implement Collector and Risk`
- `feat(sim): add deterministic customer simulation`
- `feat(eval): implement A/B/C evaluation`
- `feat(api): add application endpoints`
- `feat(band): add agent room integration`
- `feat(ui): implement dashboard and application pages`

## 8. Reusable Prompt for AI Coding Assistants

Before every implementation task, use this prompt:

"You are working on the Munshi project.

Read README.md, AGENTS.md, DEVELOPMENT_RULES.md, ARCHITECTURE.md and the relevant module contract before making changes.

First inspect the existing implementation and identify what is already complete.

Your task is limited to the module and files explicitly assigned.

Do not:
- Rebuild existing working functionality.
- Modify unrelated modules.
- Change shared interfaces without approval.
- Add unnecessary dependencies.
- Invent API or SDK methods.
- Hardcode credentials.
- Generate features outside the project scope.

Implement the requested functionality using the existing project architecture.

Add appropriate tests and execute them.

At the end, report:
1. Files created.
2. Files modified.
3. Functionality implemented.
4. Tests executed and their results.
5. Known limitations.
6. Any integration requirements.
7. Exact next recommended task.

If an essential dependency or interface is unclear, stop and report the issue instead of guessing."

## 9. Final Credit-Saving Principle

The objective is not to generate the maximum amount of code.

The objective is to generate the smallest amount of correct, tested and integration-ready code.

Prioritise working memory, invoice readiness, customer behaviour changes and evaluation over cosmetic improvements.