# Munshi Implementation Status Audit

**Audit date:** 2026-11-07  
**Scope:** Current implementation, external configuration, focused live checks, backend and frontend tests, and deployment files. No runtime source, database schema, database records, or credentials were changed by this audit.

The original PDF project document is present, but local PDF text extraction tools were unavailable and the file viewer exposed compressed PDF data rather than readable text. Its Markdown companion `PROJECT_ANALYSIS.md` and the available Markdown specifications were inspected; the PDF's full text was not independently verified.

## Status labels

- **COMPLETE AND VERIFIED** — behavior was exercised successfully by tests or a live check.
- **IMPLEMENTED BUT NOT VERIFIED** — implementation exists, but a successful run has not been established.
- **PARTIALLY IMPLEMENTED** — some required behavior works, but important pieces are missing or disconnected.
- **PLACEHOLDER / MOCK** — implementation returns canned behavior or simulates an external operation.
- **NOT IMPLEMENTED** — no implementation was found.
- **BLOCKED BY CREDENTIALS OR EXTERNAL DEPENDENCY** — work depends on missing credentials, an SDK, or an external service.

## 1. Executive summary

Munshi is a working local prototype, not an empty skeleton. It has a SQLModel/SQLite ledger with all twelve documented entities, seeded demo records, FastAPI routes, tested readiness rules, standalone Collector and Risk logic, a deterministic simulation engine, evaluation code, and seven React screens.

It is **not yet an end-to-end collections application**. The most important gaps are:

- The database is local SQLite, not Supabase; this is intentional for the current stage. The seeded demo data is hard-coded in Python and persisted in SQLite.
- Most documented REST routes exist and use SQLite, but several return fixed or incomplete results. The simulation HTTP routes do not execute the existing simulation engine.
- Collector and Risk implementations have unit tests, but no ordinary API or scheduled workflow invokes them. The daily loop is unfinished.
- Hindsight Cloud was previously reached directly with synthetic retain/recall using SDK 1.2.0 in a separate verification environment. Munshi's wrapper still expects the missing `hindsight_client.Client` class. The SDK remains absent from the actual backend virtual environment: the earlier install attempt and two bounded Prompt 2 attempts stalled without output. Direct HTTPS checks to PyPI and its package-file host returned HTTP 200, and no pip index override was found; the exact cause of pip's stall remains undetermined. No dependency manifest was changed.
- A real Groq request succeeded using `openai/gpt-oss-120b`. The configured `qwen/qwen3-32b` customer model was not present in the model list returned during this audit.
- Band is not connected: credentials are absent, the SDK is not installed, and the bridge only logs what it would post.
- The backend full suite has **317 passed, 6 failed, and 5 skipped**. Frontend tests and production build pass; frontend lint fails because there is no ESLint configuration.
- The project is untracked as a directory in its enclosing Git repository (`?? devnovate/`), so a normal Git diff cannot establish the history of individual project files.

The current Prompt 1 audit caused no runtime-code changes. The deliverables from this audit are documentation only.

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
| Hindsight SDK in backend venv | Not installed; three attempts stalled without output; PyPI index and package-file hosts respond over HTTPS |
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
| CRUD and financial API behavior | **PARTIALLY IMPLEMENTED** | Many handlers write/read SQLite; some workflows are incomplete or return generic data, as detailed in the API table below. |
| Authentication/authorization | **NOT IMPLEMENTED** | Consistent with the single-demo prototype scope, but not safe for multi-user deployment. |
| Database migrations | **NOT IMPLEMENTED** | No Alembic or other migration history; existing schemas are not upgraded by `create_all`. |
| Daily loop | **PLACEHOLDER / MOCK** | `daily_loop.py` contains a TODO for the day’s work and is not started by FastAPI. |
| Hindsight outbox lifecycle | **PARTIALLY IMPLEMENTED** | A processor exists but is not started by FastAPI. Some outbox field names and constructor arguments do not match the current `MemoryEvent` model. |

## 5. Frontend implementation status

All seven documented screens exist and render in tests. API requests are centralized in `frontend/src/api/client.ts`; TanStack Query is used for server state and the page queries poll at the documented interval. The tests mock `fetch`, so they do not prove a live browser-to-backend workflow.

| Screen | Status | Actual behavior and limitation |
|---|---|---|
| Dashboard | **PARTIALLY IMPLEMENTED** | Reads the SQLite-backed summary API. Receivable and overdue values sum invoice face values and do not subtract payments. |
| Customer | **PARTIALLY IMPLEMENTED** | Reads customer data and ledger timeline. The API always supplies an empty playbook, `updating: true`, and no beliefs. |
| New Invoice / Readiness | **PARTIALLY IMPLEMENTED** | Creates invoices, uploads documents, and requests readiness checks. The form cannot supply invoice GSTIN or PO amount. |
| Approvals Inbox | **PARTIALLY IMPLEMENTED** | Lists and edits/approves/rejects drafts. The API returns generic “why” text and no supporting evidence; approval is recorded as sent without delivery. |
| Risk Alerts | **PARTIALLY IMPLEMENTED** | Reads persisted alerts and sends acknowledgement/dismissal decisions; the screen does not initiate a risk assessment. |
| Simulation Console | **PARTIALLY IMPLEMENTED** | Calls reset/tick/inject routes, but tick only advances the clock and inject does not apply the event to the simulation. |
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
- Five backend tests fail because they patch `munshi.llm.groq_client.Groq`, but the implementation imports `Groq` inside `_initialize` and does not expose that module-level name. The live minimal SDK request does not verify the wrapper’s complete behavior.

## 8. Hindsight integration status

**Overall status: BLOCKED BY CREDENTIALS OR EXTERNAL DEPENDENCY for Munshi's application wrapper; direct Cloud operations were previously verified outside the backend venv.**

- `HINDSIGHT_API_KEY` and `HINDSIGHT_BASE_URL` are non-empty and load through backend settings. Values are withheld; only the configured host is reported.
- In the earlier direct Cloud check, SDK 1.2.0 reported API version 1.1.0. A synthetic bank was created, a synthetic fact retained, and recall returned a result. No customer data or drafts were used. The test bank was left in place.
- The current backend `.venv` still does not have `hindsight-client`. An earlier install attempt produced no output for more than six minutes. During Prompt 2, two further bounded attempts (the configured default index and explicit `https://pypi.org/simple`) each produced no output within 60 seconds and were stopped. Separate HTTPS checks to `pypi.org` and `files.pythonhosted.org` returned HTTP 200; no pip index URL override was found. The lower-level pip failure was not captured, so its cause is unknown. No project dependency manifest was changed.
- Current official Python SDK documentation exports `Hindsight`. The application wrapper in `backend/munshi/memory/client.py` constructs `hindsight_client.Client`, so Munshi's client is not compatible with the verified SDK API. No successful operation through Munshi's wrapper has been established.
- Five Hindsight integration tests are skipped unconditionally with “Requires Hindsight to be running”; they do not exercise the live configured Cloud service. The focused Prompt 2 run collected 62 tests: 56 passed, one failed, and these five integration tests skipped. The failure, `tests/test_queries.py::TestParsePlaybook.test_parse_playbook_json`, expected `Payment Collection` but got `Payment Collection Playbook`; it is unrelated to Hindsight and was present in the baseline audit.
- The outbox processor is not launched by FastAPI. Its current code references fields/arguments that differ from `MemoryEvent`, does not reliably honor retry schedules, and has no verified idempotent retain path.
- Customer-specific memory retrieval, metadata/timestamp handling through the app wrapper, agent use of memories, and memory updates are **NOT VERIFIED**.

The Prompt 2 implementation was stopped before runtime changes because the required SDK could not be installed in the backend environment. The existing 56 passing focused tests exercise mocked/local behavior only; they do not verify the wrapper against Hindsight Cloud.

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
| 1 | Dashboard | **PARTIALLY IMPLEMENTED** | Reads DB-backed totals/counts; balances do not subtract payments. |
| 2 | Customer management | **PARTIALLY IMPLEMENTED** | DB-backed list, detail, and patch exist; creation is indirect through CSV import. |
| 3 | Customer payment history | **COMPLETE AND VERIFIED** | Payments are stored in SQLite and included in the customer timeline; this is ledger history, not Hindsight history. |
| 4 | Invoice creation and management | **PARTIALLY IMPLEMENTED** | Create, readiness, upload, confirm, send, and import routes exist; invoice list/detail UI/API is absent. |
| 5 | Invoice readiness checks | **PARTIALLY IMPLEMENTED** | R1-R9 code/tests exist; normal API input cannot supply invoice GSTIN or PO amount. |
| 6 | GSTIN validation | **PARTIALLY IMPLEMENTED** | Format/check-character/state helpers exist. They do not check the government registry or prove active legal ownership. Invoice GSTIN cannot be supplied in the normal flow; demo fixture GSTINs fail the implemented checksum. |
| 7 | Purchase order validation | **PARTIALLY IMPLEMENTED** | Required PO number checks work. Amount tolerance is skipped when no PO amount is supplied; normal API has no PO amount field. |
| 8 | Required document validation | **COMPLETE AND VERIFIED** | Upload metadata is stored in SQLite and readiness checks configured required document types; file bytes are on local disk. |
| 9 | Learned customer requirements | **PARTIALLY IMPLEMENTED** | Requirement codes and precedence are implemented; live app retrieval is blocked by the wrapper. `EINVOICE_IRN` has no corresponding document/IRN field. |
| 10 | Collector agent | **PARTIALLY IMPLEMENTED** | Draft logic has unit coverage, but no normal API/scheduler path invokes it. |
| 11 | Risk agent | **PARTIALLY IMPLEMENTED** | Signal/classification logic and evidence references have tests; normal payment/message flows do not trigger reassessment. |
| 12 | Reminder drafting | **PARTIALLY IMPLEMENTED** | Collector can draft when directly invoked; no live daily trigger or UI/API draft-generation path exists. |
| 13 | Owner approval workflow | **PARTIALLY IMPLEMENTED** | Approve/edit/reject mutations are stored; approval immediately marks the action `SENT` before actual delivery. |
| 14 | Inbound customer messages | **PARTIALLY IMPLEMENTED** | Endpoint persists messages and a local memory-event row; no live channel ingestion or risk-worker queue exists. |
| 15 | Payment recording | **COMPLETE AND VERIFIED** | API enforces outstanding amount, stores payment, and updates invoice status; it does not trigger live memory/Risk workflows. |
| 16 | Hindsight retention and retrieval | **BLOCKED BY CREDENTIALS OR EXTERNAL DEPENDENCY** | Direct Cloud test previously succeeded; Munshi wrapper is incompatible and the SDK is absent from the active backend venv. |
| 17 | Band AI workflow | **PLACEHOLDER / MOCK** | Command parsing exists; room bridge logs rather than posts and approval routing is absent. |
| 18 | Simulation engine | **COMPLETE AND VERIFIED** | Deterministic world, profiles, scenarios, time advancement, injection and world-rule tests exist. The HTTP controls are not connected to it. |
| 19 | Evaluation Arms A/B/C | **PARTIALLY IMPLEMENTED** | Arms, metrics, and runner code/tests exist; no result rows were in SQLite and Arm C depends on Hindsight. |
| 20 | WhatsApp prefilled message | **PARTIALLY IMPLEMENTED** | A `wa.me` URL can be generated outside simulator mode; no WhatsApp API send occurs and simulator mode does not deliver to a simulated customer. |
| 21 | Risk alerts | **PARTIALLY IMPLEMENTED** | Read/ack routes and agent persistence exist; seeded alerts are visible but there is no normal trigger. |
| 22 | Explainability and evidence | **PLACEHOLDER / MOCK** | Readiness may include evidence IDs and Risk can create evidence; action rationale is generic, action explanation is empty, and `/api/explain` returns a fixed answer. |

## 11. API endpoint verification

“Tested” below means basic route/validation behavior is covered by the backend ASGI tests; it does not mean every external integration or full business workflow works. “Frontend uses” is based on source call sites, not a live browser session.

| Method and route | Exists / registered | Database and response behavior | Tested | Frontend uses |
|---|---|---|---|---|
| `GET /health` | Yes | App-clock liveness; no DB query | Yes; live HTTP 200 | No |
| `POST /api/import/tally-csv` | Yes | Creates SQLite customer/invoice rows from CSV | Yes | No |
| `GET /api/dashboard` | Yes | SQLite aggregate queries; amount calculations are incomplete | Yes | Yes |
| `GET /api/customers` | Yes | SQLite customer/invoice aggregates | Yes | Yes |
| `GET /api/customers/{id}` | Yes | SQLite record/timeline; playbook and beliefs are fixed empty values | Yes | Yes |
| `PATCH /api/customers/{id}` | Yes | Updates SQLite and creates local memory-event row | Yes | No |
| `POST /api/invoices` | Yes | Writes invoice/readiness rows; invokes readiness code | Yes | Yes |
| `POST /api/invoices/{id}/documents` | Yes | Saves file to local disk and metadata to SQLite | Yes | Yes |
| `POST /api/invoices/{id}/check` | Yes | Updates readiness/check rows; asks the memory abstraction | Yes | Yes |
| `POST /api/invoices/{id}/confirm` | Yes | Updates customer requirement/readiness in SQLite | Yes | No |
| `POST /api/invoices/{id}/send` | Yes | Marks invoice SENT and creates local memory-event row; no real send | Yes | No |
| `GET /api/actions?status=...` | Yes | Reads SQLite; `why` is generic fixed text | Yes | Yes |
| `POST /api/actions/{id}/approve` | Yes | Sets action SENT and writes event before any real delivery; may return a `wa.me` link | Yes | Yes |
| `POST /api/actions/{id}/reject` | Yes | Updates SQLite; optional reason becomes local memory-event row | Yes | Yes |
| `GET /api/actions/{id}/explain` | Yes | SQLite lookup, generic summary, empty evidence | Yes | Yes |
| `POST /api/messages/inbound` | Yes | Writes SQLite message and local memory event; returns success-shaped `risk_check_queued` without a worker | Yes | No |
| `POST /api/payments` | Yes | Writes payment and updates invoice status in SQLite | Yes | No |
| `GET /api/risk/alerts` | Yes | Reads SQLite alert rows | Yes | Yes |
| `POST /api/risk/alerts/{id}/ack` | Yes | Updates SQLite alert status | Yes | Yes |
| `POST /api/explain` | Yes | Checks customer exists, then returns fixed “No evidence is available yet.” | Yes | No |
| `POST /api/sim/reset` | Yes | Drops/recreates DB and seeds demo; scenario name is not used | Yes | Yes |
| `POST /api/sim/tick?days=N` | Yes | Advances clock only; reports zero drafts/alerts | Yes | Yes |
| `POST /api/sim/inject` | Yes | Returns `{ok: true}` without applying the event | Yes | Yes |
| `GET /api/eval/results` | Yes | Reads `sim_run`; empty/default results when no runs are saved | Yes | Yes |
| `GET /api/documents/{id}` | Handler only; not registered | Would read SQLite metadata and local file | No | No |

The frontend does not call CSV import, customer patch, invoice confirm/send, inbound message, payment, plain-language explain, or document download. The API contract says a duplicate invoice is returned as a readiness finding, while the implementation returns HTTP 409.

## 12. Hardcoded, mocked, and placeholder behavior

| Category | Examples |
|---|---|
| Hardcoded demo data | Seed literals, simulation profiles, and scenarios are fictional values in source and are persisted only when the corresponding seed/reset path runs. |
| Hardcoded API results | Customer playbook/beliefs are empty/updating; action `why` is generic; action explanation has no evidence; `/api/explain` always says no evidence is available. |
| Mocked external behavior | Band bridge logs “Would post”; frontend tests mock `fetch`; agent tests mock external collaborators. |
| Placeholder workflow | Daily loop has TODO logic; sim tick/inject do not execute the world; inbound “risk queued” does not correspond to a worker. |
| Graceful fallback, not integration | Groq fallback text and Hindsight empty-result fallbacks can look like valid business results unless surfaced distinctly. |
| Local-only persistence | SQLite is local; invoice file uploads are stored on local disk. Neither uses Supabase or cloud object storage. |

## 13. Tests and execution

### Backend

Command run from `backend`: `.\.venv\Scripts\python.exe -m pytest -q`

- Collected: **328**
- Passed: **317**
- Failed: **6**
- Skipped: **5**
- Warnings: **9**
- Duration: **36.58 seconds**

Reproduced failures (none were caused by this documentation-only audit; the previous audit recorded the same six failures):

1. `tests/test_groq_client.py::TestChatCompletion::test_successful_completion`
2. `tests/test_groq_client.py::TestChatCompletion::test_completion_with_structured_output`
3. `tests/test_groq_client.py::TestChatCompletion::test_completion_with_rate_limit_headers`
4. `tests/test_groq_client.py::TestChatCompletion::test_completion_retry_on_error`
5. `tests/test_groq_client.py::TestHelperFunctions::test_generate_reminder_draft`  
   These fail because the mock patches `munshi.llm.groq_client.Groq`, which is not a module-level attribute.
6. `tests/test_queries.py::TestParsePlaybook::test_parse_playbook_json`  
   The test expects title `Payment Collection`; parser returns `Payment Collection Playbook`.

The five Hindsight integration tests are explicitly skipped in their source because they require Hindsight; they do not test the configured Cloud connection.

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

1. **Approval is not delivery:** approval records `SENT` and `sent_at` before a message is sent. The WhatsApp URL is only a manual handoff; simulator mode has no simulated delivery.
2. **Agent logic is unreachable in routine operation:** no daily loop or normal API path invokes Collector/Risk.
3. **Simulation API is disconnected from the actual engine:** tick and injection return success without doing the advertised work.
4. **Memory retry is not automatic:** the outbox is not started and has schema/API mismatches; memory service failures may be represented as empty results.
5. **Financial summary can be misleading:** dashboard and customer overdue totals use invoice face values, not outstanding balance after payments.
6. **Evidence is lost at API boundary:** drafts have generic reasons and explain endpoints return no evidence.
7. **Normal invoice flow omits fields needed for R3/R6:** invoice GSTIN and purchase-order amount are not accepted; IRN is not modeled.
8. **Database selection depends on working directory:** both an initialized backend DB and an empty project-root DB exist.
9. **No schema migrations:** model changes can leave existing database files out of date.
10. **Band is not a transport:** no actual room posting, inbound command route, or approval parity was verified.
11. **Demo GSTINs fail the current checksum implementation:** canned invoices may appear blocked for the wrong demonstration reason. The checksum does not consult the government registry.
12. **Deployment files disagree:** Dockerfile requires the absent `uv.lock`; README/Makefile assume `uv`, which was unavailable here. Hindsight Compose image uses `latest`, reducing reproducibility.
13. **Documentation contradicts observed behavior:** README calls the project a skeleton, while `docs/AI_PROGRESS.md` labels Hindsight/Groq/Band complete. `docs/INTEGRATION_VERIFICATION.md` describes an older Hindsight API. API/database docs also disagree with current duplicate and constraint behavior.
14. **Credential exposure:** a prior test assertion printed the Groq key in local output. Rotate if that output might be shared.

## 16. Remaining work

- Keep SQLite for now; do not migrate to Supabase.
- Repair the Hindsight SDK adapter and test Munshi's own retain/recall/reflect calls.
- Reconcile the outbox with the actual `MemoryEvent` schema, add idempotency/retry scheduling, and wire startup/shutdown safely.
- Resolve the official Band SDK dependency installation, register remote agents, and implement/test real room and command transport.
- Decide on a supported Groq customer model before changing the configured identifier.
- Wire the daily loop and controlled Collector/Risk triggers to invoice, payment, and inbound-message workflows.
- Separate approval, handoff, and confirmed delivery states; preserve mandatory owner approval.
- Persist draft evidence and return it through action/explanation APIs.
- Connect simulation API controls to the deterministic world and persist evaluation outputs.
- Correct outstanding receivable calculations and add invoice GSTIN/PO amount inputs only after confirming the product contract.
- Correct synthetic GSTIN fixtures and test known-valid format/checksum examples.
- Add migrations and resolve the relative SQLite path before schema growth or deployment.
- Fix the Dockerfile/lockfile mismatch; add ESLint configuration if lint is a required check.
- Run backend/frontend end-to-end tests against a live backend and external integrations.

## 17. Which planned prompts can be skipped or should be modified

| Earlier development prompt | Recommendation | Reason |
|---|---|---|
| Database/backend foundation | **Skip a rebuild; retain only a verification pass** | The twelve SQLite entities, app foundation, route registration, error handling, and seed are present and tested. Keep SQLite; do not redo the foundation. |
| Invoice readiness | **Modify to close contract gaps only** | R1-R9 and tests exist. Focus on missing invoice GSTIN/PO amount inputs, demo GSTIN fixtures, and blocked learned-memory reads rather than rewriting the rules. |
| Collector and Risk | **Modify to wire existing logic** | Agents and policy tests exist. The remaining work is runtime triggers, memory evidence, and persistence; do not duplicate agent logic. |
| Frontend | **Skip rebuilding the seven screens; modify integration gaps** | Screens, central API client, tests, and production build exist. Prioritize live-backend validation and missing UI paths instead of recreating pages. |
| Prompt 1 credential configuration/audit | **Do not repeat as a setup task** | Groq/Hindsight settings are present; Groq had a live successful request and Hindsight was directly tested in a separate environment. Band remains blocked. Rotate the Groq key if earlier local test output could be exposed. |
| Prompt 2 Hindsight repair | **Do not skip** | Munshi's wrapper uses the incompatible `Client` class, the package is absent from the active backend venv, and the outbox is not safely running. |
| Prompts 3 and 4 | **Not yet confirmed** | Their exact requirements have not been supplied. The recommended stage boundaries below are proposals, not confirmed user-provided prompt contracts. |

### Recommended stage boundaries

1. **Prompt 2 — Hindsight integration repair:** update only the existing adapter for the current official SDK, verify retain/recall/reflect using synthetic data, reconcile outbox fields/retries, and connect lifecycle only after tests support it.
2. **Prompt 3 — Band and runtime workflow:** after the official SDK is installable and credentials are configured, verify remote agent setup, room posting, command routing, approval parity, and then wire normal backend triggers for Collector/Risk without bypassing owner approval.
3. **Prompt 4 — End-to-end simulation/evaluation and product integration:** connect sim APIs to the engine, persist evaluation outputs, reconcile evidence and financial summaries, and verify frontend-to-live-backend workflows.

## 18. Integration risks

- Direct Hindsight Cloud success does not imply Munshi's wrapper works.
- Empty memory fallback can be mistaken for “no learned behavior.”
- Groq's agent model works, but the configured customer model is not listed and structured output/retries have not been verified live.
- Band Desktop, Band account sign-in, and a registered remote agent API key are distinct setup requirements.
- Frontend tests with mocked `fetch` do not establish live API compatibility.
- `SENT` currently conflates owner approval with message delivery.
- Simulation endpoints currently provide success-shaped responses without applying scenario changes.
- Relative SQLite paths, absent migrations, and missing `uv.lock` can break local/container parity.
- The enclosing Git repository treats the entire project folder as untracked, limiting reliable change-history attribution.
