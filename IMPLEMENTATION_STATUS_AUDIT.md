# Munshi Implementation Status Audit

**Audit date:** 2026-11-07  
**Scope:** Current implementation, external configuration, focused live checks, backend and frontend tests, and deployment files. Prompt 2 repaired the existing Hindsight adapter/outbox. Prompt 3 connected the existing Collector/Risk logic to operational workflows and aligned API/UI states.

The original PDF project document is present, but local PDF text extraction tools were unavailable and the file viewer exposed compressed PDF data rather than readable text. Its Markdown companion `PROJECT_ANALYSIS.md` and the available Markdown specifications were inspected; the PDF's full text was not independently verified.

## Status labels

- **COMPLETE AND VERIFIED** — behavior was exercised successfully by tests or a live check.
- **IMPLEMENTED BUT NOT VERIFIED** — implementation exists, but a successful run has not been established.
- **PARTIALLY IMPLEMENTED** — some required behavior works, but important pieces are missing or disconnected.
- **PLACEHOLDER / MOCK** — implementation returns canned behavior or simulates an external operation.
- **NOT IMPLEMENTED** — no implementation was found.
- **BLOCKED BY CREDENTIALS OR EXTERNAL DEPENDENCY** — work depends on missing credentials, an SDK, or an external service.

## Current status after Prompt 3

The Prompt 3 workflow changes are implemented and covered by focused mocked/local tests. Collector runs from a bounded lifecycle-managed daily loop; payment and inbound-message writes trigger Risk assessments after the SQLite commit. Daily drafts are deduplicated and carry persisted rationale/evidence. Payment-adjusted outstanding balances are used in dashboard/customer summaries. Invoice create and the frontend form now pass invoice GSTIN and PO amount into the existing readiness checks.

Approval, handoff, and delivery reporting are distinct: approval leaves an action `APPROVED` or `EDITED`; a guarded 09:00–19:00 IST WhatsApp handoff only opens a prefilled link; `SENT` is recorded only after the owner reports sending, and the API explicitly marks provider delivery unverified. Assessment failures are returned explicitly without undoing committed ledger writes. Hindsight availability is shown distinctly from empty memory.

The existing simulation clock can now advance by hours as well as days so the demo can reach a planned contact time. This does not connect the simulation world/injection engine or start the later evaluation stage. Band room delivery remains unavailable; web approval is the operative path. No authentication or automatic message sending was added.

Latest verified results: **316 passed, 1 failed, 2 skipped** in the backend suite; the only failure is the existing playbook-title assertion (`test_parse_playbook_json` expects “Payment Collection” while the parser returns “Payment Collection Playbook”). Frontend: **14 passed** and production build passed. Two Hindsight live integration tests were skipped in the normal test mode; no live Groq or Hindsight request was made for Prompt 3.

## 1. Executive summary

Munshi is a working local prototype, not an empty skeleton. It has a SQLModel/SQLite ledger with all twelve documented entities, seeded demo records, FastAPI routes, tested readiness rules, standalone Collector and Risk logic, a deterministic simulation engine, evaluation code, and seven React screens.

It is **not yet an end-to-end collections application**. The most important gaps are:

- The database is local SQLite, not Supabase; this is intentional for the current stage. The seeded demo data is hard-coded in Python and persisted in SQLite.
- Core Collector/Risk workflows now have normal triggers and a bounded daily worker. The existing deterministic simulation world and event-injection engine remain disconnected from the simulation HTTP routes.
- Hindsight Cloud is now verified through Munshi's wrapper using the installed `hindsight-client` 1.2.0 in the active backend Python 3.11.9 environment. Synthetic Cloud tests verified bank create/access, retain, recall, reflect, metadata/timestamp handling, customer and business-bank isolation, and outbox processing.
- A real Groq request succeeded using `openai/gpt-oss-120b`. The configured `qwen/qwen3-32b` customer model was not present in the model list returned during this audit.
- Band is not connected: credentials are absent, the SDK is not installed, and the bridge only logs what it would post.
- The latest backend full suite has **316 passed, 1 failed, and 2 skipped**; the single failure is the pre-existing playbook-title mismatch. Frontend tests and production build pass; frontend lint remains unavailable because there is no ESLint configuration.
- The project has its own Git repository and origin; current generated test/upload artifacts and a pre-existing `.gitignore` edit remain in the worktree and should be reviewed separately before staging.

Prompt 2 implementation and verification details are in section 8.

## 2. Existing project structure

```text
devnovate/
  backend/
    munshi/
      api/          FastAPI resource routers and schemas
      agents/       Collector, Risk, policy, drafting, prompts
      band/         Band bridge, command parser, agent manager
      checks/       GSTIN validation and readiness rules R1-R9
      db/           SQLModel entities, SQLite sessions, demo seed
      llm/          Groq wrapper, JSON helpers, disk cache
      memory/       Hindsight wrapper, bank setup, queries, outbox
      services/     Simulated clock, daily-loop placeholder, WhatsApp URL
    sim/            Deterministic world, profiles, personas, scenarios
    eval/           Evaluation runner, arms A/B/C, metrics and reports
    scripts/        Demo-memory and integration-spike scripts
    tests/          Pytest suites for API, DB, rules, agents and integrations
    pyproject.toml  Python dependency manifest
  frontend/
    src/api/        Central HTTP client
    src/components/ Shared UI components
    src/hooks/      Query/mutation hooks
    src/pages/      Seven documented application screens
    src/test/       Frontend test setup
    package.json    Frontend dependencies and scripts
  docs/             Integration, module, demo, progress and audit documents
  API_DOCUMENTATION.md
  ARCHITECTURE.md
  DATABASE_DESIGN.md
  DEVELOPMENT_RULES.md
  IMPLEMENTATION_ROADMAP.md
  docker-compose.yml
  Makefile
  README.md
```

Generated/cache directories and local data files are also present (including `.cache`, `.pytest_cache`, `frontend/dist`, `backend/uploads`, and the two SQLite files). They were not removed or modified.

## 3. Technology stack actually detected

| Area | Detected |
|---|---|
| Backend runtime | Python 3.11.9 in `backend/.venv` |
| Backend libraries | FastAPI 0.141.1, Uvicorn 0.52.4, SQLModel 0.0.48, SQLAlchemy 2.1.8, Pydantic 2.13.5, pydantic-settings 2.16.2 |
| Database | SQLite; default URL `sqlite:///./munshi.db` |
| LLM SDK | Groq 1.7.0 |
| Hindsight SDK in backend venv | `hindsight-client==1.2.0`, installed in the active Python 3.11.9 backend `.venv` and exercised through Munshi's wrapper |
| Band SDK in backend venv | Not installed |
| Frontend | React 18.3.1, Vite 5.4.21, TypeScript 5.9.3, Tailwind 3.4.19, TanStack Query 5.107.1, Recharts 2.15.4 |
| Frontend runtime/tooling | Node 25.9.0, npm 11.12.1, Vitest 2.1.9 |
| Dependency files | `backend/pyproject.toml` is declared source of truth; `requirements.txt` says reference only. `frontend/package-lock.json` exists. No `uv.lock` exists. |
| Supabase | No Supabase client, URL, schema, migration, or deployment configuration found. |
| Deployment tools in this environment | Docker, Docker Compose, `uv`, and Ruff are unavailable. |

The README, Makefile, and Dockerfile assume `uv`, although the active backend environment was a Python virtual environment and `uv` was not installed. The Dockerfile copies `uv.lock`, but that file is absent, so a Docker build is expected to fail at that step. Docker could not be run to confirm the build failure.

## 4. Backend implementation status

| Area | Status | Evidence and limitations |
|---|---|---|
| Twelve SQLModel entities | **COMPLETE AND VERIFIED** | Tables, relationships, indexes, enum checks, integer-paise amounts, and core constraints are tested. |
| SQLite initialization and sessions | **COMPLETE AND VERIFIED** | Startup calls `SQLModel.metadata.create_all`; session dependencies and rollback behavior have tests. `create_all` is not a migration mechanism. |
| Demo seed | **COMPLETE AND VERIFIED** | Seed values are fictional literals in `backend/munshi/db/seed.py` and are stored in SQLite. |
| FastAPI app, health, CORS, error handling | **COMPLETE AND VERIFIED** | TestClient coverage passes; a temporary Uvicorn process started and `GET /health` returned HTTP 200. |
| Documented API route registration | **COMPLETE AND VERIFIED** | A test compares the registered `/api` methods and paths to the API contract. |
| Ledger and workflow API behavior | **PARTIALLY IMPLEMENTED** | Payment-adjusted balances, invoice GSTIN/PO fields, evidence-backed action outputs, event-triggered Risk assessments, and truthful approval/handoff states are implemented. Band transport, the simulator world/injection engine, and evaluation persistence remain incomplete. |
| Authentication/authorization | **NOT IMPLEMENTED** | Consistent with the single-demo prototype scope, but not safe for multi-user deployment. |
| Database migrations | **NOT IMPLEMENTED** | No Alembic or other migration history; existing schemas are not upgraded by `create_all`. |
| Daily loop | **COMPLETE AND VERIFIED for bounded workflow** | FastAPI lifespan starts/stops a single local worker. It performs daily Collector and Risk passes; the loop is bounded to one customer batch per pass and logs failures without stopping the application. |
| Hindsight outbox lifecycle | **COMPLETE AND VERIFIED for the Prompt 2 scope** | FastAPI lifespan starts/stops the processor; tests cover persistence, retries, duplicate prevention, and confirmed-success status. |

## 5. Frontend implementation status

All seven documented screens exist and render in tests. API requests are centralized in `frontend/src/api/client.ts`; TanStack Query is used for server state and the page queries poll at the documented interval. The tests mock `fetch`, so they do not prove a live browser-to-backend workflow.

| Screen | Status | Actual behavior and limitation |
|---|---|---|
| Dashboard | **COMPLETE AND VERIFIED for ledger balances** | Reads SQLite-backed totals and subtracts recorded payments from outstanding/overdue balances. |
| Customer | **PARTIALLY IMPLEMENTED** | Reads ledger history and customer-scoped Hindsight playbook/beliefs when available; exposes memory unavailable separately and reports outstanding balance. |
| New Invoice / Readiness | **COMPLETE AND VERIFIED for available R3/R6 inputs** | Creates invoices, uploads documents, requests readiness checks, and accepts invoice GSTIN/PO amount. IRN still has no dedicated data field. |
| Approvals Inbox | **COMPLETE AND VERIFIED for manual approval/handoff states** | Shows persisted rationale/evidence; approval does not send. Handoff is time-gated and owner-reported sending is distinct from provider verification. |
| Risk Alerts | **COMPLETE AND VERIFIED for stored assessments** | Shows persisted signals/evidence and whether Hindsight was available; payment and inbound-message writes trigger Risk assessment. |
| Simulation Console | **PARTIALLY IMPLEMENTED** | Clock can advance by days/hours to reach scheduled contact times; reset is available in demo mode. Event injection still acknowledges without applying changes to the deterministic simulation world. |
| Evaluation | **PARTIALLY IMPLEMENTED** | Reads and charts result data; no evaluation rows/results were present, so the real UI generally has an empty state. |

UI controls are connected to the API client, but a connected button is not proof of completed business behavior. No WebSockets are used. No frontend `.env*` file was present, and no secret is configured as a Vite variable.

## 6. Database and Supabase readiness

### Current database

The backend is using a **real local SQLite database**, not Supabase or an in-memory mock:

| File | Tables | Rows observed |
|---|---:|---|
| `backend/munshi.db` | 12 | 1 business, 3 customers, 3 invoices, 1 invoice document, 1 readiness check, 1 action, 1 inbound message, 1 payment, 1 promise, 1 risk alert, 0 memory events, 0 simulation runs |
| Project-root `munshi.db` | 0 application tables | Empty database file |

The second empty file demonstrates a path risk: `sqlite:///./munshi.db` is relative to the process working directory. Running from a different directory can create or use a different database.

| Question | Finding |
|---|---|
| Are tables actually created? | Yes; all twelve documented tables are present in `backend/munshi.db`. |
| Are SQLModel models connected to a working database? | Yes; backend API handlers use SQLModel sessions and the real file persists data locally. |
| Are demo records persistent? | Yes, after seed execution. The fictional source values are literals in the seed code, then stored in SQLite. |
| Is the application storing/retrieving data in the frontend? | The frontend calls backend APIs; persistence and SQL operations occur in the backend. |
| Is Supabase configured? | No. SQLite remains the current approved choice. |
| Are migrations/schema scripts present? | No versioned migration system was found. Tables are created at startup. |
| Are relationships and constraints implemented? | Yes for documented core relations and tested checks/uniqueness; not every business invariant is a SQL constraint. |

No Supabase setup, database migration, or database write was performed by this audit.

## 7. Groq API status

**Overall status: PARTIALLY IMPLEMENTED.** A real minimal request succeeded; the application wrapper and all supported model behaviors are not fully verified.

- `GROQ_API_KEY` is non-empty and loads through the backend settings. Its value is not included here.
- `groq` 1.7.0 is installed in the active backend Python 3.11 environment.
- The loaded API host is `api.groq.com`; the configured agent model is `openai/gpt-oss-120b`.
- A minimal live chat-completion request succeeded using `openai/gpt-oss-120b`.
- The live model-list request did **not** list the configured customer model `qwen/qwen3-32b`. The model setting was not changed.
- Groq SDK calls are confined to `backend/munshi/llm/groq_client.py`. The wrapper contains request construction, JSON/structured-output handling, retries, rate-limit code, and fallback paths, but those behaviors were not verified against the live service.
- The earlier Groq mock-patching failures were fixed in Prompt 3 by exposing an injectable client factory and constructing test clients before singleton initialization. The live minimal SDK request does not verify the wrapper’s full provider behavior.

## 8. Hindsight integration status

**Overall status: COMPLETE AND VERIFIED for the Prompt 2 adapter/outbox scope.** The installed SDK and Munshi's own wrapper were exercised against Hindsight Cloud with synthetic data; mocked tests separately cover failure and retry behavior.

- `HINDSIGHT_API_KEY` and `HINDSIGHT_BASE_URL` are configured and loaded by backend settings; values are withheld. Live synthetic Cloud tests exercised Munshi's wrapper.
- `hindsight-client==1.2.0` is installed in `backend\.venv` running Python 3.11.9. The declared dependency already existed in `backend/pyproject.toml`; its version range was not changed. The official SDK docs and installed package confirm `Hindsight`, async `a*` methods, `RetainResponse.success`, recall `.results`, and reflect `.structured_output`.
- The adapter uses configured URL/key/timeout, SDK async methods, stable document IDs, customer tags, metadata serialization, and structured reflect output. Network failures raise sanitized `HindsightUnavailable`; readiness marks memory pending, while Collector/Risk fall back to ledger evidence.
- Two real Cloud tests passed with synthetic data: the application wrapper created/accessed banks, retained/recalled a fact, reflected, verified available timestamp/metadata, isolated tagged customer results and a second business bank, and processed a local SQLite outbox row through the wrapper. Live tests require `MUNSHI_RUN_HINDSIGHT_INTEGRATION=1`.
- SDK recall responses do not always populate `occurred_start`; Cloud list results exposed `mentioned_at`/`var_date`. The adapter normalizes available timestamp fields; metadata was returned in the live recall result.
- FastAPI lifespan starts and stops the outbox worker. A process-local lock prevents overlapping passes; stable event IDs are sent as Hindsight document IDs, retries honor due times and stop at the configured bound, and success is recorded only after confirmed retention. Mocked tests cover retry/failure handling, duplicate processing, redaction and lifecycle.
- Outbox metadata is restricted to event/customer/invoice identifiers; phone numbers with common spaces/parentheses/separators, labeled account numbers, IFSC codes, and labeled UPI/VPA identifiers are redacted; known unsent-draft kinds are excluded. This does not replace careful upstream construction of durable learned facts.

Prompt 2's historical focused run had 58 passed, one pre-existing parser-title failure and two expected live-test skips. Its full backend run collected 314 tests: 306 passed, 6 failed, 2 skipped. Prompt 3 resolved the five Groq mock-patching failures; the current full-suite results are recorded in “Current status after Prompt 3” and section 13.

## 9. Band AI status

**Overall status: BLOCKED BY CREDENTIALS OR EXTERNAL DEPENDENCY.**

- The current official quickstart describes `band-sdk` 8.1.0 and requires a Band account plus a registered remote agent's ID and API key. The quickstart's Python install example uses `band-sdk[langgraph]==8.1.0`; agent keys are shown only once and must be kept private. Band Desktop supports local coding-agent integrations but does not itself run Munshi's custom Collector/Risk backend logic.
- `BAND_ROOM_ID`, Collector/Risk agent IDs, and their per-agent API keys are missing from the loaded configuration.
- `band-sdk` is not installed. A prior install attempt for the official package was blocked because the configured package index could not resolve its required `band-sdk-core==6.1.1` dependency. No unofficial substitute was used.
- `band/commands.py` has regex parsing and unit tests. `band/bridge.py` only logs “Would post…” and sends no room message. `run_agents.py` is not started by FastAPI, and there is no registered route to route a Band command into the backend approval endpoint.
- The current source's SDK setup and adapter compatibility have not been established against the current official quickstart.
- No Band connection, post, inbound command, or web/Band approval parity has been verified.

Official reference checked during this audit: [Band Python quickstart](https://docs.band.ai/quickstart). The current Hindsight reference is [Python client docs](https://hindsight.vectorize.io/sdks/python).

## 10. Feature-by-feature status

| # | Feature | Status | Verified behavior and remaining gap |
|---:|---|---|---|
| 1 | Dashboard | **COMPLETE AND VERIFIED for ledger balances** | Reads DB-backed totals/counts and subtracts recorded payments from outstanding and overdue balances. |
| 2 | Customer management | **PARTIALLY IMPLEMENTED** | DB-backed list, detail, and patch exist; creation is indirect through CSV import. |
| 3 | Customer payment history | **COMPLETE AND VERIFIED** | Payments are stored in SQLite and included in the customer timeline; this is ledger history, not Hindsight history. |
| 4 | Invoice creation and management | **PARTIALLY IMPLEMENTED** | Create, readiness, upload, confirm, send, and import routes exist; invoice list/detail UI/API is absent. Create now accepts invoice GSTIN and PO amount. |
| 5 | Invoice readiness checks | **COMPLETE AND VERIFIED for available contract inputs** | R1-R9 code/tests exist; normal API supplies invoice GSTIN and PO amount to the checks. |
| 6 | GSTIN validation | **PARTIALLY IMPLEMENTED** | Format/check-character/state helpers exist. They do not check the government registry or prove active legal ownership. Invoice GSTIN cannot be supplied in the normal flow; demo fixture GSTINs fail the implemented checksum. |
| 7 | Purchase order validation | **PARTIALLY IMPLEMENTED** | Required PO number checks work. Amount tolerance is skipped when no PO amount is supplied; normal API has no PO amount field. |
| 8 | Required document validation | **COMPLETE AND VERIFIED** | Upload metadata is stored in SQLite and readiness checks configured required document types; file bytes are on local disk. |
| 9 | Learned customer requirements | **PARTIALLY IMPLEMENTED** | Requirement codes and precedence are implemented; the repaired app wrapper now retrieves memory, but `EINVOICE_IRN` has no corresponding document/IRN field. |
| 10 | Collector agent | **COMPLETE AND VERIFIED for local draft workflow** | A lifecycle-managed daily pass creates deduplicated, evidence-backed action drafts; it does not send messages. |
| 11 | Risk agent | **COMPLETE AND VERIFIED for local assessment workflow** | Daily assessments and payment/inbound-message-triggered reassessments persist levels, signals, evidence, and memory availability. |
| 12 | Reminder drafting | **COMPLETE AND VERIFIED for scheduled candidates** | Collector selects due/overdue ledger invoices, applies its timing/promise rules, and persists drafts with a daily dedupe key. |
| 13 | Owner approval workflow | **COMPLETE AND VERIFIED for handoff state** | Approve/edit/reject mutations persist; approval stays `APPROVED`/`EDITED`. Guarded WhatsApp handoff does not mark sent; owner confirmation records `OWNER_REPORTED`. |
| 14 | Inbound customer messages | **COMPLETE AND VERIFIED for API ingestion** | Endpoint validates customer/invoice relationship, commits message and memory event, then reports explicit Risk assessment completion/failure. No channel webhook integration is claimed. |
| 15 | Payment recording | **COMPLETE AND VERIFIED** | API enforces outstanding amount, commits payment and invoice status, triggers Risk, and reports assessment failure without undoing the payment. |
| 16 | Hindsight retention and retrieval | **COMPLETE AND VERIFIED for the Prompt 2 adapter/outbox scope** | The official SDK is installed in the active backend venv; live synthetic tests exercised the wrapper, retention, recall, reflection, customer/business isolation, and outbox processing. |
| 17 | Band AI workflow | **PLACEHOLDER / MOCK** | Command parsing exists; room bridge logs rather than posts and approval routing is absent. |
| 18 | Simulation engine | **COMPLETE AND VERIFIED** | Deterministic world, profiles, scenarios, time advancement, injection and world-rule tests exist. The HTTP controls are not connected to it. |
| 19 | Evaluation Arms A/B/C | **PARTIALLY IMPLEMENTED** | Arms, metrics, and runner code/tests exist; no result rows were in SQLite and Arm C depends on Hindsight. |
| 20 | WhatsApp prefilled message | **PARTIALLY IMPLEMENTED** | Approved action can open a prefilled `wa.me` link during the scheduled 09:00–19:00 IST window; no provider send/delivery API is implemented. |
| 21 | Risk alerts | **COMPLETE AND VERIFIED for local triggers** | Daily and event-triggered assessments persist alerts with evidence and memory availability; Band posting remains blocked/unavailable. |
| 22 | Explainability and evidence | **PARTIALLY IMPLEMENTED** | Draft rationale/evidence, risk evidence, and customer-scoped Hindsight context are exposed. `/api/explain` remains limited to available ledger/memory evidence and reports memory availability. |

## 11. API endpoint verification

“Tested” below means basic route/validation behavior is covered by the backend ASGI tests; it does not mean every external integration or full business workflow works. “Frontend uses” is based on source call sites, not a live browser session.

| Method and route | Exists / registered | Database and response behavior | Tested | Frontend uses |
|---|---|---|---|---|
| `GET /health` | Yes | App-clock liveness; no DB query | Yes; live HTTP 200 | No |
| `POST /api/import/tally-csv` | Yes | Creates SQLite customer/invoice rows from CSV | Yes | No |
| `GET /api/dashboard` | Yes | SQLite aggregate queries use payment-adjusted outstanding balances | Yes | Yes |
| `GET /api/customers` | Yes | SQLite customer/invoice aggregates | Yes | Yes |
| `GET /api/customers/{id}` | Yes | Ledger timeline/balance and customer-scoped Hindsight context with explicit memory status | Yes | Yes |
| `PATCH /api/customers/{id}` | Yes | Updates SQLite and creates local memory-event row | Yes | No |
| `POST /api/invoices` | Yes | Writes invoice/readiness rows and accepts invoice GSTIN/PO amount inputs | Yes | Yes |
| `POST /api/invoices/{id}/documents` | Yes | Saves file to local disk and metadata to SQLite | Yes | Yes |
| `POST /api/invoices/{id}/check` | Yes | Updates readiness/check rows; asks the memory abstraction | Yes | Yes |
| `POST /api/invoices/{id}/confirm` | Yes | Updates customer requirement/readiness in SQLite | Yes | No |
| `POST /api/invoices/{id}/send` | Yes | Marks invoice SENT and creates local memory-event row; no real send | Yes | No |
| `GET /api/actions?status=...` | Yes | Reads SQLite evidence/rationale and reports handoff/owner-confirmation state | Yes | Yes |
| `POST /api/actions/{id}/approve` | Yes | Persists APPROVED/EDITED; never marks sent or sends a message | Yes | Yes |
| `GET /api/actions/{id}/handoff` | Yes | Validates approval, phone, planned time and contact hours, then redirects to a prefilled WhatsApp URL | Yes | Yes |
| `POST /api/actions/{id}/confirm-delivery` | Yes | Stores owner-reported sending after handoff; provider delivery remains unverified | Yes | Yes |
| `POST /api/actions/{id}/reject` | Yes | Updates SQLite; optional reason becomes local memory-event row | Yes | Yes |
| `GET /api/actions/{id}/explain` | Yes | Returns persisted action rationale and evidence references | Yes | Yes |
| `POST /api/messages/inbound` | Yes | Commits message/event then performs a Risk assessment; response reports completed/failed status | Yes | No |
| `POST /api/payments` | Yes | Commits payment/status then assesses Risk; assessment failure does not roll back payment | Yes | No |
| `GET /api/risk/alerts` | Yes | Reads SQLite alert rows | Yes | Yes |
| `POST /api/risk/alerts/{id}/ack` | Yes | Updates SQLite alert status | Yes | Yes |
| `POST /api/explain` | Yes | Uses customer-scoped ledger/memory evidence and reports memory availability | Yes | No |
| `POST /api/sim/reset` | Yes | Drops/recreates DB and seeds demo; scenario name is not used | Yes | Yes |
| `POST /api/sim/tick?days=N&hours=N` | Yes | Advances simulated time; daily workflow is separate and injection still does not apply to the simulation world | Yes | Yes |
| `POST /api/sim/inject` | Yes | Returns `{ok: true}` without applying the event | Yes | Yes |
| `GET /api/eval/results` | Yes | Reads `sim_run`; empty/default results when no runs are saved | Yes | Yes |
| `GET /api/documents/{id}` | Handler only; not registered | Would read SQLite metadata and local file | No | No |

The frontend does not call CSV import, customer patch, invoice confirm/send, inbound message, payment, plain-language explain, or document download. The API contract says a duplicate invoice is returned as a readiness finding, while the implementation returns HTTP 409.

## 12. Hardcoded, mocked, and placeholder behavior

| Category | Examples |
|---|---|
| Hardcoded demo data | Seed literals, simulation profiles, and scenarios are fictional values in source and are persisted only when the corresponding seed/reset path runs. |
| Hardcoded API results | Evaluation results may be empty when no runs are persisted; simulation injection currently acknowledges without applying world state. |
| Mocked external behavior | Band bridge logs “Would post”; frontend tests mock `fetch`; agent tests mock external collaborators. |
| Placeholder workflow | Simulation injection does not apply to the deterministic world; Band does not deliver messages or route commands. |
| Graceful fallback, not integration | Groq fallback text and Hindsight empty-result fallbacks can look like valid business results unless surfaced distinctly. |
| Local-only persistence | SQLite is local; invoice file uploads are stored on local disk. Neither uses Supabase or cloud object storage. |

## 13. Tests and execution

### Backend

Command run from `backend`: `.\.venv\Scripts\python.exe -m pytest -q`

- Collected: **319**
- Passed: **316**
- Failed: **1**
- Skipped: **2**
- Warnings: **7**

The single remaining failure is `tests/test_queries.py::TestParsePlaybook::test_parse_playbook_json`: the existing assertion expects “Payment Collection” while the parser returns “Payment Collection Playbook.” The five Groq mock-patching failures from the earlier baseline are resolved.

Two opt-in Hindsight integration tests exercise the application wrapper and outbox against Cloud with synthetic data; both passed in the explicit live run and skip by default.

### Frontend and runtime

| Check | Result |
|---|---|
| `npm test -- --reporter=dot` | Passed: 2 files, 13 tests |
| `npm run build` | Passed: TypeScript and Vite production build |
| `npm run lint` | Failed: ESLint 8.57.1 reports no configuration file |
| Backend startup | Passed: temporary Uvicorn server initialized SQLite and served `GET /health` with HTTP 200 |
| Frontend against live backend | Not tested; frontend tests use mocked `fetch` |
| Ruff | Not run; Ruff is not installed |
| Docker/container build | Not run; Docker is unavailable |

## 14. Environment variables and external dependencies

No credential values are reproduced here.

| Variable/service | Current state |
|---|---|
| `GROQ_API_KEY` | Present and loaded by backend settings |
| `GROQ_BASE_URL` | Loaded host is `api.groq.com` |
| `GROQ_AGENT_MODEL` | `openai/gpt-oss-120b`; live minimal request succeeded |
| `GROQ_CUSTOMER_MODEL` | `qwen/qwen3-32b`; not present in current model-list response |
| `HINDSIGHT_API_KEY` | Present and loaded; value withheld |
| `HINDSIGHT_BASE_URL` | Present and loaded; configured host is `api.hindsight.vectorize.io` |
| `HINDSIGHT_LOCAL_URL` | Not configured |
| `BAND_ROOM_ID` | Missing |
| `BAND_COLLECTOR_AGENT_ID`, `BAND_COLLECTOR_API_KEY` | Missing |
| `BAND_RISK_AGENT_ID`, `BAND_RISK_API_KEY` | Missing |
| `BAND_API_KEY`, `BAND_AGENT_ID` | Legacy settings; missing and not a working bridge |
| `DATABASE_URL` | SQLite; no Supabase variables found |
| Frontend environment files | None found; backend secrets are not in Vite variables |

`backend/.env` exists and is ignored by Git. Both environment templates use empty secret placeholders. Earlier test output from a failed assertion exposed the configured Groq key locally. Rotate that key if the output is accessible to anyone else; no key value is included in this report.

## 15. Critical bugs and architectural problems

1. **No provider delivery integration:** approval and manual WhatsApp handoff are separate and accurate, but `SENT` is only an owner report; no WhatsApp provider API verifies delivery.
2. **Band is not connected:** no actual room posting, inbound command route, or web/Band approval parity was verified.
3. **Simulation API is disconnected from the actual engine:** tick and injection return success without doing the advertised work.
3. **Simulation injection remains a placeholder:** clock control works, including hour advancement; injecting an event still does not update the simulation world.
4. **Evaluation results may be empty:** no `sim_run` persistence workflow was connected in this stage.
5. **IRN is not modeled:** learned `EINVOICE_IRN` needs a dedicated document/IRN contract.
6. **Database selection depends on working directory:** both an initialized backend DB and an empty project-root DB exist.
7. **No general schema migration framework:** only safe additive SQLite columns for the new Prompt 3 fields are added at startup.
8. **Demo GSTINs fail the current checksum implementation:** canned invoices may appear blocked for the wrong demonstration reason. The checksum does not consult the government registry.
9. **Deployment files disagree:** Dockerfile requires the absent `uv.lock`; README/Makefile assume `uv`, which was unavailable here. Hindsight Compose image uses `latest`, reducing reproducibility.
10. **Credential exposure:** a prior test assertion printed the Groq key in local output. Rotate if that output might be shared.

## 16. Remaining work

- Keep SQLite for now; do not migrate to Supabase.
- Preserve the verified Hindsight adapter/outbox behavior; address only newly discovered defects. The outbox lock is process-local, not distributed.
- Resolve the official Band SDK dependency installation, register remote agents, and implement/test real room and command transport.
- Decide on a supported Groq customer model before changing the configured identifier.
- Connect simulation event injection to the deterministic world and persist evaluation outputs (later stage).
- Add a dedicated IRN/document field if required by the product contract.
- Correct synthetic GSTIN fixtures and test known-valid format/checksum examples.
- Add migrations and resolve the relative SQLite path before schema growth or deployment.
- Fix the Dockerfile/lockfile mismatch; add ESLint configuration if lint is a required check.
- Run backend/frontend end-to-end tests against a live backend and external integrations.

## 17. Which planned prompts can be skipped or should be modified

| Earlier development prompt | Recommendation | Reason |
|---|---|---|
| Database/backend foundation | **Skip a rebuild; retain only a verification pass** | The twelve SQLite entities, app foundation, route registration, error handling, and seed are present and tested. Keep SQLite; do not redo the foundation. |
| Invoice readiness | **Modify to close contract gaps only** | R1-R9 and tests exist. Focus on missing invoice GSTIN/PO amount inputs, demo GSTIN fixtures, and blocked learned-memory reads rather than rewriting the rules. |
| Collector and Risk | **Complete for Prompt 3 scope** | Runtime triggers, evidence persistence, ledger balances, and owner-gated handoff are implemented; do not duplicate agent logic. |
| Frontend | **Skip rebuilding the seven screens; modify integration gaps** | Screens, central API client, tests, and production build exist. Prioritize live-backend validation and missing UI paths instead of recreating pages. |
| Prompt 1 credential configuration/audit | **Do not repeat as a setup task** | Groq/Hindsight settings are present; Groq had a live successful request and Hindsight was subsequently verified through Munshi's wrapper. Band remains blocked. Rotate the Groq key if earlier local test output could be exposed. |
| Prompt 2 Hindsight repair | **Complete for the requested stage** | Installed SDK 1.2.0, repaired and live-tested the app wrapper, customer/business isolation, and outbox path. |
| Prompt 3 | **Complete for requested workflow scope** | Collector/Risk runtime workflows, Groq testability/error reporting, truthful approval/handoff states, ledger/API corrections, focused frontend alignment, and docs are implemented and tested. |
| Prompt 4 | **Not started** | Simulation world integration, evaluation persistence, and full product integration remain separate work. |

### Recommended stage boundaries

1. **Prompt 2 — Hindsight integration repair:** complete. Do not repeat this stage unless new Hindsight integration defects are found.
2. **Prompt 3 — operational runtime workflow:** complete. Band remains a separate blocked dependency and was not integrated.
3. **Prompt 4 — End-to-end simulation/evaluation and product integration:** connect sim APIs to the engine, persist evaluation outputs, reconcile evidence and financial summaries, and verify frontend-to-live-backend workflows.

## 18. Integration risks

- Hindsight is integrated through the verified wrapper; live checks used only synthetic data. Continue to treat Cloud outages as unavailable memory, not as “no learned behavior.”
- Groq's agent model worked in a previous live request, but the configured customer model was not listed in the prior model-list response; structured output/retries have not been verified live.
- Band Desktop, Band account sign-in, and a registered remote agent API key are distinct setup requirements.
- Frontend tests with mocked `fetch` do not establish live API compatibility.
- `SENT` means an owner reported sending; provider delivery is not verified.
- Simulation event injection acknowledges the request but does not apply changes to the deterministic world.
- Relative SQLite paths, absent migrations, and missing `uv.lock` can break local/container parity.
- The enclosing Git repository treats the entire project folder as untracked, limiting reliable change-history attribution.
