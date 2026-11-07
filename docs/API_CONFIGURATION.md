# API Credential Configuration and Verification

## Scope

This update verifies the existing Groq, Hindsight Cloud, and Band configuration without rebuilding their application features. The database remains local SQLite as instructed; no Supabase settings, migration, or schema changes were made.

The current full-project findings are in the root [implementation audit](../IMPLEMENTATION_STATUS_AUDIT.md) and [checklist](../IMPLEMENTATION_CHECKLIST.md).

No credential values are included in this document. A failed test assertion emitted the configured Groq key in local test output; treat it as exposed if that output is accessible to anyone else and rotate it in the Groq console. The tests now isolate settings with synthetic values.

## Backend environment loading

The backend reads `backend/.env` from a path resolved relative to `backend/munshi/config.py`, so startup does not depend on the shell's working directory. Values already present in the process environment take precedence over `.env`.

`backend/.env` is ignored by `backend/.gitignore`. The root `.env.example` directs developers to `backend/.env.example`; the backend template has empty secret values. Do not copy backend credentials to `frontend/.env` or any `VITE_*` variable.

### Environment variables used by the backend

| Variable | Purpose | Current configuration |
|---|---|---|
| `GROQ_API_KEY` | Groq authentication | Present; value withheld |
| `GROQ_BASE_URL` | Groq SDK API root | `https://api.groq.com` |
| `GROQ_AGENT_MODEL` | Agent/drafting model | `openai/gpt-oss-120b` |
| `GROQ_CUSTOMER_MODEL` | Customer simulation model | `qwen/qwen3-32b` |
| `HINDSIGHT_API_KEY` | Hindsight Cloud authentication | Present; value withheld |
| `HINDSIGHT_BASE_URL` | Hindsight Cloud API URL | Present; value withheld |
| `HINDSIGHT_LOCAL_URL` | Optional local Hindsight URL | Empty/unset |
| `HINDSIGHT_TIMEOUT` | Hindsight request timeout in seconds | Defaults to `30` |
| `BAND_ROOM_ID` | Shared Band room | Missing |
| `BAND_COLLECTOR_AGENT_ID` | Registered Collector remote-agent ID | Missing |
| `BAND_COLLECTOR_API_KEY` | Collector agent-specific API key | Missing |
| `BAND_RISK_AGENT_ID` | Registered Risk remote-agent ID | Missing |
| `BAND_RISK_API_KEY` | Risk agent-specific API key | Missing |
| `BAND_API_KEY`, `BAND_AGENT_ID` | Legacy bridge configuration | Missing; bridge does not send messages |
| `BAND_WEBHOOK_URL` | Legacy setting | Defined in configuration but unused; no matching webhook route exists |
| `DATABASE_URL` | SQLModel database | Remains the local SQLite URL |

Band assigns an API key to each registered remote agent. The SDK authenticates using that agent key (the REST API documents the `X-API-Key` header). Configure separate IDs and keys for Collector and Risk; a shared account key is not a substitute for both agent credentials.

## Groq

**Connection result: successful.**

- The installed Groq Python SDK is version 1.7.0.
- A minimal live chat-completion request succeeded using `openai/gpt-oss-120b`.
- The current Groq model list includes `openai/gpt-oss-120b` and `qwen/qwen3.8-27b`. It does not include the configured customer model `qwen/qwen3-32b`.
- No model setting was silently changed. Confirm whether the customer-model configuration should be updated to a currently listed model before relying on simulation behavior.
- An initial request returned HTTP 404 because the configured Groq SDK base URL included `/openai/v1`, which the SDK appended again. The backend default and example now use the SDK's API root, `https://api.groq.com`; the subsequent completion succeeded.
- Structured-output behavior, rate limits, retries, and the customer model remain unverified.

## Hindsight Cloud

**Application wrapper result: verified against Cloud with synthetic data.**

- `hindsight-client==1.2.0` is installed in the active backend `.venv` (Python 3.11.9). The installed package and official [Python SDK documentation](https://hindsight.vectorize.io/sdks/python) confirm the `Hindsight` client, async methods, and supported response fields.
- Munshi's existing adapter uses the configured service URL, API key, and timeout. The wrapper's live Cloud tests verified bank access/creation, retain, recall, reflect, timestamp/metadata handling, customer-tag isolation, and separation between business banks.
- Two opt-in live tests passed using synthetic data only. They are enabled with `MUNSHI_RUN_HINDSIGHT_INTEGRATION=1`; routine automated tests use mocks and local SQLite.
- The FastAPI lifespan starts and stops the memory outbox worker. Local/mocked tests cover bounded due-time retries, failure status, duplicate processing protection, and recording success only after confirmed retention. Its overlap lock is process-local, not distributed across multiple service processes.
- Hindsight outages are surfaced as unavailable; readiness marks memory pending, and Collector/Risk fall back to ledger evidence rather than treating an outage as an empty customer history.
- Outbox retention excludes known unsent-draft kinds and redacts common formatted phone numbers, labeled account numbers, IFSC codes, and labeled UPI/VPA identifiers from content before retention.
- SDK recall entries do not always populate `occurred_start`; the adapter maps timestamp fields available in responses. Metadata and an available timestamp were observed in the live test.
- Live integration tests leave their clearly synthetic banks/facts in the configured Cloud service.

Official references: [Python client](https://hindsight.vectorize.io/sdks/python), [Hindsight quick start](https://hindsight.vectorize.io/developer/api/quickstart), [API reference](https://hindsight.vectorize.io/api-reference).

## Band AI

**Connection result: blocked; no Band credentials are configured.**

- Current official documentation describes `band-sdk` 8.1.0. The Python SDK authenticates as a registered agent; the quickstart stores an agent ID and API key for each agent and connects the agent process to Band.
- Installing `band-sdk==8.1.0` failed because the configured package index does not provide its required `band-sdk-core==6.1.1`. The install was not bypassed with an incomplete or unofficial dependency set.
- The current `.env.example` and agent manager now describe separate Collector and Risk agent credentials. No Band values were added.
- Band Desktop runs supported local coding agents, but is not a connection for Munshi's custom backend agents. Munshi needs its own registered remote agents and a compatible SDK installation.
- The existing `BandBridge` only logs “Would post…” and does not send room messages. FastAPI does not start the agent manager, and there is no `/api/band/webhook` endpoint. Adding credentials alone will not make this integration work.

Official references: [Band Python SDK quickstart](https://docs.band.ai/quickstart), [SDK reference](https://docs.band.ai/reference/sdk), [agent and configuration](https://docs.band.ai/reference/sdk/agent-and-config).

## Dependency and test results

| Check | Result |
|---|---|
| Python runtime | 3.11.9 |
| Groq SDK | 1.7.0; live minimal request passed |
| Hindsight SDK | 1.2.0 installed in active backend `.venv` (Python 3.11.9); Munshi wrapper integration verified |
| Band SDK | Install blocked by unavailable `band-sdk-core==6.1.1` |
| Credential loading from a different working directory | Passed; status checks only, no values printed |
| `.env` Git ignore check | Passed for `backend/.env` |
| Full backend suite | 314 collected; 306 passed, 6 known baseline failures, 2 skipped |
| Frontend tests | 13 passed |
| Frontend production build | Passed |
| Frontend lint | Failed because ESLint configuration is missing |
| Backend startup | Temporary Uvicorn server started; `/health` returned HTTP 200 |
| Focused earlier configuration tests | 8 Groq initialization/model tests and 21 Band tests passed |
| Prompt 2 focused Hindsight/agent/readiness tests | 58 passed, 1 known unrelated parser-title failure, 2 live tests skipped in default mode |
| Prompt 2 live Hindsight Cloud tests | 2 passed using synthetic data |

Failure details and the feature/API audit are in the root [implementation audit](../IMPLEMENTATION_STATUS_AUDIT.md).

## Remaining integration work

Prompt 2's Hindsight adapter/outbox scope is complete and verified. Do not reinstall the SDK or rebuild those modules. The next separate integration work is resolving the official Band SDK package-index dependency, configuring registered Collector/Risk agent credentials, and verifying real room messaging. Separately decide whether to update the configured Groq customer model, which was absent from the live model list.
