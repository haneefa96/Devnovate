# Munshi Implementation Checklist

Current evidence and status details are in [IMPLEMENTATION_STATUS_AUDIT.md](./IMPLEMENTATION_STATUS_AUDIT.md). This checklist distinguishes tested behavior from source-code presence.

## Already completed and verified

- [x] Twelve SQLModel tables, relations, integer-paise amounts, indexes, and core constraints.
- [x] SQLite initialization, sessions, transaction rollback, and demo seed tests.
- [x] Persistent fictional demo records in `backend/munshi.db`.
- [x] FastAPI health endpoint, route registration, CORS, validation/error envelopes, and DB injection tests.
- [x] GSTIN helper and R1-R9 readiness unit tests (not all fields are available through the normal API).
- [x] Collector/Risk logic and policy unit tests (not runtime-triggered).
- [x] Deterministic simulation world and evaluation code/unit tests (not connected to the simulation HTTP routes).
- [x] Seven React screens and centralized API client.
- [x] Backend startup and `GET /health` HTTP 200 during this audit.
- [x] Frontend tests: 13 passed.
- [x] Frontend production build: passed.
- [x] Groq credentials load in backend settings; minimal live request succeeded with `openai/gpt-oss-120b`.
- [x] Direct Hindsight Cloud synthetic bank/retain/recall was previously verified with SDK 1.2.0 in a separate verification environment.
- [x] `backend/.env` is ignored; templates contain empty secret placeholders; no frontend `.env` file was found.
- [x] Keep local SQLite for this stage; no Supabase configuration or migration.

## Partially completed

- [ ] Dashboard and customer totals should use outstanding, not invoice face, amounts.
- [ ] Customer page reads ledger history but returns no learned playbook or beliefs.
- [ ] Invoice/readiness form lacks invoice GSTIN and PO amount.
- [ ] Readiness R3/R6 cannot be fully exercised through normal API input; GSTIN validation is not registry verification.
- [ ] Learned requirements invoke an incompatible Hindsight adapter; IRN has no modeled field/document type.
- [ ] Owner approval persists but marks the action SENT without actual delivery.
- [ ] WhatsApp support generates a prefilled link only; no automatic sending or simulator delivery.
- [ ] Action explanations and plain-language explain return generic/empty evidence.
- [ ] Simulation HTTP tick/inject are not connected to the deterministic world.
- [ ] Evaluation runner exists but there are no stored `sim_run` results.
- [ ] Backend test suite has 6 failures; details are in the audit.
- [ ] Frontend lint fails because ESLint configuration is missing.
- [ ] Dockerfile refers to absent `uv.lock`; Docker was unavailable for a build check.

## Needs implementation

- [ ] Make Hindsight application calls use the actual SDK API and propagate unavailable/error state honestly.
- [ ] Reconcile and idempotently process memory outbox events; respect retry times and wire startup/shutdown.
- [ ] Wire daily Collector/Risk behavior to backend events while preserving customer isolation and owner approval.
- [ ] Persist and return evidence for drafts, alerts, and explanations.
- [ ] Separate approval, handoff, and confirmed delivery states.
- [ ] Connect simulation endpoints to the simulator and apply event injections.
- [ ] Persist evaluation runs/results and report missing/failed arms rather than empty success-shaped results.
- [ ] Correct financial summary calculations to subtract payments.
- [ ] Resolve the invoice GSTIN, PO amount, and IRN data contract.
- [ ] Add database migrations and make SQLite path stable across working directories.
- [ ] Correct the deployment lockfile mismatch and stale documentation.
- [ ] Add or configure authentication before any multi-user/production use.

## Needs external configuration

- [x] `GROQ_API_KEY` and Hindsight Cloud settings are present in ignored `backend/.env`.
- [ ] Rotate the Groq key if the earlier local test output is accessible to anyone else.
- [ ] Select an available Groq customer model; `qwen/qwen3-32b` was absent from the model list returned in this audit.
- [ ] Install the Hindsight SDK in the actual backend environment; the earlier attempt and two bounded Prompt 2 attempts stalled without output. PyPI and its package-file host responded with HTTP 200, no pip index override was found, and the exact pip stall cause remains unknown.
- [ ] Resolve official Band SDK package-index dependency failure.
- [ ] Register Collector and Risk remote agents and configure separate agent IDs/keys plus the shared room ID.
- [ ] Decide whether local Hindsight Docker is needed; Docker is unavailable in this environment.

## Needs testing

- [ ] Resolve five Groq mock-patching failures and the playbook parser title mismatch.
- [ ] Re-run the focused Prompt 2 tests after resolving SDK installation: the current run had 56 passed, one unrelated playbook-title assertion failure, and five Hindsight integration tests skipped unconditionally.
- [ ] Test Hindsight wrapper operations and customer isolation against Cloud with synthetic data.
- [ ] Test outbox success, retry schedule, idempotency, and FastAPI lifecycle.
- [ ] Test Band SDK compatibility, real room posting, inbound commands, and web/Band approval parity.
- [ ] Test Groq structured output, retries, rate limits, and selected customer model.
- [ ] Run frontend tests against the live API rather than mocked `fetch`.
- [ ] Test invoice readiness with complete invoice GSTIN and PO amount contracts.
- [ ] Test simulation endpoint effects and repeatability.
- [ ] Run A/B/C evaluation with all external dependencies available.
- [ ] Add ESLint configuration and run lint; install/run Ruff if backend lint is required.
- [ ] Build and run the Docker stack after fixing missing lockfile and confirming Docker availability.

## Needs final integration

- [ ] Verify the complete path: seed/import → readiness → draft → owner decision → actual handoff → inbound reply/payment → risk/memory update.
- [ ] Verify web and Band use the same approval state and first-decision-wins rule.
- [ ] Verify no action is marked sent before the defined delivery step.
- [ ] Verify Hindsight failures are surfaced without fabricated memories.
- [ ] Verify UI loading, empty, unavailable, and error states against real backend responses.
- [ ] Confirm evaluation output and metrics for Arms A, B, and C.
- [ ] Refresh `README.md`, `docs/AI_PROGRESS.md`, `docs/INTEGRATION_VERIFICATION.md`, API docs, and deployment docs from verified behavior.
