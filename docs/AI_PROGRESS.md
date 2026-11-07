# AI Progress

This document tracks the implementation progress of the Munshi backend.

---

## Prompt 3 — Operational Collector/Risk Workflows — IMPLEMENTED AND TESTED

**Current status supersedes earlier statements below that the agents are not wired.**

- FastAPI lifespan starts and stops one bounded daily Collector/Risk worker. Collector creates idempotent, evidence-backed action drafts and never sends messages.
- Payment and inbound-message routes commit ledger data first, then perform Risk assessment. The API reports assessment failure explicitly without rolling back the committed ledger write.
- Risk persists signal evidence and Hindsight availability; HIGH continues to require at least two distinct qualifying signals.
- Dashboard/customer outstanding amounts subtract recorded payments. Invoice create and the frontend invoice form carry invoice GSTIN and PO amount into existing readiness checks.
- Approval remains `APPROVED`/`EDITED`; the 09:00–19:00 IST handoff opens a prefilled WhatsApp URL only after approval, valid contact, and planned time. Separate owner confirmation records `SENT` as `OWNER_REPORTED`; it does not claim provider delivery.
- Customer detail/explain output distinguishes Hindsight unavailable from no learned history. The demo clock supports hour advancement to reach planned contact times.
- Groq wrapper supports constructor injection for tests and emits sanitized explicit provider failures. No live Groq or Hindsight call was made for Prompt 3.
- Band room transport was not modified and remains unavailable. Simulation event injection/world integration and evaluation persistence remain later work.

### Prompt 3 verification

- Backend: `.\.venv\Scripts\python.exe -m pytest -q` from `backend` — **316 passed, 1 failed, 2 skipped** out of 319. The sole failure is the existing playbook-title assertion (`tests/test_queries.py::TestParsePlaybook::test_parse_playbook_json`); the two opt-in Hindsight Cloud tests skip in default mode.
- Frontend: `npm test` — **14 passed**; `npm run build` — passed TypeScript and Vite production build.
- Backend/API tests use isolated SQLite and mocks; no external provider was contacted during these Prompt 3 checks.

---

## Hindsight Integration — COMPLETE

**Date**: 2026-11-06
**Status**: All 6 modules implemented, all test files created.

### Modules implemented

| File | Status | Description |
|------|--------|-------------|
| `backend/munshi/memory/client.py` | ✅ Done | Hindsight SDK wrapper — singleton, Cloud + local Docker, graceful degradation for all 9 SDK methods |
| `backend/munshi/memory/bank_setup.py` | ✅ Done | Bank naming (`munshi-<slug>`, `eval-<run>-C-s<seed>`), 6 directives, retain/observations/reflect missions, disposition |
| `backend/munshi/memory/events.py` | ✅ Done | 8 event type templates, tag generation (`customer:`, `kind:`, `invoice:`), format helpers per event type |
| `backend/munshi/memory/queries.py` | ✅ Done | `MemoryStore` class — `retain`, `retain_batch`, `recall`, `reflect`, `list_memories`, `create_bank`, `get_playbook`; three agent-specific helpers |
| `backend/munshi/memory/parsing.py` | ✅ Done | Pydantic models (`Requirement`, `Conflict`, `Playbook`, `ReflectResponse`), parsers, timestamp validator |
| `backend/munshi/memory/outbox.py` | ✅ Done | `OutboxProcessor` — 60s interval, 5-retry cap, exponential backoff, `queue_memory_event`, `mark_event_as_retained`, `retry_failed_events` |

### Test files created

| File | Covers |
|------|--------|
| `backend/tests/test_bank_setup.py` | Bank name generation, directives, missions, disposition, config, validation |
| `backend/tests/test_events.py` | Tag generation, all 8 template types, retain payload, format helpers |
| `backend/tests/test_queries.py` | `MemoryStore` init, reflect/recall operations, agent-specific helpers |
| `backend/tests/test_parsing.py` | All Pydantic models, parsers, timestamp validation, playbook parsing |
| `backend/tests/test_outbox.py` | Queue, mark retained/failed, retry, pending/failed counts |
| `backend/tests/test_client.py` | Singleton, availability, all SDK method wrappers (mocked) |
| `backend/tests/test_memory_integration.py` | Integration scenarios (skip unless Hindsight running) |

### Design decisions

- **Singleton client**: `HindsightClient._instance` prevents multiple SDK connections.
- **Graceful degradation**: Every SDK call is wrapped — if Hindsight is down, agents continue with empty memory, SQLite is unaffected.
- **Isolation enforced in tags**: Every retain includes `customer:<id>` so recall and reflect never bleed between customers.
- **Outbox pattern**: Failed retains are stored in `MemoryEvent` with `retained_at=NULL`. `OutboxProcessor` retries with exponential backoff (300s × 2^n). After 5 failures, `failed_at` is set; `retry_failed_events()` can reset it manually.
- **SDK import isolation**: `hindsight_client` is imported only in `client.py`. All other modules import from `munshi.memory.client`.
- **SQLite is source of truth**: Financial data (invoices, payments, balances) lives only in SQLite. Hindsight holds narrative/behavioural memory only.

### Environment variables

| Variable | Purpose | Required |
|----------|---------|---------|
| `HINDSIGHT_LOCAL_URL` | Local Docker URL (e.g. `http://localhost:8888`) | One of these |
| `HINDSIGHT_BASE_URL` + `HINDSIGHT_API_KEY` | Hindsight Cloud | One of these |
| `HINDSIGHT_TIMEOUT` | Timeout in seconds (default: 30) | No |
| `OUTBOX_INTERVAL` | Retry check interval in seconds (default: 60) | No |
| `OUTBOX_MAX_RETRIES` | Max retries before permanent failure (default: 5) | No |
| `OUTBOX_RETRY_DELAY` | Base delay in seconds for backoff (default: 300) | No |

---

## Groq LLM Integration — COMPLETE

**Date**: 2026-11-06
**Status**: All 3 modules implemented, 18 unit tests passing.

### Modules implemented

| File | Status | Description |
|------|--------|-------------|
| `backend/munshi/llm/groq_client.py` | ✅ Done | Groq SDK wrapper — singleton, authenticated, retry with exponential backoff, rate limit handling, structured output support for gpt-oss-120b/qwen3.8-27b, fallback for unsupported models |
| `backend/munshi/llm/cache.py` | ✅ Done | Disk cache with TTL (24h default), key generation based on model+messages+params, `cached_llm_call` decorator, `clear_expired()` maintenance |
| `backend/munshi/llm/json_utils.py` | ✅ Done | JSON extraction from markdown/code blocks, `validate_json_schema`, `parse_json_response`, `safe_dict_get`, `truncate_response`, `extract_json_from_text` |

### Test files created

| File | Covers | Tests |
|------|--------|-------|
| `backend/tests/test_groq_client.py` | Client initialization, model capabilities, chat completion, rate limit headers, retries | 22 tests (async) |
| `backend/tests/test_json_utils_direct.py` | JSON utilities (direct imports) | 18 tests passing |

### Model support

| Model ID | Supports Strict Output | Supports JSON Schema | Max Output Tokens | Rate Limit RPM |
|----------|----------------------|---------------------|-------------------|----------------|
| `openai/gpt-oss-120b` | ✅ Yes | ✅ Yes | 65,536 | 30 |
| `openai/gpt-oss-20b` | ✅ Yes | ✅ Yes | 65,536 | 30 |
| `qwen/qwen3.8-27b` | ✅ Yes | ✅ Yes | 16,384 | 30 |
| `qwen/qwen3-32b` | ❌ No | ❌ No | 32,768 | 30 |
| `llama-3.3-70b-versatile` | ❌ No | ❌ No | 32,768 | 30 |

### Helper functions

| Function | Purpose |
|----------|---------|
| `generate_reminder_draft()` | Generate reminder draft with phone_number, channel, message, why |
| `generate_evidence_based_message()` | Generate evidence-based customer message |
| `generate_risk_explanation()` | Generate risk explanation for owner review |
| `generate_agent_summary()` | Generate agent summary for owner review |

### Design decisions

- **Singleton client**: `GroqClient._instance` prevents multiple SDK connections.
- **Graceful degradation**: If Groq is unavailable, returns fallback response with `fallback=True` flag.
- **Structured output fallback**: Models without JSON schema support fall back to `json_object` mode.
- **Rate limit tracking**: Parses `x-ratelimit-*` headers, tracks remaining requests and reset time.
- **Retry with backoff**: Exponential backoff (1s, 2s, 4s...) on transient failures, respects `retry-after` header.
- **SDK import isolation**: `groq` is imported only in `groq_client.py`.
- **No hardcoded secrets**: API key must be set via `GROQ_API_KEY` environment variable.

### Environment variables

| Variable | Purpose | Required |
|----------|---------|---------|
| `GROQ_API_KEY` | Groq API key | Yes (for production) |
| `GROQ_AGENT_MODEL` | Model for agent operations (default: `openai/gpt-oss-120b`) | No |
| `GROQ_CUSTOMER_MODEL` | Model for customer operations (default: `qwen/qwen3.8-27b`) | No |
| `GROQ_BASE_URL` | Groq base URL (default: `https://api.groq.com/openai/v1`) | No |
| `CACHE_TTL` | Cache TTL in seconds (default: 86400) | No |

---

## Band AI Integration — BLOCKED / PLACEHOLDER

**Date**: 2026-11-06
**Status**: Command parsing and local bridge tests exist; real Band room transport is not connected.

### Modules implemented

| File | Status | Description |
|------|--------|-------------|
| `backend/munshi/band/bridge.py` | ✅ Done | Band bridge for room posting, lazy client initialization, graceful fallback |
| `backend/munshi/band/commands.py` | ✅ Done | Message parsing (draft, risk, handoff, command), regex-based parsing |
| `backend/munshi/band/run_agents.py` | ✅ Done | Agent orchestration (Collector, Risk), message routing, callback support |

### Test files created

| File | Covers | Tests |
|------|--------|-------|
| `backend/tests/test_band_commands.py` | Command parsing for drafts, risks, handoffs, owner commands | 23 tests |
| `backend/tests/test_band_bridge.py` | Bridge initialization, message routing, agent manager | 20 tests |

### Agent collaboration

| Agent | Purpose |
|-------|---------|
| **Collector** | Retrieves customer memory, plans follow-ups, generates reminder drafts for owner approval |
| **Risk** | Detects missed payments, behavior changes, financial distress, recommends alerts |

### Band SDK integration notes

**Important**: Band AI provides a Python SDK (`band-sdk`) that connects agents to a shared platform via the `band.Agent` class with framework adapters (LangGraph, Pydantic AI, etc.).

**How it works**:
1. Agents connect independently with `agent_id` and `api_key`
2. Agents join shared rooms and communicate via @mentions
3. Each agent runs independently with its own LLM/model
4. Band handles routing, history, and per-agent context isolation

**Limitations**:
- No "ExternalAgent" class in SDK — agents use `band.Agent` with framework adapters
- Desktop application is for human participation; programmatic integration uses the Python SDK
- Each agent needs its own `BAND_*_AGENT_ID` and `BAND_API_KEY` environment variables

### Environment variables

| Variable | Purpose | Required |
|----------|---------|---------|
| `BAND_ROOM_ID` | Shared room ID for agent collaboration | Yes (for collaboration) |
| `BAND_AGENT_ID` | Agent UUID from Band dashboard | Yes (for each agent) |
| `BAND_API_KEY` | Agent API key from Band dashboard | Yes (for each agent) |
| `BAND_COLLECTOR_AGENT_ID` | Collector agent UUID | Yes (for Collector) |
| `BAND_RISK_AGENT_ID` | Risk agent UUID | Yes (for Risk) |

### Current fallback behavior

When Band is unavailable, the web approvals inbox and persisted risk alerts remain available. No Band message is sent, and no Band command is routed into the web approval workflow.

### Design decisions

- **SDK import isolation**: `band-sdk` imported only in `run_agents.py`
- **Graceful fallback**: Bridge and agent manager handle missing credentials without error
- **Regex parsing**: Message parsing uses regex (not LLM) for deterministic parsing
- **Callback support**: Agents can register callbacks for events

---

## Next Steps

The following integrations remain outside Prompt 3:

- **Band transport** — real room posting, inbound command routing, and web/Band approval parity
- **Simulation/evaluation** — connect event injection to the simulation world and persist evaluation outputs

To run all unit tests:

```bash
# Hindsight tests
pytest backend/tests/test_bank_setup.py backend/tests/test_events.py backend/tests/test_parsing.py -v

# Groq tests
pytest backend/tests/test_json_utils_direct.py backend/tests/test_groq_json_utils.py -v

# Band tests
pytest backend/tests/test_band_commands.py backend/tests/test_band_bridge.py -v
```

To run integration tests (requires external services):

```bash
# Hindsight integration tests
pytest backend/tests/test_memory_integration.py -m integration -v

# Groq integration tests
pytest backend/tests/test_groq_client.py -m integration -v
```

---

## Database and Backend Foundation — COMPLETE

**Date**: 2026-11-06

- Confirmed and retained the 12 documented SQLModel entities, relationships, enum values, foreign keys, indexes, paise amounts, and invoice uniqueness constraint.
- Added database checks for positive invoice/payment amounts, non-negative customer credit days, and invoice due dates not preceding issue dates.
- Enforced documented enum values with SQLite `CHECK` constraints and added database-level invalid-enum coverage.
- Initialized tables from the application lifespan, enabled SQLite foreign keys, and kept transaction rollback behavior in the session helpers.
- Seeded the documented demo business and sample records through `seed_demo_data`.
- Registered the documented `/api` route set with Pydantic request/response shapes, a single `/health` endpoint, configured local CORS origins, and the documented error envelope.
- Removed unlisted API paths and unsupported response aliases; explain/playbook responses remain empty until their memory integration is wired.
- Used timezone-aware simulated timestamps with the fixed IST offset. Simulator resets now operate on the injected database engine, allowing isolated API tests.
- Kept external Hindsight, Groq, and Band clients and agent behavior out of this module.

### Verification

`python -m pytest tests/test_db_foundation.py tests/test_api_foundation.py -q --tb=short`

Result: **30 passed**.

### Contract conflicts for follow-up

- The invoice API documentation says a duplicate invoice number is returned as an R7 finding, while also listing 409 as a possible error and the database requires `(customer_id, number)` to be unique. Current API behavior returns 409 and preserves the database constraint; reconcile the response contract in the readiness/API phase.
- The project analysis lists R3 (invoice GSTIN matching), but the documented invoice entity and invoice-create request contain no invoice GSTIN field. No undocumented field was added; R3 requires a contract decision before implementation.
- Readiness rules and evidence-backed Hindsight integration were deferred to the dedicated readiness module documented below.

---

## Invoice Readiness and Business Rules — IMPLEMENTED

**Date**: 2026-11-06

- Implemented structural GSTIN validation, the alternating base-36 checksum, buyer-record matching when an invoice GSTIN is supplied, and buyer/supplier state-code consistency.
- Implemented fixed rules R1–R9, including one-percent PO amount comparison using integer paise, invoice-number duplicate checks, configured and attached document comparison, and a seven-day due-date warning using the shared simulated clock.
- Applied the documented result precedence: fixed blocker, evidenced missing learned requirement, memory conflict, insufficient/stale/pending evidence, then ready. If evidence timestamps cannot be verified from the event ledger, the result is UNCERTAIN.
- Retrieved learned requirements through `memory.get_memory_for_readiness`; invoice API handlers await the readiness service and do not call the Hindsight SDK.
- Added handling and tests for PO_REF, SIGNED_CHALLAN, GRN_COPY, EWAY_BILL, EINVOICE_IRN, CONTACT_PERSON, and OTHER requirements. Unavailable memory and insufficient evidence produce UNCERTAIN rather than READY.
- Added individual rule tests, GSTIN validation tests, precedence tests, memory-service tests, and an API regression run.

### Verification

`python -m pytest tests/test_gstin.py tests/test_rules.py tests/test_readiness.py tests/test_api_foundation.py -q --tb=short`

Result: **50 passed**.

The full backend suite could not be collected because the existing `tests/test_world_rules.py` imports the missing `munshi.sim` module. This simulator issue is outside the readiness module.

### Contract and validation limitations

- GSTIN format/checksum checks verify structure and the check character only. They do not confirm registration, active status, legal ownership, or portal records.
- `invoice` and `InvoiceCreate` have no invoice-recipient GSTIN, so R3 can compare only when supplied to the readiness function; the current API cannot perform that comparison.
- Neither the invoice model nor documented upload/import contract stores or extracts a PO amount. R6 supports the exact 1% calculation when supplied, but the current API skips comparison rather than inventing an amount.
- There is no dedicated e-invoice IRN field or document type. An evidenced EINVOICE_IRN requirement therefore remains unsatisfied by the current schema.
- Duplicate invoice numbers are rejected by the API before readiness is run and remain protected by the unique database constraint; R7 is independently enforced by the readiness rule when existing records are available.
- The existing demo seed contains GSTINs with structurally valid formats but invalid check characters, so seeded invoices will correctly be blocked by R2 until those demo values are updated in the database module.
- The memory parser exposes evidence IDs/counts but not consolidation state or evidence timestamps. Readiness uses the SQLite memory-event ledger for ages and returns UNCERTAIN when an evidence age cannot be verified.

---

## Collector and Risk Agents — IMPLEMENTED

**Date**: 2026-11-07

- Implemented Collector using ledger-backed invoice, payment, promise, and customer data plus customer-scoped Hindsight lookups. Memory requirements are retained only when their evidence IDs match recalled customer evidence; unscoped reflection/playbook text is not sent to the model.
- Collector produces structured reminder proposals with evidence references and an explanation, clamps contact time to 09:00–19:00 IST, caps reminders at two per invoice in a rolling seven-day period, and persists proposals as `DRAFTED` actions. It never sends a customer message; Band receives a proposal only, and the web approval path remains the fallback.
- Collector uses the existing Groq client for structured wording, retries once, and falls back to a deterministic ledger-based draft when wording generation is unavailable or invalid. Coercive language and unsupported financial claims are rejected.
- Implemented Risk signals for missed promises, repeated late payments, customer distress statements, conflicting/weakening learned behavior, and stale observations. Alerts carry evidence references and are persisted before attempting Band delivery.
- Risk uses only NORMAL, WATCH, and HIGH; shared policy validation requires at least two distinct qualifying signals for HIGH. Risk recommendations request owner review and do not change credit or dispatch decisions.
- Added tests covering draft generation, signal detection/classification, evidence references, customer isolation (including reflection/playbook content), IST contact windows, owner approval, coercive language, high-risk threshold enforcement, and Band-unavailable fallback.

### Verification

`python -m pytest tests\test_agents.py tests\test_band_bridge.py -q --tb=short`

Result: **33 passed**. Agent modules and tests also passed `py_compile`.

### Integration boundaries and limitations

- The existing `Action` schema has no durable rationale/evidence fields, and the API approval response currently supplies generic rationale text. Agent results and Band proposals include evidence, but preserving it through the existing API would require a schema/API change outside this agents-only scope.
- The Collector schedules drafts only during allowed IST contact hours. The existing approval endpoint does not independently recheck the time at approval/send time; this remains an API integration boundary and no messages are sent by Collector.
- Distress phrase detection is intentionally deterministic and may miss indirect language or flag negated phrases; alerts remain owner-reviewed rather than triggering automated decisions.
- Hindsight unavailability or insufficient scoped evidence does not authorize memory-based claims; Collector falls back to ledger-supported wording, and Risk omits unsupported memory signals.

---

## Simulation Engine — IMPLEMENTED

**Date**: 2026-11-06

- Implemented the documented `backend/sim/` profile, calibration, world, persona, and scenario structure. Preserved the existing Reddy Traders, Sharma Suppliers, Patel Enterprises, Gupta Electronics, Sharma Traders, and Patel Suppliers profiles/scenario entries; added six deterministic profiles to support the full 12-customer cohort.
- The demo scenario runs four customers; the evaluation scenario keeps its documented six-customer first-run cohort. `SimulationWorld.from_scenario("eval", customer_count=12)` expands the same seeded scenario to the full 12-customer cohort.
- Simulated runs span three learning plus three testing months (2026-01-01 through the 2026-07-01 boundary), with monthly invoices generated only for months in the evaluation interval. Calibration retains the documented seeds 1, 2, and 3.
- Per-customer and per-invoice seeded random streams determine integer-paise invoice amounts and repeatable payment timing. Runs produce synthetic payments, promises, missed-promise replies, and payment-run events; persona responses are templates and use no external LLM.
- Implemented time advancement and CONTACT_CHANGE, REQUIREMENT_CHANGE, and DISTRESS_START injection. Database persistence is opt-in via a caller-provided session and existing business; generated customers/invoices/payments/promises/messages are clearly marked synthetic, use simulated dates, and are flushed but not committed by the engine.
- Scenario files use JSON syntax, which is valid YAML 1.2, so the engine can validate and load the checked-in YAML scenarios without adding a dependency.
- Added simulator tests for repeatability, 12-customer and four-customer scenarios, six-month boundaries, payment and promise behavior, event injection, validation, and SQLite foreign-key/status consistency.

### Verification

`python -m pytest tests\test_world_rules.py -q --tb=short`

Result: **16 passed**. Simulation source and tests passed `py_compile`; both scenario files parsed and validated.

At the simulation implementation stage, the full backend run collected 315 tests: **304 passed, 5 skipped, and 6 failed** in Groq-client mock expectations and a memory playbook-title assertion. The simulation tests passed in that run. Ruff could not be run because it is not installed in the environment.

### Boundaries

- The engine creates only local synthetic data and `SIMULATED` inbound-message records; it never creates real transactions or sends messages.
- It does not modify the existing simulation API routes or database schema. Evaluation orchestration is implemented separately in `backend/eval/`.

---

## Evaluation Framework — IMPLEMENTED

**Date**: 2026-11-07

- Implemented the documented A/B/C arms: fixed rules with no memory, structured customer database memory, and Hindsight customer memory through the existing `MemoryStore` boundary. Arm A and B make no Hindsight calls; Arm C uses a unique `eval-<run-id>-C-s<seed>` bank and ignores recall results whose customer identity does not match.
- Each run uses the same deterministic six-month scenario and seed; months 1–3 are the learning period and months 4–6 are the test period. Arm C retains only training-period customer evidence and never receives test outcomes for learning.
- Implemented average days late, early-warning lead time, blocker catch rate, false-positive rate, monthly summaries, and learning curves. Missing observations remain missing and are reported with sample/missing counts rather than imputed. Reports identify simulated results and do not claim real-world impact.
- Results identify arm, seed, scenario, source fingerprint, methodology, failures, and metric definitions. JSON output is written by default to `backend/eval/results/evaluation.json`; optional `SimRun` persistence flushes into the caller's transaction without committing it.
- The simulator does not model document attachments. To exercise blocker detection, evaluation derives deterministic synthetic missing-document/PO cases from customer index and scenario month and explicitly discloses those formulas in result metadata and reports. Arm A applies fixed universal document checks; Arm B uses structured `po_required`/`required_docs`; Arm C learns customer-specific requirements from training evidence.
- Arm C fails explicitly if Hindsight is unavailable or retaining training evidence fails; it is not replaced with Arm B. If Hindsight is available but produces no usable scoped evidence, the run reports zero memory coverage, missing warnings, and evidence counts.
- Added evaluation tests for reproducibility, identical inputs across arms, test/training separation, arm isolation, Hindsight unavailability and empty evidence, customer-scoped recall, metric denominators/missing values, report provenance/failures, and transaction-safe persistence.

### Verification

`python -m pytest tests\test_evaluation.py tests\test_world_rules.py -q --tb=short`

Result: **28 passed**.

The full backend suite collected 327 tests: **316 passed, 5 skipped, and 6 failed**. The six failures are the same unrelated Groq-client mock expectations and memory playbook-title assertion seen before this evaluation implementation; all evaluation and simulation tests passed.

### Methodology limitations

- Evaluation results are deterministic synthetic experiments, not observed customer outcomes. Simulated payment behavior is not affected by evaluation-arm reminders.
- Synthetic blocker cases are generated because the simulator has no attachment model; blocker catch rates must be interpreted within the disclosed synthetic case construction.
- Arm C depends on the configured Hindsight service and documented memory API. A live Hindsight service was not needed for the test suite; tests use an isolated fake implementing that boundary.
- `SimRun` has no dedicated evaluation run identifier or scenario field, so those values are recorded in its JSON config. The evaluator leaves commit/rollback ownership to its caller.

---

## Frontend — IMPLEMENTED

**Date**: 2026-11-07

- Implemented the React 18/Vite/TypeScript/Tailwind application shell with responsive navigation for Dashboard, Customers/Customer detail, New Invoice, Approvals, Risk Alerts, Simulation Console, and Evaluation. Page modules are lazy-loaded; shared loading, empty, error, badge, panel, and action components provide consistent states.
- Centralized typed HTTP calls and backend error decoding in `frontend/src/api/client.ts`. TanStack Query owns server state and polls the documented dashboard, customer, inbox, risk, and evaluation reads every three seconds. Vite proxies `/api` to FastAPI; the frontend does not call Hindsight, Groq, or Band.
- Dashboard and customer views render API-provided collection balances, risk, structured customer information, payment timeline, playbook, beliefs, and evidence. Missing playbook/history data remains an explicit empty or updating state.
- New Invoice submits integer paise to the documented create endpoint, presents backend readiness/findings, and supports document upload followed by a readiness recheck. It does not duplicate readiness rules in the browser.
- Approvals supports draft review, editing, explicit owner approval, rejection with an optional note, and the documented explanation/evidence endpoint. Risk alerts show signals/evidence and call the backend acknowledgement/dismissal endpoint.
- Simulation controls use the documented reset, tick, and inject endpoints. Reset is confirmed because it replaces the demo database. The UI accurately reports that the current injection endpoint only acknowledges the request and does not report whether customer state changed.
- Evaluation displays available A/B/C run metrics and monthly Recharts comparisons, and labels results as simulated. No charts or production values are fabricated when the results endpoint is empty.
- Added API/client and screen interaction tests for route rendering, loading/error states, invoice paise conversion/readiness, edited approval submission, risk acknowledgement, simulation event injection, and API error decoding.

### Verification

- `npm run build` — **passed**.
- `npm test -- --reporter=dot` — **13 passed**.
- `npm audit --omit=dev --audit-level=high` — **0 production dependency vulnerabilities**.
- `npm run lint` could not run because the existing frontend project has no ESLint configuration file.

### Integration notes

- The backend is the source of truth for financial amounts, readiness, risk, action decisions, and evaluation outcomes. The frontend converts rupees to integer paise only at the invoice form boundary and formats paise for display.
- Error handling accepts both the documented `{error: ...}` envelope and FastAPI's current `detail` response shape.
- The documented backend exposes no invoice-list endpoint, so the frontend does not invent an invoice listing. Customer payment history comes from the documented customer timeline response.
- Current backend detail/explanation/evaluation responses may contain empty memory evidence or no completed metrics; those are displayed as unavailable/empty rather than replaced with sample values.
