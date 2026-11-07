> **Superseded:** The current checklist is [IMPLEMENTATION_CHECKLIST.md](../IMPLEMENTATION_CHECKLIST.md) at the project root (2026-11-07). This older copy is retained as historical context; use the root checklist for current status.

# Munshi Implementation Checklist

This checklist is based on the implementation and test evidence recorded in [IMPLEMENTATION_STATUS_AUDIT.md](./IMPLEMENTATION_STATUS_AUDIT.md). Groq's minimal completion and Hindsight's direct Cloud retain/recall have now been verified; this does not imply that every application workflow or Band integration is live.

## Already completed and verified

- [x] Twelve SQLModel entities are defined with primary keys, foreign keys, relationships, indexes, enum constraints, and integer-paise amounts.
- [x] SQLite table initialization, foreign-key enforcement, transaction rollback, core constraints, and demo seeding have passing tests.
- [x] Demo business/customer/invoice and supporting records are persisted in the backend SQLite database.
- [x] FastAPI has a liveness endpoint, CORS configuration, route registration, session dependency, and structured validation/error handling.
- [x] The documented API routes are exercised by ASGI/TestClient tests.
- [x] GSTIN format/checksum/state helpers and readiness rules R1–R9 are implemented and tested as code.
- [x] Readiness result precedence and learned requirement code handling are implemented.
- [x] Collector and Risk agent logic has unit-test coverage for drafts, signals, risk thresholds, evidence, and customer scoping.
- [x] A deterministic simulation world, 12 customer profiles, four-customer demo scenario, six-customer evaluation scenario, promises, payment events, and event injection are implemented and covered by tests.
- [x] Evaluation Arms A/B/C, learning/testing separation, metrics, failure reporting, and simulated-results labeling are implemented and tested.
- [x] Seven React screens, a central API client, TanStack Query polling, and loading/error/empty states are implemented.
- [x] Frontend tests pass (13 tests), and the TypeScript/Vite production build passes.
- [x] Backend `.env` loading is rooted at the backend directory, works from another current directory, and preserves process-variable overrides.
- [x] `backend/.env` is ignored by Git; no credentials are included in these documents, and both example files contain empty placeholders. One failed test assertion exposed the Groq key in local output; rotate it if that output is accessible to others.
- [x] Groq accepted a minimal live chat-completion request using `openai/gpt-oss-120b`.
- [x] Hindsight Cloud accepted a synthetic test bank, retain, and recall request using `hindsight-client` 1.2.0; the test bank was left in place.

## Partially completed

- [ ] **Database:** current persistence is SQLite as directed; schema upgrades still have no migration system.
- [ ] **Migrations:** startup creates missing tables but does not migrate an existing database schema.
- [ ] **Supabase demo data:** demo records are hard-coded in the seed module and stored in SQLite; no Supabase seed/migration exists.
- [ ] **Dashboard:** uses database values, but amounts are invoice face values rather than outstanding balances after payments.
- [ ] **Customer management:** listing, detail and patch exist; creation is only available indirectly through import.
- [ ] **Invoice flow:** create, upload and readiness work, but there is no invoice list/detail endpoint or UI.
- [ ] **Readiness R3:** no invoice GSTIN input exists, so invoice-to-customer GSTIN matching is not available in the normal API flow.
- [ ] **Readiness R6:** no PO amount input or extraction exists, so 1% tolerance is skipped in the normal API flow.
- [ ] **E-invoice IRN requirement:** the learned requirement code is recognized, but no IRN field or document type is modeled.
- [ ] **Hindsight:** direct Cloud bank/retain/recall works, but Munshi's wrapper uses the absent `hindsight_client.Client` export and therefore cannot initialize with SDK 1.2.0.
- [ ] **Memory outbox:** processor exists but is not started by application lifecycle.
- [ ] **Collector/Risk:** implementations exist but no runtime trigger calls them from normal API, payment, inbound-message, or daily-loop flows.
- [ ] **Owner approval:** review/edit/reject requests persist, but approved actions are marked SENT before actual external delivery.
- [ ] **WhatsApp:** non-simulator approval can return a prefilled `wa.me` link; it does not send a message.
- [ ] **Explainability:** agent-side evidence exists, but API action explanation and plain-language explain do not retrieve it.
- [ ] **Simulation API:** it controls the clock and acknowledges injections, but is not connected to `SimulationWorld`.
- [ ] **Evaluation:** runner and metrics exist, but no saved result file or `sim_run` records were found; Arm C needs Hindsight.
- [ ] **Frontend/API:** frontend requests are centralized and component-tested with mocks, but live server integration was not verified.
- [ ] **Groq models:** agent model is live; configured customer model `qwen/qwen3-32b` is absent from the current model list (the current Qwen model listed is `qwen/qwen3.8-27b`).
- [ ] **Band:** current official SDK is 8.1.0, but installation could not resolve `band-sdk-core==6.1.1`; no Band credentials are configured and the bridge remains mock logging.
- [ ] **Documents:** upload metadata is in SQLite and file bytes are local; download handler exists but its router is not registered.

## Needs implementation

- [x] Keep the existing local SQLite database for this task; no Supabase configuration or migration was performed.
- [ ] If the database decision changes later, separately plan and authorize any Postgres migration, backend-only settings, migrations, and demo seed.
- [ ] Define and implement safe production authentication before multi-user use.
- [ ] Add persistent document storage suitable for the chosen deployment instead of relying on local upload paths.
- [ ] Add the missing invoice GSTIN and PO amount contract only after confirming the product requirements and source of those values.
- [ ] Define separate action states for approved, dispatched, and actually sent; do not report delivery that did not happen.
- [ ] Persist each draft’s reason and evidence references and return those from the approvals/explanation APIs.
- [ ] Replace the fixed `/api/explain` answer with customer-scoped evidence retrieval and explicit unavailable/insufficient-evidence behavior.
- [ ] Complete the daily loop and wire controlled Collector/Risk triggers to invoice, payment, and inbound-message events.
- [ ] Connect simulator reset/tick/inject routes to the actual deterministic simulation world.
- [ ] Make simulation event injection validate and apply the documented event to the selected simulated customer.
- [ ] Persist evaluation reports and expose complete/missing/failed arm statuses to the frontend.
- [ ] Fix dashboard calculations to subtract payments when reporting outstanding balances.
- [ ] Register the document download endpoint if it is still part of the API contract.
- [ ] Correct invalid checksum demo GSTIN fixtures or replace them with verified fictional test vectors.
- [ ] Decide whether to replace the configured Groq customer model with a currently available model; do not silently change its behavior.
- [ ] Update README, API documentation, database design, progress documentation, and integration status to match verified behavior.

## Needs external configuration

- [x] Groq and Hindsight credentials are configured in the ignored backend `.env`; a test diagnostic echoed the Groq key, so rotate it if that output is accessible to others.
- [x] Verify one Groq request and a Hindsight synthetic bank/retain/recall flow.
- [ ] Adapt Munshi's Hindsight wrapper to the documented `Hindsight` client before relying on app-level memory calls.
- [ ] Resolve the package-index failure for Band SDK 8.1.0's `band-sdk-core==6.1.1` dependency.
- [ ] Create each Band remote agent, then configure its own agent ID and API key plus the shared room ID. Band Desktop alone does not run Munshi's custom backend agents.
- [ ] Configure a real Band inbound callback/webhook only after adding and verifying the matching backend route.
- [ ] Decide whether a real WhatsApp provider is in scope. A prefilled link alone is not delivery integration.
- [ ] Install Docker/enable Docker Compose if local Hindsight and container-based development remain part of the workflow.

## Needs testing

- [ ] Resolve the five failing Groq tests that patch a missing module-level `Groq` symbol.
- [ ] Resolve the playbook parser title expectation mismatch.
- [ ] Register ESLint configuration or remove lint from the expected workflow; `npm run lint` currently fails because configuration is absent.
- [ ] Align VS Code/Pylance with the backend Python 3.11 environment; selected Python 3.13 did not resolve backend dependencies.
- [ ] Start the backend with the intended runtime and verify `/health` over HTTP.
- [ ] Run frontend tests against the live backend rather than only mocked `fetch`.
- [ ] Test all API validation, error, transaction, and database behaviors against the retained SQLite schema.
- [ ] Verify GSTIN examples against independently known test cases; document the limits of checksum-only validation.
- [ ] Run Hindsight integration tests for timestamps, customer isolation, contradiction handling, evidence references, and retries.
- [ ] Verify the outbox starts, stops, respects retry schedules, and marks successfully retained events.
- [ ] Verify Groq structured output, invalid output fallback, rate limits, and the approved customer-model selection with credentials.
- [ ] Verify actual Band room posting and a Band-originated approval reaches the same backend action endpoint.
- [ ] Verify that approval, external handoff, and actual send states cannot be confused.
- [ ] Verify simulation API event effects in the database/world and repeatability for the same seed.
- [ ] Run the full A/B/C evaluation with a reachable Hindsight service and retain all failures/missing metrics in results.

## Needs final integration

- [x] Keep current architecture on SQLite, as requested; no Supabase configuration or migration.
- [ ] Ensure frontend only uses the documented API contract and all screens show honest memory/service state.
- [ ] Ensure the API, agents, memory outbox, simulation, and evaluation use the same persistent database configuration.
- [ ] Ensure Collector drafts can be generated through a real backend trigger and remain owner-approved.
- [ ] Ensure Risk assessments are triggered on the documented events and persist customer-scoped evidence.
- [ ] Ensure Band failure leaves web approvals and risk alerts usable.
- [ ] Ensure no message is marked SENT until delivery is actually confirmed; simulator behavior must be explicitly simulated.
- [ ] Run a full end-to-end demo with synthetic records only: seed/import → readiness → reminder draft → owner approval → actual handoff → inbound reply/payment → risk/memory update → simulation/evaluation.
- [ ] Update the audit checklist and status report after the integration tests pass.
