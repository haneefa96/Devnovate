# Munshi Implementation Checklist

Current evidence and status details are in [IMPLEMENTATION_STATUS_AUDIT.md](./IMPLEMENTATION_STATUS_AUDIT.md). This checklist distinguishes tested behavior from source-code presence.

## Already completed and verified

- [x] Twelve SQLModel tables, relations, integer-paise amounts, indexes, and core constraints.
- [x] SQLite initialization, sessions, transaction rollback, and demo seed tests.
- [x] Persistent fictional demo records in `backend/munshi.db`.
- [x] FastAPI health endpoint, route registration, CORS, validation/error envelopes, and DB injection tests.
- [x] GSTIN helper and R1-R9 readiness unit tests; invoice GSTIN and PO amount flow through the normal API.
- [x] Collector/Risk policy, evidence, daily-loop, and payment/message-triggered workflows.
- [x] Dashboard/customer outstanding amounts subtract ledger payments.
- [x] Action evidence and rationale persist; owner approval, WhatsApp handoff, and owner-reported sending are distinct.
- [x] Guarded WhatsApp handoff requires an approved action, planned time, valid phone, and 09:00–19:00 IST contact window.
- [x] Customer detail/explain responses distinguish Hindsight unavailable from an empty memory result.
- [x] Simulation clock supports day/hour advancement; the simulation event injection/world integration remains outstanding.
- [x] Updated API, frontend, README, and implementation-status documentation for the operational behavior.
- [x] Seven React screens and centralized API client.
- [x] Backend startup and `GET /health` HTTP 200 during this audit.
- [x] Frontend tests: 14 passed.
- [x] Frontend production build: passed.
- [x] Groq credentials load in backend settings; minimal live request succeeded with `openai/gpt-oss-120b`.
- [x] Direct Hindsight Cloud synthetic bank/retain/recall was previously verified with SDK 1.2.0 in a separate verification environment.
- [x] Installed `hindsight-client==1.2.0` in the active backend Python 3.11.9 environment and verified the installed `Hindsight` async API.
- [x] Repaired Munshi's existing Hindsight adapter; live synthetic Cloud tests verified bank access, retain, recall, reflect, timestamp/metadata handling, customer tags, and business isolation.
- [x] Connected the persisted memory outbox to FastAPI lifespan; mocked/local tests cover confirmed-success status, retry bounds, duplicate prevention, failure handling, and worker shutdown.
- [x] Hindsight outages now surface explicitly; readiness marks memory pending and Collector/Risk continue from ledger evidence instead of treating errors as empty memory.
- [x] `backend/.env` is ignored; templates contain empty secret placeholders; no frontend `.env` file was found.
- [x] Keep local SQLite for this stage; no Supabase configuration or migration.

## Partially completed

- [ ] `EINVOICE_IRN` has no corresponding document/IRN field.
- [ ] WhatsApp provider sending/delivery verification is not implemented; `SENT` is an owner-reported state only.
- [ ] Simulation event injection does not update the deterministic simulation world.
- [ ] Evaluation runner exists but there are no stored `sim_run` results.
- [ ] Backend suite has one existing parser-title assertion failure; details are in the audit.
- [x] Prompt 2 focused Hindsight/agent/readiness run: 58 passed, 1 pre-existing parser-title failure, 2 default-mode live integration skips; separate opt-in live Cloud run: 2 passed.
- [x] Prompt 3 backend regression run: 316 passed, 1 existing parser-title assertion failure, 2 live Hindsight tests skipped by default.
- [x] Prompt 3 frontend tests: 14 passed; production TypeScript/Vite build passed.
- [ ] Frontend lint fails because ESLint configuration is missing.
- [ ] Dockerfile refers to absent `uv.lock`; Docker was unavailable for a build check.

## Needs implementation

- [ ] Connect simulation endpoints to the simulator and apply event injections.
- [ ] Persist evaluation runs/results and report missing/failed arms rather than empty success-shaped results.
- [ ] Add database migrations and make SQLite path stable across working directories.
- [ ] Correct the deployment lockfile mismatch and stale documentation.
- [ ] Add or configure authentication before any multi-user/production use.

## Needs external configuration

- [x] `GROQ_API_KEY` and Hindsight Cloud settings are present in ignored `backend/.env`.
- [ ] Rotate the Groq key if the earlier local test output is accessible to anyone else.
- [ ] Select an available Groq customer model; `qwen/qwen3-32b` was absent from the model list returned in this audit.
- [ ] Resolve official Band SDK package-index dependency failure.
- [ ] Register Collector and Risk remote agents and configure separate agent IDs/keys plus the shared room ID.
- [ ] Decide whether local Hindsight Docker is needed; Docker is unavailable in this environment.

## Needs testing

- [ ] Decide whether to adjust the existing parser-title assertion/behavior; do not mask it as a Prompt 3 regression.
- [ ] Test Band SDK compatibility, real room posting, inbound commands, and web/Band approval parity.
- [ ] Test Groq structured output, retries, rate limits, and selected customer model.
- [ ] Run frontend tests against the live API rather than mocked `fetch`.
- [ ] Test simulation event effects and repeatability after world integration.
- [ ] Run A/B/C evaluation with all external dependencies available.
- [ ] Add ESLint configuration and run lint; install/run Ruff if backend lint is required.
- [ ] Build and run the Docker stack after fixing missing lockfile and confirming Docker availability.

## Needs final integration

- [ ] Verify the complete path against a running application and external services: seed/import → readiness → draft → owner decision → manual handoff/report → inbound reply/payment → risk/memory update.
- [ ] Verify web and Band use the same approval state and first-decision-wins rule.
- [ ] Verify no action is marked sent before the defined delivery step.
- [ ] Verify Hindsight failures are surfaced without fabricated memories.
- [ ] Verify UI loading, empty, unavailable, and error states against real backend responses.
- [ ] Confirm evaluation output and metrics for Arms A, B, and C.
- [ ] Refresh `README.md`, `docs/AI_PROGRESS.md`, `docs/INTEGRATION_VERIFICATION.md`, API docs, and deployment docs from verified behavior.
