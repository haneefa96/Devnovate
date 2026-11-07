# AGENTS.md

This file is for AI coding assistants. See `README.md` for the project overview.

---

## Quick start for AI assistants

1. Read this file and `DEVELOPMENT_RULES.md`
2. Read the module's entry in `docs/MODULE_CONTRACTS.md`
3. Check `docs/EXTERNAL_INTEGRATIONS.md` for Hindsight, Band, Groq integration details
4. Check `docs/INTEGRATION_VERIFICATION.md` for Day 1–2 verification tasks

---

## Module ownership (from the project document)

| Owner | Folders | Responsibility |
|-------|---------|----------------|
| P1 memory lead | `backend/munshi/memory/`, `backend/munshi/agents/` | Hindsight integration, policy interface, Collector, Risk |
| P2 simulator + eval | `backend/sim/`, `backend/eval/` | World, personas, scenarios, arms A/B/C, metrics, report |
| P3 backend + Band | `backend/munshi/db/`, `api/`, `checks/`, `band/`, `services/`, `llm/`, `config.py`, `main.py` | Core backend, DB, LLM, API, Band bridge |
| P4 frontend + story | `frontend/`, `docs/`, README | React app, documentation, demo script, video |

---

## Technology stack for hackathon

| Technology | Purpose | Required | Integration boundary |
|------------|---------|----------|---------------------|
| Hindsight | Long-term customer memory | **Mandatory** | `backend/munshi/memory/` |
| Band AI | Multi-agent collaboration | **Mandatory** | `backend/munshi/band/` |
| Groq | LLM inference | Recommended | `backend/munshi/llm/` |

---

## Hindsight integration

**Only** `backend/munshi/memory/` may import and use the Hindsight SDK.

### Core modules

| Module | Purpose |
|--------|---------|
| `memory/client.py` | Hindsight SDK client, bank initialization, configuration |
| `memory/bank_setup.py` | Bank naming, directives, missions, disposition |
| `memory/events.py` | Event tagging, retain templates, writing rules |
| `memory/queries.py` | Reflect, recall, memory types |
| `memory/parsing.py` | LLM output parsing, JSON schema validation |
| `memory/outbox.py` | Retry mechanism for failed retains |

### Day 1–2 verification

| Check | Status | Notes |
|-------|--------|-------|
| Timestamp honoured | | Run `docs/INTEGRATION_VERIFICATION.md` test |
| First-person → experience facts | | |
| Observations change on contradiction | | |
| Mental models auto-refresh | | |
| Retain/reflect latency | | |

See `docs/INTEGRATION_VERIFICATION.md` for detailed tests.

### Bank naming

| Bank | Purpose |
|------|---------|
| `munshi-<business-slug>` | Production/demo |
| `eval-<run-id>-C-s<seed>` | Evaluation runs |

---

## Band AI integration

**Only** `backend/munshi/band/` may import and use the Band SDK.

### Core modules

| Module | Purpose |
|--------|---------|
| `band/run_agents.py` | External Agent setup (Collector, Risk), SDK initialization |
| `band/bridge.py` | Backend events → Band room posts |
| `band/commands.py` | Regex patterns for approve A-n, edit A-n, reject A-n, @Risk handoff |

### External Agents

| Agent | Purpose | SDK class |
|-------|---------|-----------|
| Collector | Posts drafts for approval | `Agent` or `ExternalAgent` |
| Risk | Posts risk alerts | `Agent` or `ExternalAgent` |

### Message formats (regex parsed)

| Format | Example |
|--------|---------|
| Collector draft | `[DRAFT A-231] To Priya (Reddy Traders), WhatsApp, today 10:30. <message>. Why: <evidence>. Reply: approve A-231 / edit A-231: <text> / reject A-231` |
| Risk alert | `[RISK] Reddy Traders: Watch → High. Signals: ... Suggest: ... @owner` |
| Collector→Risk handoff | `@Risk reply from Rahul mentions cash-flow trouble on INV-1060, please assess` |

### Fallback

If Band is unavailable, web app (approvals inbox, risk alerts) provides identical functionality.

---

## Groq LLM integration

**Only** `backend/munshi/llm/` may call Groq API.

### Core modules

| Module | Purpose |
|--------|---------|
| `llm/groq_client.py` | Groq SDK client, model selection, retry logic |
| `llm/cache.py` | Disk cache, rate limit handling |
| `llm/json_utils.py` | JSON schema validation, function calling wrappers |

### Model identifiers

| Task | Model ID |
|------|----------|
| Agents, drafting | `openai/gpt-oss-120b` |
| Simulated customers | `qwen/qwen3-32b` |

### Error handling

| Error | Handling |
|-------|----------|
| Rate limit | Exponential backoff, log and retry |
| Malformed response | Log, return empty, continue |
| Function-calling error | Per-model fallback |

---

## Module contracts

See `docs/MODULE_CONTRACTS.md` for detailed contracts including:

- **Boundary**: Only files allowed in each module
- **Interfaces**: Inputs/outputs (Python types, JSON schemas)
- **Dependencies**: What each module imports
- **Environment variables**: Required config
- **Checklist**: Verification items to mark complete

---

## Integration order

1. **Day 1–2**: Hindsight verification (timestamps, experience facts, mental models)
2. **Day 2**: Band verification (External Agent setup, message formats, fallback)
3. **Day 3**: Groq verification (structured outputs, function calling, rate limits)
4. **Day 4+**: Integration with backend modules

---

## Rules for AI assistants

1. Read `DEVELOPMENT_RULES.md` and `docs/MODULE_CONTRACTS.md` before implementing
2. State which module you are implementing and list the files you will touch
3. Resolve every `# VERIFY` marker against the installed SDK version, record in `docs/INTEGRATION_VERIFICATION.md`
4. Stop after the module checklist passes; do not start the next module

---

## Unresolved questions

| Question | Source |
|----------|--------|
| Exact Hindsight SDK version | Pin on Day 1 |
| Exact Band SDK class names | Check installed version against docs |
| Exact Groq function-calling support per model | Verify on Day 2–3 |

---

## Getting help

- Hindsight docs: [hindsight.vectorize.io/docs](https://hindsight.vectorize.io/)
- Band docs: [band.ai/docs](https://band.ai/docs)
- Groq docs: [console.groq.com/docs](https://console.groq.com/docs)
