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

**Direct Cloud result: successful. Application wrapper result: incompatible.**

- The configured base URL and key were present. Neither value is reproduced here.
- A previous direct check installed `hindsight-client` 1.2.0 in an isolated verification environment and used its documented `Hindsight` client. The service returned API version 1.1.0.
- Created synthetic bank `munshi-config-check-a152a59c20`, retained a non-customer test fact, and recalled one result. The test bank was left in place.
- The package remains absent from the actual backend `.venv` (`Python 3.11.9`). An earlier install attempt stalled without output for more than six minutes. During Prompt 2, two additional bounded attempts—using the configured default index and then explicit `https://pypi.org/simple`—each stalled without output for 60 seconds and were stopped. Separate HTTPS checks to `pypi.org` and `files.pythonhosted.org` returned HTTP 200; no pip index override was found. Pip emitted no diagnostic, so the exact cause is unknown. No dependency manifest or lockfile was changed.
- The application's [client.py](../backend/munshi/memory/client.py) uses `hindsight_client.Client`. The installed SDK exports `Hindsight`, not `Client`; the application wrapper therefore reports unavailable even though direct Cloud requests work.
- Application memory retention/retrieval, timestamp behavior, retries, and agent use of retrieved memories are not verified. The five existing Hindsight integration tests are skipped unconditionally. Update the existing wrapper to the documented SDK before claiming application-level Hindsight integration.
- Prompt 2's focused backend run collected 62 tests: 56 passed, one failed, and five integration tests skipped. The unrelated existing failure was `tests/test_queries.py::TestParsePlaybook.test_parse_playbook_json` (expected title `Payment Collection`, actual `Payment Collection Playbook`). No code was changed because SDK installation remained the explicit stop condition.

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
| Hindsight SDK | 1.2.0 in prior isolated verification environment; absent from active backend `.venv`; install attempt stalled; previous direct retain/recall passed |
| Band SDK | Install blocked by unavailable `band-sdk-core==6.1.1` |
| Credential loading from a different working directory | Passed; status checks only, no values printed |
| `.env` Git ignore check | Passed for `backend/.env` |
| Full backend suite | 328 collected; 317 passed, 6 failed, 5 skipped, 9 warnings |
| Frontend tests | 13 passed |
| Frontend production build | Passed |
| Frontend lint | Failed because ESLint configuration is missing |
| Backend startup | Temporary Uvicorn server started; `/health` returned HTTP 200 |
| Focused earlier configuration tests | 8 Groq initialization/model tests and 21 Band tests passed |
| Prompt 2 focused backend tests | 56 passed, 1 unrelated playbook-title failure, 5 Hindsight integration tests skipped unconditionally |
| PyPI shell connectivity | `pypi.org` index and `files.pythonhosted.org` distribution host returned HTTP 200; no pip index override found; pip installation still stalled without diagnostics |

Failure details and the feature/API audit are in the root [implementation audit](../IMPLEMENTATION_STATUS_AUDIT.md).

## Next implementation task

The next action for Prompt 2 is to resolve why pip stalls in `backend/.venv` despite successful HTTPS checks, then install/verify the official `hindsight-client` there. A single diagnostic retry can use `backend\.venv\Scripts\python.exe -m pip install -v "hindsight-client==1.2.0"` after checking the machine's proxy, certificate, and package-source policy; do not loop retries. Then repair and test the existing adapter/outbox. After that, resolve the official Band SDK package-index dependency and verify a live agent connection. Separately decide whether to update the unsupported configured Groq customer model.
