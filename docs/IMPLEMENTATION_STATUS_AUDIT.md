> **Superseded:** The current audit is [IMPLEMENTATION_STATUS_AUDIT.md](../IMPLEMENTATION_STATUS_AUDIT.md) at the project root (2026-11-07). This older copy is retained as historical context; do not use its test counts or integration statuses as current.

# Munshi Implementation Status Audit

## Scope and evidence

This report began as a read-only audit. The API-credential follow-up below records subsequent configuration changes and live service checks. Earlier feature/test observations remain the baseline unless explicitly updated here.

The status labels below use the requested categories. “NOT VERIFIED” means there is not enough runtime or test evidence to claim the behavior works; it is not an additional implementation status.

## 1. Executive summary

Munshi is no longer an empty skeleton. It contains a persistent SQLite/SQLModel backend, all twelve documented database entities, demo seed data, a collection of working API handlers, a React dashboard, readiness checks, standalone Collector and Risk agent implementations, a deterministic simulator, and an A/B/C evaluation framework. The database, API foundation, readiness rules, agents, simulation, and evaluation have meaningful automated test coverage.

However, the system is not yet a complete end-to-end collections application:

- The current database is **SQLite**, not Supabase. The backend SQLite file contains the schema and demo rows. No Supabase connection, schema, or migration is present.
- The frontend makes API requests, but its component tests mock `fetch`; no backend was listening during this audit. Live browser-to-server integration is **NOT VERIFIED**.
- The simulation engine and evaluation runner exist, but the simulation HTTP routes do not call the engine. Simulation tick only changes the shared clock, while event injection only acknowledges the request.
- Collector and Risk logic exists, but no running application service invokes the agents. The daily loop is a TODO and is not started by FastAPI.
- The approval route records an action as `SENT` before any WhatsApp handoff is actually completed. Simulator mode does not deliver it to a simulated customer.
- Groq credentials are configured and one minimal live request succeeded with `openai/gpt-oss-120b`. The configured customer model `qwen/qwen3-32b` is not present in the current Groq model list. Hindsight Cloud credentials are configured and a synthetic test bank retain/recall succeeded, but Munshi's existing wrapper is incompatible with the installed SDK API. Band credentials are absent and its SDK install is blocked by a missing transitive package in the configured package index.
- The backend test run collected 327 tests: **316 passed, 6 failed, and 5 were skipped**. Frontend tests passed (**13/13**) and its production build passed. Frontend lint could not run because the project has no ESLint configuration.

**Bottom line:** preserve the existing work and close the integration gaps; do not restart the project from the foundation prompts. The latest database instruction is to keep local SQLite; no Supabase configuration or migration was made.

## 2. Existing project structure

The main folders and files inspected are:

```text
devnovate/
  backend/
    munshi/
      api/          FastAPI routers and API schemas
      agents/       Collector, Risk, shared policy, prompts
      band/         Band bridge, command parser, agent manager
      checks/       GSTIN validation, R1-R9 readiness rules
      db/           SQLModel entities, SQLite sessions, demo seed
      llm/          Groq client, JSON helpers, disk cache
      memory/       Hindsight wrapper, parsing, queries, outbox
      services/     Shared clock, WhatsApp link, daily loop
    sim/            Profiles, personas, deterministic simulation world
    eval/           Evaluation runner, arms A/B/C, metrics, report
    tests/          Pytest suites
  frontend/
    src/api/        Central API client
    src/pages/      Dashboard, customer, invoice, approvals, risk,
                    simulation, and evaluation screens
    src/            React/Vite/TypeScript application
  docs/             Module contracts, integration notes, progress,
                    evaluation, demo, and project documentation
  API_DOCUMENTATION.md
  ARCHITECTURE.md
  DATABASE_DESIGN.md
  DEVELOPMENT_RULES.md
  docker-compose.yml
  Makefile
  README.md
```

The repository root is `C:\Users\Dell\Downloads`; the project is in its `devnovate` subdirectory. That parent repository has unrelated workspace changes; this audit did not attempt to alter or clean them.

## 3. Technology stack actually detected

| Area | Detected implementation |
|---|---|
| Backend | Python 3.11.9, FastAPI 0.141.1, SQLModel 0.0.48, SQLAlchemy, Pydantic settings |
| Database | SQLite, with a relative default URL `sqlite:///./munshi.db` |
| Frontend | React 18, Vite 5, TypeScript, Tailwind CSS, TanStack Query, Recharts |
| LLM | Groq Python SDK 1.7.0 installed in the Python 3.11 environment used for tests |
| Memory and collaboration SDKs | Hindsight client 1.2.0 was installed in an isolated verification environment; the configured package index could not resolve Band SDK 8.1.0's required `band-sdk-core==6.1.1` |
| Testing | pytest (backend); Vitest/Testing Library (frontend) |
| Deployment support | Dockerfile, Docker Compose file, Makefile; Docker Compose command unavailable during audit |
| Supabase | No Supabase client, URL, schema, migration, or deployment configuration found |

The selected Pylance interpreter is a separate Python 3.13 environment and does not resolve the backend dependencies. The backend test command used Python 3.11.9 successfully. Configure VS Code to use the intended backend environment to avoid misleading editor import diagnostics.

## 4. Backend implementation status

| Area | Status | What the source and tests establish |
|---|---|---|
| Database models | **Fully implemented and verified** | Twelve SQLModel tables, primary/foreign keys, relationships, enum checks, indexes, integer-paise amounts, and tested SQLite constraints exist. |
| Database initialization | **Fully implemented and verified** | FastAPI lifespan calls `SQLModel.metadata.create_all`; session fixtures test initialization and rollback. This is not a schema migration system. |
| Demo seed | **Fully implemented and verified** | `seed_demo_data` persists one supplier, three buyers, three invoices, a document, readiness check, action, payment, promise, inbound message, and risk alert. Seed records are hard-coded, fictional demo data stored in SQLite. |
| FastAPI foundation | **Fully implemented and verified** | Router registration, `/health`, CORS, validation/error envelopes, and database dependency behavior have API test coverage. A standalone Uvicorn process was not run. |
| API/database operations | **Partially implemented** | Most documented handlers query or mutate SQLite. Some integrations described by the API contract are placeholders, and some routes do not connect to their corresponding engine/service. |
| Readiness rules | **Partially implemented** | R1–R9 are implemented and covered by tests. Some inputs required by the contract do not exist in the invoice schema or API, so rules R3 and R6 cannot be fully exercised through normal invoice requests. |
| Collector and Risk | **Partially implemented** | Agent code and tests exist. No app startup task, API handler, or daily service invokes them during normal operation. |
| Daily loop | **Placeholder** | `services/daily_loop.py` contains a TODO rather than invoice scanning or agent calls; FastAPI does not start it. |
| Hindsight outbox | **Partially implemented** | A retry processor and local `MemoryEvent` rows exist, but FastAPI does not start the processor, so pending events are not automatically retained. |
| Authentication | **Not implemented** | There is no authentication or authorization. This matches the documented single-demo prototype scope but is not appropriate for a multi-user production deployment. |
| Schema migrations | **Not implemented** | Startup uses `create_all`; no Alembic migrations were found. Existing database schema changes will not be reliably migrated. |

### Readiness and GSTIN details

The readiness code contains:

- **R1/R2:** supplier and buyer GSTIN format and check-character validation.
- **R3:** invoice GSTIN matching when an invoice GSTIN is supplied. The invoice model and create request have no invoice GSTIN field; the API does not supply one, so R3 reports the match as not verifiable and passes.
- **R4:** state-prefix consistency between GSTIN and each saved state code.
- **R5:** customer PO requirement and PO-number presence.
- **R6:** 1% invoice/PO amount tolerance when a PO amount is supplied. There is no PO amount field or extraction path, so the normal API flow skips the comparison.
- **R7:** duplicate invoice-number check per customer, backed by a unique database constraint. The create API returns HTTP 409 before a readiness finding can be returned, which conflicts with the documented example that says duplicate is a finding.
- **R8:** due-date warning; a past-due invoice is not itself a blocker under this rule.
- **R9:** comparison of customer-required documents with uploaded document types.

GSTIN validation is structural and algorithmic, not a check against the government GST registration registry. It cannot establish that a GSTIN is active or belongs to the actual legal entity. The seeded business and customer GSTIN examples pass format checks but fail the implemented checksum calculation. Consequently, demo readiness checks can legitimately produce GSTIN blockers on the canned demo data.

The learned-requirement combiner recognizes the documented codes, including `PO_REF`, `SIGNED_CHALLAN`, `GRN_COPY`, `EWAY_BILL`, `EINVOICE_IRN`, `CONTACT_PERSON`, and `OTHER`. But there is no IRN model field or document type; an `EINVOICE_IRN` requirement is treated as missing. Live memory retrieval depends on the unavailable Hindsight service.

## 5. Frontend implementation status

The seven requested screens are present, built, and rendered in frontend tests:

| Screen | Status | Observed behavior |
|---|---|---|
| Dashboard | **Partially implemented** | Fetches actual summary endpoint and links to risk customers and approvals. Backend sums invoice face value rather than outstanding balances. |
| Customer | **Partially implemented** | Lists and fetches customer records and ledger timeline. The customer detail API always returns an empty playbook, `updating: true`, and no beliefs. |
| New Invoice / Readiness | **Partially implemented** | Creates an invoice, uploads a document, and rechecks readiness through the central API client. No PO amount or invoice GSTIN can be entered. |
| Approvals Inbox | **Partially implemented** | Lists drafts and sends edit/approve/reject requests. “Why” and explanation data from the backend are generic or empty; the approval result may say SENT even though no message was sent. |
| Risk Alerts | **Partially implemented** | Lists stored alerts and submits acknowledge/dismiss decisions. The screen does not trigger risk assessment itself. |
| Simulation Console | **Partially implemented** | Calls reset, tick, and inject endpoints. Tick does not run the simulation engine; inject does not apply the event to customer state. |
| Evaluation | **Partially implemented** | Reads and charts persisted results, with empty states. No results file or `sim_run` rows existed during this audit. |

The API client is centralized in `frontend/src/api/client.ts`, and page-level TanStack Query requests generally poll every three seconds. UI tests mock `fetch`, so they verify component behavior and request wiring rather than a live backend. The browser smoke check from earlier work and current local checks found no backend on port 8000.

## 6. Database readiness (SQLite retained)

### Current database

The project currently uses SQLite. Read-only inspection found:

| File | Tables | Rows observed |
|---|---:|---|
| `backend/munshi.db` | 12 | 1 business, 3 customers, 3 invoices, 1 invoice document, 1 readiness check, 1 action, 1 inbound message, 1 payment, 1 promise, 1 risk alert, 0 memory events, 0 simulation runs |
| `munshi.db` at the project root | 0 | No application tables |

Thus, the backend database is real local persistence, not an in-memory or JSON mock. The sample records originate as literals in `backend/munshi/db/seed.py` and are stored in the backend SQLite file. The top-level empty file illustrates a path risk: the relative `DATABASE_URL` can create different database files depending on the process working directory.

| Question | Finding |
|---|---|
| Are tables actually created? | Yes: all twelve documented tables were present in the backend SQLite file. |
| Are models connected to a database? | Yes: SQLModel creates the SQLite engine and the API handlers use injected sessions. |
| Is data persistent? | Yes, locally in `backend/munshi.db` when run from the backend directory. |
| Are records hard-coded? | Demo values and simulation profiles are hard-coded in seed/profile/scenario files, then persisted when those paths run. |
| Is Supabase configured? | No. The latest instruction explicitly keeps SQLite, so Supabase was not configured or migrated. |
| Are migrations present? | No. `create_all` is used; there is no migration history. |
| Are relationships and constraints present? | Yes for the documented model relationships and core tested constraints. Not every cross-entity business invariant is enforced by SQL constraints. |

The earlier audit recommended evaluating Supabase based on a previous database preference. That recommendation is superseded by the latest instruction: keep the current local SQLite database. This task did not change database URLs, tables, seeds, or persistence.

## 7. Groq API status

**Status: Implemented and live connection verified for one minimal request; broader model behavior remains partially verified.**

- `GROQ_API_KEY` is present in `backend/.env`; its value is not included in this report. A failed test assertion exposed it in local test output; rotate it if that output is accessible to others. The file is ignored by `backend/.gitignore`.
- The installed Groq SDK is 1.7.0. The backend configuration now loads the absolute `backend/.env` path independent of the current working directory, and preserves shell environment overrides.
- One real chat completion succeeded with model `openai/gpt-oss-120b`.
- The live model list includes `openai/gpt-oss-120b` and `qwen/qwen3.8-27b`, but does not include the configured customer model `qwen/qwen3-32b`. The project must decide whether to update the customer model setting; it was not changed in this credential-only task.
- The first request returned HTTP 404 because the Groq SDK's default root URL had been configured with an additional `/openai/v1` suffix. The configured base was corrected to `https://api.groq.com`; the following request succeeded.
- The source client builds chat-completion requests and contains structured-output, retry, and fallback code. Real structured output, retries, rate limits, and model-specific behavior remain **NOT VERIFIED**.
- Five pre-existing tests failed because they patch `munshi.llm.groq_client.Groq`, but the implementation imports `Groq` locally inside `_initialize` and does not expose that module-level name. These failures do not contradict the successful live request.

## 8. Hindsight status

**Status: Cloud connection and basic bank operations verified directly; Munshi's existing SDK wrapper remains incompatible.**

- `HINDSIGHT_API_KEY` and `HINDSIGHT_BASE_URL` are present in `backend/.env`; their values are not included in this report. The backend configuration now loads them independently of the working directory.
- Installed `hindsight-client` 1.2.0 in an isolated verification environment, using the official current `Hindsight` client. The Cloud service reported API version 1.1.0.
- Created synthetic test bank `munshi-config-check-a152a59c20`, retained a non-customer test fact, and recalled one result successfully. The test bank was left in place; no deletion was attempted.
- This does **not** establish that the application memory pipeline works: `backend/munshi/memory/client.py` expects `hindsight_client.Client`, which is not exported by version 1.2.0 (it exports `Hindsight`). The app wrapper's availability check fails with that SDK.
- Readiness, Collector, Risk, and evaluation Arm C call the wrapper. Their real cloud calls remain blocked until the wrapper is updated to the installed SDK contract.
- The outbox is not started by the app lifecycle; timestamp semantics, customer isolation through Munshi, retries, consolidation, and agent use of retrieved memories remain **NOT VERIFIED**.
- `docs/INTEGRATION_VERIFICATION.md` still has blank verification fields. Customer playbook/belief retrieval is not wired into customer detail.

## 9. Band AI status

**Status: Mocked; real connection blocked by missing credentials and SDK dependency resolution.**

- The current official Python SDK documentation is for `band-sdk` 8.1.0. A normal install attempt failed because the configured package index has no `band-sdk-core==6.1.1`, which that release requires. No Band SDK was installed.
- No Band room ID, remote-agent IDs, or agent API keys are configured. The backend template now documents separate `BAND_COLLECTOR_API_KEY` and `BAND_RISK_API_KEY` values because Band issues an API key for each registered agent; the agent manager reads these separate settings.
- Band Desktop runs supported local coding agents, but it does not by itself connect Munshi's custom Collector/Risk processes. The official SDK quickstart requires creating remote agents in Band, saving each agent's ID/API key, and running the SDK agent process. Band SDK uses the agent key and a WebSocket connection.
- `band/commands.py` implements regex parsing and has passing unit tests. `band/run_agents.py` contains scaffolding, but FastAPI does not start it and no inbound route connects commands to action approval.
- `band/bridge.py` only logs “Would post…”; it sends no room message. No Band-originated approval is verified.
- Current SDK compatibility, real agent sessions, room posting, inbound command routing, and web/Band approval parity remain **NOT VERIFIED**.

## 10. Feature-by-feature status

Each feature has one primary status label. Details explain remaining gaps without combining status categories.

| # | Feature | Status | Finding |
|---:|---|---|---|
| 1 | Dashboard | **Partially implemented** | Real DB summary endpoint and UI exist. Receivable and overdue figures use full invoice amounts, not amount less payments. |
| 2 | Customer management | **Partially implemented** | DB-backed list and patch exist; customer detail history is assembled from DB. No standalone customer-create endpoint; imports create customers. |
| 3 | Customer payment history | **Fully implemented and verified** | Payment rows are stored in SQLite and included in the customer timeline; API/test coverage exists. This is ledger history, not Hindsight history. |
| 4 | Invoice creation and management | **Partially implemented** | Create, readiness, upload, confirm, send, and CSV import routes exist. There is no invoice-list/get endpoint or invoice-list UI. |
| 5 | Invoice readiness checks | **Partially implemented** | R1–R9 and precedence are implemented and tested; R3/R6 fields cannot be supplied in the normal API flow. |
| 6 | GSTIN validation | **Partially implemented** | Format, check character, record match, and state-prefix helpers exist. No GST registry/active-status validation; API cannot supply invoice GSTIN. Seeded examples fail checksum. |
| 7 | Purchase order validation | **Partially implemented** | PO-required and PO-number presence checks work. Amount tolerance exists only when a PO amount is supplied; normal API has no PO amount. |
| 8 | Required document validation | **Fully implemented and verified** | Document upload and configured required-document checks are present. Upload files are stored on local disk, not Supabase storage. |
| 9 | Learned customer requirements | **Partially implemented** | Codes and readiness precedence exist and call the memory service. Live Hindsight is blocked; customer detail does not return learned beliefs. |
| 10 | Collector agent | **Partially implemented** | Agent draft logic and tests exist, but no normal API/scheduler path invokes it. |
| 11 | Risk agent | **Partially implemented** | Signal calculation, evidence references, risk levels, and alert persistence exist. No normal event path invokes reassessment. |
| 12 | Reminder drafting | **Partially implemented** | Collector can persist a draft when directly invoked. Daily loop is a TODO; no UI/API action generates drafts. |
| 13 | Owner approval workflow | **Partially implemented** | Approve/edit/reject handlers persist decisions, but approval sets `SENT`/`sent_at` before a real send. |
| 14 | Inbound customer messages | **Partially implemented** | API stores the message and local memory event. It does not enqueue a working risk assessment or connect to WhatsApp/email. |
| 15 | Payment recording | **Fully implemented and verified** | API checks outstanding amount, persists payment, and updates invoice status. It does not trigger Risk or live memory retention. |
| 16 | Hindsight retention and retrieval | **Blocked** | Wrappers and call sites exist, but SDK/service/configuration are unavailable; integration tests are skipped and outbox is not started. |
| 17 | Band AI workflow | **Mocked** | Regex parser exists; outbound bridge only logs, no webhook exists, and no approval command reaches the API. |
| 18 | Simulation engine | **Fully implemented and verified** | Seeded deterministic world, profiles, promises, payments, time advancement, injection, and SQLite persistence hooks exist; world-rule tests pass. API controls do not use it. |
| 19 | Evaluation Arms A/B/C | **Partially implemented** | Arm policies, six-month separation, metrics, and report code have tests. Hindsight Arm C needs live service; no result artifact or `sim_run` rows were found. |
| 20 | WhatsApp prefilled message | **Partially implemented** | A `wa.me` link can be generated outside simulator mode. It is not a WhatsApp API send; simulator mode does not deliver to a simulated customer. |
| 21 | Risk alerts | **Partially implemented** | Alerts can be read/acknowledged and the agent can persist alerts when invoked. Existing demo alert is seeded; automatic assessment is not wired. |
| 22 | Explainability and evidence | **Placeholder** | Readiness findings can include evidence IDs and Risk can store references. Action “why” is generic, action explain returns an empty evidence list, and `/api/explain` always says no evidence is available. |

## 11. API endpoint verification

“Tested” means the backend `test_api_foundation.py` ASGI/TestClient suite exercises the documented API paths or their basic validation/response behavior. Those tests use a test database and do **not** prove live Hindsight, Groq, Band, WhatsApp, or frontend-to-running-server behavior. “Frontend uses” refers to the current source, not a live network session.

| Method and route | Route status | Database / response source | Tested | Frontend uses |
|---|---|---|---|---|
| `GET /health` | Registered | Liveness timestamp from app clock; no DB query | Yes | No |
| `POST /api/import/tally-csv` | Registered | Creates customer/invoice rows; CSV import | Yes | No |
| `GET /api/dashboard` | Registered | Aggregate queries over SQLite | Yes | Yes |
| `GET /api/customers` | Registered | Customer and invoice aggregates from SQLite | Yes | Yes |
| `GET /api/customers/{id}` | Registered | Customer and ledger timeline from SQLite; playbook/beliefs hardcoded empty | Yes | Yes |
| `PATCH /api/customers/{id}` | Registered | Updates SQLite; writes a local memory-event row | Yes | No |
| `POST /api/invoices` | Registered | Writes invoice/readiness rows; invokes readiness rules and memory abstraction | Yes | Yes |
| `POST /api/invoices/{id}/documents` | Registered | Stores file locally and document metadata in SQLite | Yes | Yes |
| `POST /api/invoices/{id}/check` | Registered | Updates readiness/check rows; may query Hindsight through memory service | Yes | Yes |
| `POST /api/invoices/{id}/confirm` | Registered | Updates customer requirements and readiness in SQLite | Yes | No |
| `POST /api/invoices/{id}/send` | Registered | Marks invoice SENT and creates local memory-event row; no actual send | Yes | No |
| `GET /api/actions?status=...` | Registered | Reads SQLite; `why` is a fixed generic string | Yes | Yes |
| `POST /api/actions/{id}/approve` | Registered | Marks action SENT and creates local memory event; returns optional `wa.me` link, not actual delivery | Yes | Yes |
| `POST /api/actions/{id}/reject` | Registered | Updates SQLite; optional reason becomes local memory event | Yes | Yes |
| `GET /api/actions/{id}/explain` | Registered | Generic summary and empty evidence list | Yes | Yes |
| `POST /api/messages/inbound` | Registered | Writes inbound message and local memory-event row; reports `risk_check_queued=true` without a worker | Yes | No |
| `POST /api/payments` | Registered | Writes payment and updates invoice status in SQLite | Yes | No |
| `GET /api/risk/alerts` | Registered | Reads SQLite alerts | Yes | Yes |
| `POST /api/risk/alerts/{id}/ack` | Registered | Updates SQLite alert status | Yes | Yes |
| `POST /api/explain` | Registered | Hardcoded “No evidence is available yet.” response | Yes | No |
| `POST /api/sim/reset` | Registered | Drops/recreates selected DB and reseeds demo data; resets clock; scenario parameter is not used to load a simulation scenario | Yes | Yes |
| `POST /api/sim/tick?days=N` | Registered | Advances clock only; reports zero drafts and alerts | Yes | Yes |
| `POST /api/sim/inject` | Registered | Acknowledges request; does not mutate simulated or customer state | Yes | Yes |
| `GET /api/eval/results` | Registered | Reads `sim_run` records; empty/default results when no runs are persisted | Yes | Yes |
| `GET /api/documents/{id}` | **Not registered** | Handler exists in `api/documents.py`, but `main.py` does not include that router | No | No |

The frontend does not currently call the CSV import, customer patch, invoice confirm/send, inbound message, payment, plain-language explain, or document-download endpoints. The API contract’s duplicate-number behavior also differs: it documents a duplicate finding while the implementation returns 409.

## 12. Hardcoded, mocked, and placeholder behavior

| Kind | Examples |
|---|---|
| Hardcoded demo data | The seed function contains a named demo business, customers, invoices, payment, promise, action, and risk alert. These are stored in SQLite when seeded; they are not production records. Simulator profiles and scenario files also contain fixed synthetic data. |
| Hardcoded API output | `/api/explain` returns a fixed no-evidence answer; customer detail returns empty/updating memory; action list and action explanation do not retrieve saved evidence. |
| Mocked external behavior | Band bridge logs the message it “would post.” Frontend API tests mock `fetch`. Agent unit tests mock memory/Groq/Band collaborators. |
| Placeholder workflow | Daily loop has TODO logic; simulation tick/inject do not execute the simulator; inbound message’s “risk queued” flag does not correspond to a running queue. |
| Fallback behavior | Groq returns fallback text when unavailable; Collector can use fixed wording. Hindsight operations generally return empty lists/dicts when unavailable. These fallback paths are not equivalent to a working external integration. |
| Local-only persistence | SQLite stores data; invoice documents are written to local filesystem uploads. Neither is Supabase-backed. |

## 13. Tests and execution

### Backend

Command run from `backend`: `python -m pytest -q`

- Discovered: **327 tests**
- Passed: **316**
- Failed: **6**
- Skipped: **5**
- Warnings: **9**
- Duration: **15.56 seconds**

Failures:

1. Four Groq chat-completion tests and one Groq helper test fail before the API is called because the test patches a module-level `Groq` name that the implementation does not expose.
2. One playbook parser test expects title `Payment Collection`, while the parser returns `Payment Collection Playbook`.

The five Hindsight integration tests were skipped. The database, API foundation, readiness, GSTIN, agent, simulator world, Band parser, and evaluation unit tests passed within this suite. This does not constitute live external integration testing.

For the later credential-configuration changes, 8 focused Groq initialization/model tests and all 21 Band bridge tests passed. Modified Python modules compiled successfully. Ruff was not installed, so lint was not run. These targeted results do not replace the historical full-suite results above.

### Frontend

- `npm test -- --reporter=dot`: **2 test files passed; 13 tests passed**.
- `npm run build`: **passed** (`tsc` and Vite production build).
- `npm run lint`: **not passed**. ESLint exits because there is no ESLint configuration file.
- Tests exercise UI and API-client behavior with mocked responses. A real API server was not running.

### Runtime and external services

- Local `http://127.0.0.1:8000/health`: not responding.
- Local `http://127.0.0.1:8888/health`: not responding.
- Docker Compose: unavailable in this environment.
- Backend startup as a standalone Uvicorn process: **NOT VERIFIED**. ASGI TestClient tests exercised app setup and routes.
- Supabase connection: not configured by design; the current instruction keeps SQLite.
- Groq live call: **verified**; one completion succeeded with `openai/gpt-oss-120b`.
- Hindsight Cloud: **verified directly**; API version 1.1.0, synthetic bank created, retain succeeded, and recall returned one result. Munshi's wrapper is incompatible with the installed SDK.
- Band live connection: **NOT VERIFIED**; credentials are absent and SDK installation is blocked by its unavailable `band-sdk-core==6.1.1` dependency.
- WhatsApp delivery: **NOT VERIFIED**; source only builds an external prefilled link in a non-simulator path.

## 14. Environment variables and external dependencies

This report does not include credential values. A failed test assertion emitted the configured Groq key in local test output; treat it as exposed if that output is accessible to anyone else and rotate it in the Groq console. The tests now isolate settings with synthetic values. `backend/.env` exists and is ignored by `backend/.gitignore`; the following service settings are present:

- `GROQ_API_KEY`
- `HINDSIGHT_API_KEY`, `HINDSIGHT_BASE_URL`

Band room/agent IDs and per-agent API keys are missing. The backend now loads its absolute `.env` path independently of the current working directory, with already-set process variables taking precedence. A runtime check from the repository parent confirmed this behavior without printing values.

The root `.env.example` points developers to `backend/.env.example`. The backend template contains empty credential placeholders, does not contain real keys, and keeps API credentials out of Vite variables. Band's documented separate agent-key requirements are represented by `BAND_COLLECTOR_API_KEY` and `BAND_RISK_API_KEY`. SQLite remains the configured database; no Supabase variables or migration were added.

The existing webhook template value points to `/api/band/webhook`, but no such route exists. Docker Compose specifies a local Hindsight URL and SQLite URL for its backend container; Docker was unavailable during the earlier audit.

## 15. Critical bugs and architectural problems

1. **Approval is not delivery.** The approval endpoint immediately sets `status=SENT` and `sent_at`; the WhatsApp link is only returned afterward. In simulator mode it returns no link and does not invoke the simulator. The recorded state can claim a message was sent when it was not.
2. **Agent workflows are unreachable in normal operation.** No API path creates a Collector draft or invokes Risk after a payment/message; `daily_loop` is unfinished and not started.
3. **Simulation UI implies behavior that does not happen.** Tick advances only the shared clock, returns zero actions, and injection returns `{ok:true}` without changing the engine or customer record. Reset always seeds the database, regardless of requested scenario.
4. **Memory retries are not automatically processed.** The outbox exists but is not started from the app lifecycle. Memory records created by writes do not reach Hindsight automatically.
5. **Dashboard amounts are not outstanding balances.** Receivable and overdue queries sum original invoice amounts and do not subtract recorded payments.
6. **Evidence is lost at the API boundary.** Collector plans carry evidence, but `Action` has no rationale/evidence storage. Action list supplies a generic reason and action explain returns no evidence; `/api/explain` is also a fixed answer.
7. **Normal invoice flow cannot validate some documented fields.** Invoice GSTIN and PO amount are absent, so R3 and R6 cannot be fully run through the API. EINVOICE IRN is likewise not represented.
8. **SQLite schema upgrades are not automated.** SQLite is the chosen database for this task, but there are no versioned migrations; `create_all` does not upgrade existing schemas.
9. **Relative database path creates ambiguity.** The backend DB has 12 tables, while a second root-level `munshi.db` has none. Different working directories can silently select different files.
10. **Band integration is not a transport.** The configured webhook is absent and the bridge does not post. There is no demonstrated route from a Band command to the same web approval endpoint.
11. **Demo GSTINs do not satisfy the current checksum implementation.** This makes the canned examples fail checksum readiness, which may confuse a demo operator.
12. **Documentation is stale or conflicting.** README still calls the project a skeleton, database docs say constraints are missing although code contains several, and the API contract’s duplicate invoice behavior conflicts with the 409 implementation. Groq model defaults also differ across config and client code.

## 16. Remaining work

- Keep SQLite as directed. Do not migrate to Supabase unless the database decision changes.
- Update `memory/client.py` from the legacy `hindsight_client.Client` reference to the current `hindsight_client.Hindsight` interface, then test the application-level retain/recall path against the verified Cloud service.
- Resolve the Band SDK package-index dependency issue, then validate the exact SDK version/API signatures before wiring Band room traffic.
- Decide whether to replace the unavailable configured customer model `qwen/qwen3-32b` with the currently listed `qwen/qwen3.8-27b`; do not change model behavior without approval.
- Complete the memory outbox lifecycle and verify timestamp, isolation, reflect, and retry behavior with real Hindsight.
- Connect the daily scheduler and inbound/payment event flows to Collector/Risk, keeping recommendations owner-approved.
- Store and return agent evidence so the customer profile, inbox, and explain endpoint are truthful.
- Define approval vs actual dispatch states and ensure simulator/WhatsApp actions correspond to what occurred.
- Make simulation routes call the existing simulation world, or clearly separate the simulation API from the engine.
- Persist and expose evaluation runs/results; report Arm C failure when Hindsight is unavailable.
- Decide how the invoice GSTIN and PO amount enter the system before claiming R3/R6 are end-to-end.
- Resolve demo GSTIN fixtures and the model-ID mismatch.
- Add ESLint configuration if lint is intended to be a required check.
- Update README, API/database docs, integration verification, and AI progress so they reflect observed behavior rather than intended behavior.

## 17. Recommended implementation order

1. **Repair the Hindsight SDK wrapper.** The credentials and Cloud service work, but Munshi's current wrapper imports a class absent from the installed SDK. Adapt only that client boundary and verify app-level retain/recall.
2. **Resolve Band SDK installation/authentication.** Use an index that provides the official SDK's required dependency, configure one agent ID/key per Collector and Risk agent, then test actual room communication and approval routing.
3. **Decide on the customer model.** Groq confirmed the configured `qwen/qwen3-32b` is not currently listed; approve an active replacement before changing it.
4. **Make the core backend truthful.** Correct outstanding-balance calculations, action rationale/evidence persistence, and approval-vs-send semantics.
5. **Wire agents to backend events.** Start a safe scheduler/worker, invoke Risk after inbound messages and payments, and create Collector drafts only through controlled triggers. Keep human approval mandatory.
6. **Complete Hindsight lifecycle tests.** Verify timestamps, event isolation, evidence retrieval, retries, and startup/shutdown of the outbox.
7. **Connect simulation/evaluation surfaces.** Route simulation controls through `SimulationWorld`, persist reproducible evaluation outputs, and display failures/missing metrics without inventing results.
8. **Run integration tests and refresh documentation.** Test the running backend, frontend against it, Groq, Hindsight, Band, and the complete demo path; keep SQLite as the current database.

## 18. Risks that could cause integration problems

- SQLite’s relative URL can make developers and containers use different database files.
- The `ActionStatus.SENT` name currently conflates owner approval with actual message delivery.
- Empty memory fallback can look like valid “no learned behavior” data unless API/UI surfaces service availability explicitly.
- Munshi's Hindsight wrapper currently expects `hindsight_client.Client`, while the verified SDK exports `Hindsight`; successful direct service checks do not mean the application memory flow works.
- Band SDK 8.1.0 installation is blocked by unavailable dependency `band-sdk-core==6.1.1`; credentials and room transport are unverified.
- Groq's agent model is live and succeeded, but the configured customer model is not listed and structured-output behavior is untested.
- Frontend tests passing with mocked fetch can be mistaken for real API integration.
- Simulation endpoints currently provide success-shaped responses without running scenario behavior.
- `create_all` does not upgrade existing databases when models change.
- Demo GSTIN check failures make readiness examples appear broken unless fixtures are corrected.
- The requested API configuration guide, audit, and checklist are explicitly exempted from the existing `docs/*.md` ignore rule so they can be tracked.
