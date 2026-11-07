# DEVELOPMENT RULES

## 1. Coding standards

- Python 3.11+, type hints on public functions, `ruff` (line length 100). Pydantic models for every JSON boundary (reflect output, API bodies, policy interfaces).
- TypeScript `strict`; no `any` on API data; types live in `frontend/src/types.ts` and mirror API_DOCUMENTATION.md.
- Money is integer paise in code and DB; formatted only in `frontend/src/lib/format.ts`.
- No prompts in Python strings (use `agents/prompts/*.md`). No secrets in code. Dates in code come from `services/clock.py`, never `datetime.now()`.

## 2. Naming conventions

Python: `snake_case` files/functions, `PascalCase` classes, constants `UPPER_SNAKE`. Rule codes `R<n>_<NAME>`. Memory event ids `evt_<ulid or counter>`. Tags `customer:<id>`, `kind:<event>`. Frontend: components `PascalCase.tsx`, hooks `useThing.ts`. Branches below.

## 3. Folder ownership (from the project document)

| Owner | Folders |
|---|---|
| P1 memory lead | `backend/munshi/memory/`, `backend/munshi/agents/` |
| P2 simulator + eval | `backend/sim/`, `backend/eval/` |
| P3 backend + Band | `backend/munshi/db/`, `api/`, `checks/`, `band/`, `services/`, `llm/`, `config.py`, `main.py` |
| P4 frontend + story | `frontend/`, `docs/`, README |

If you work solo or with fewer people, you still treat each folder as a separate module with its own contract.

## 4. File modification rules

1. A task may change **only** the files listed under "Boundary" in `docs/MODULE_CONTRACTS.md` for that module, plus its tests.
2. Never edit files owned by another module. If you need a change there, write the request in the PR description or `docs/CHANGE_REQUESTS.md` (create if needed) and stop.
3. Shared contracts (`agents/policy.py`, `db/models.py`, `frontend/src/types.ts`, API shapes, `.env.example`) change only in a dedicated PR that also updates the relevant doc.
4. Do not reformat, rename, or move files you are not implementing. No drive-by refactors.
5. Do not add dependencies without listing them in the PR and updating `pyproject.toml` / `package.json` plus the stack table in README.
6. Do not create new top-level folders.

## 5. Rules to prevent unnecessary code changes

- Implement the placeholder as specified; do not add features outside the project scope (see "Out of scope" in docs/MODULE_CONTRACTS.md).
- Placeholder docstrings are the spec. Keep them accurate; do not delete them, update them.
- Prefer editing the function you were asked to implement over rewriting the file.
- If a test fails outside your module, report it; do not "fix" it.

## 6. Rules to prevent integration conflicts

### 6.1 Technology integration boundaries (MUST FOLLOW)

| Technology | Allowed module | Forbidden modules |
|------------|----------------|-------------------|
| Hindsight SDK (`hindsight_client`) | `memory/client.py` only | `agents/`, `checks/`, `api/`, `band/`, `llm/`, `sim/`, `eval/` |
| Groq SDK (`groq`) | `llm/groq_client.py` only | `agents/`, `checks/`, `api/`, `band/`, `memory/`, `sim/`, `eval/` |
| Band SDK (`band-sdk`) | `band/run_agents.py` only | `agents/`, `checks/`, `api/`, `memory/`, `llm/`, `sim/`, `eval/` |

**Enforcement**: CI must fail if these rules are violated.

### 6.2 Data source of truth rules

| Decision | Source |
|----------|--------|
| Amounts, dates, statuses | SQLite (source of truth) |
| Why customers pay/don't | Hindsight (knowledge layer) |
| Rule checks, days late, risk signals | Code (testable logic) |
| Message wording, JSON plans | LLM (from evidence passed in) |

### 6.3 Data write order

**For every state-changing endpoint**:
1. Write to SQLite first
2. Retain in Hindsight
3. Post to Band (if Band is reachable)

If step 2 or 3 fails, the response is still success and `memory_event.retained_at` stays NULL for background retry.

**Never**: Delete from SQLite without also deleting Hindsight memories by document id.

## 7. Git and branching

- `main` always runs (`make test` green). Protected; merge by PR.
- Branches: `feat/<module>-<short>`, `fix/<module>-<short>`, `docs/<topic>`. One module per branch.
- Commits: `<module>: <imperative summary>` e.g. `checks: implement R1-R4`.
- Never commit `.env`, `*.db`, `.cache/`, uploads. Evaluation results are committed together with the code git hash.

## 8. Dependency management

Backend: `uv add <pkg>` (updates `pyproject.toml` and lockfile; commit the lockfile). Frontend: `npm install <pkg>` (commit `package-lock.json`). Pin `hindsight-client`, `band-sdk` and the Hindsight Docker image tag on Day 1.

## 9. Testing requirements

- Fixed code (GSTIN, rules, readiness combiner, risk level rule, simulator rules, retain templates, parsing) needs unit tests before merge.
- Memory-dependent code: integration test + golden scenario; never assert exact LLM wording.
- LLM-dependent code: test structured outputs per model; test function-calling error handling; test rate-limit retry.
- A module is "done" only when its checklist in `docs/MODULE_CONTRACTS.md` passes.
- Run the golden scenario after any prompt or Hindsight version change.

## 10. Rules for AI coding assistants

1. Read `AGENTS.md`, this file, and the module's entry in `docs/MODULE_CONTRACTS.md`. Do not read the whole repo.
2. State which module you are implementing and list the files you will touch before writing code.
3. Resolve every `# VERIFY` marker against the installed SDK version, record the result in `docs/INTEGRATION_VERIFICATION.md`.
4. Stop after the module checklist passes; do not start the next module.

## 11. Technology verification rules (Day 1–2 spike)

### 11.1 Hindsight verification

| Check | How to verify | Fallback |
|-------|---------------|----------|
| Timestamp honoured | Retain event with timestamp T; recall with cutoff ≥T finds it | Use date-aware reflect prompts |
| First-person → experience facts | Retain "I sent invoice"; recall `kind:experience` | Tag with `kind:action` and filter |
| Observations change on contradiction | Add conflicting evidence; observe trend change | Manual trend comparison |
| Mental models auto-refresh | Trigger update; verify playbook card refreshes | Weekly refresh fallback |

### 11.2 Groq verification

| Check | How to verify | Fallback |
|-------|---------------|----------|
| Structured outputs per model | Parse `gpt-oss-120b` and `qwen3-32b` responses | Add schema validation |
| Function-calling error handling | Call with unsupported function schema | Log and retry |
| Rate-limit retry | Hit rate limit; verify exponential backoff | Cache + retry later |

### 11.3 Band verification

| Check | How to verify | Fallback |
|-------|---------------|----------|
| External Agent connection | Start agent; verify room posts | Web app (approvals inbox, risk alerts) |
| Message format parsing | Post formatted messages; verify regex matches | Log errors, human review |
| Web vs Band parity | Approve from web and Band; verify same outcome | Web only if Band unavailable |

## 12. Fallback rules

| Technology | Production fallback | Development fallback |
|------------|--------------------|---------------------|
| Hindsight | Cloud instance; local Docker | `memory/fake.py` (in-memory store) |
| Groq | Cloud API; cache layer | `llm/fake.py` (cached responses) |
| Band | Desktop app + external agents | Web app (approvals inbox, risk alerts) |

**Never** skip fallback testing. Run full integration tests with each fallback configured.
