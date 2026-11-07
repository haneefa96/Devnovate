# ARCHITECTURE

## 1. System architecture
One FastAPI backend sits between three **surfaces** (React web app, Band room "AR Desk", simulator) and three **services** (SQLite, Hindsight, Groq). Agents are backend modules, not separate services.

```
 Web app (React) ──REST──┐
 Band room (AR Desk) ─SDK─┼──► FastAPI backend ──records──► SQLite  (facts)
 Simulator ────events────┘     │  readiness · collector · risk · daily loop
                               ├──retain/recall/reflect──► Hindsight (knowledge)
                               └──prompts (cached)───────► Groq LLMs
```

### 1.1 Technology stack for hackathon

| Technology | Purpose | Required | Integration boundary |
|------------|---------|----------|---------------------|
| **Hindsight** | Long-term customer memory: store historical events, retain payment behaviour, retrieve learned patterns, remember communication preferences and document requirements | **Mandatory** | `backend/munshi/memory/` only |
| **Band AI** | Multi-agent collaboration: Collector and Risk agents work with owner in shared Band room | **Mandatory** | `backend/munshi/band/` only |
| **Groq** | LLM inference: gpt-oss-120b for agents, qwen3-32b for simulated customers | Recommended | `backend/munshi/llm/` only |

### 1.2 Technology-specific architecture boundaries

#### Hindsight integration
- **Single responsibility**: Memory store only. Hindsight never decides amounts, dates, or statuses.
- **Integration boundary**: Only `backend/munshi/memory/` may import and use the Hindsight SDK.
- **Core modules**:
  - `memory/client.py` — Hindsight SDK client, bank initialization, configuration
  - `memory/bank_setup.py` — bank naming, directives, missions, disposition
  - `memory/events.py` — event tagging, retain templates, writing rules
  - `memory/queries.py` — reflect, recall, memory types
  - `memory/parsing.py` — LLM output parsing, JSON validation
  - `memory/outbox.py` — retry mechanism for failed retains
- **Data model**: SQLite remains source of truth for financial and transactional data. Hindsight stores:
  - Experience facts (Munshi's actions)
  - Observations (payment patterns, document requirements)
  - Mental models (customer playbooks)
  - Evidence links (based_on)
- **Never**:
  - Store phone numbers, bank account numbers, or unsent drafts
  - Decide on invoice validity or payment receipt
  - Replace or modify SQLite data

#### Band AI integration
- **Single responsibility**: Multi-agent collaboration surface. Band is **not** the agent logic.
- **Desktop vs integration**:
  - **Desktop application**: Downloaded and used by owner for collaborative work
  - **Programmatic integration**: Backend connects agents as External Agents via SDK
- **Integration boundary**: Only `backend/munshi/band/` may use the `band-sdk`.
- **Core modules**:
  - `band/run_agents.py` — External Agent setup (Collector, Risk), SDK initialization
  - `band/bridge.py` — backend events → Band room posts
  - `band/commands.py` — regex patterns for inbound messages (approve A-n, edit A-n, reject A-n, @Risk handoff)
- **Message formats** (regex parsed, **not** LLM):
  - Collector: `[DRAFT A-231] To Priya (Reddy Traders), WhatsApp, today 10:30. <message>. Why: <evidence>. Reply: approve A-231 / edit A-231: <text> / reject A-231`
  - Risk: `[RISK] Reddy Traders: Watch → High. Signals: … Suggest: … @owner`
  - Handoff: `@Risk reply from Rahul mentions cash-flow trouble on INV-1060, please assess`
  - Owner questions: plain text → `POST /api/explain`
- **Fallback**: If Band is unavailable, web app provides identical functionality (approvals inbox, risk alerts)
- **Never**:
  - Replace owner approval for sending messages
  - Implement own agent logic (only SDK glue)
  - Store agent state outside backend

#### Groq LLM integration
- **Single responsibility**: LLM inference with structured outputs.
- **Integration boundary**: Only `backend/munshi/llm/` may call Groq API.
- **Core modules**:
  - `llm/groq_client.py` — Groq SDK client, model selection, retry logic
  - `llm/cache.py` — disk cache, rate limit handling
  - `llm/json_utils.py` — JSON schema validation, function calling wrappers
- **Model identifiers** (configurable via environment):
  - `openai/gpt-oss-120b` — Agents, drafting, policy reasoning
  - `qwen/qwen3-32b` — Simulated customers
- **Requirements**:
  - Configurable model identifiers per task
  - Environment-based credentials (no hard-coded keys)
  - Structured JSON outputs with schema validation
  - Function-calling error handling per model capability
  - Malformed response handling (fallback, logging)
  - Rate-limit and timeout handling with exponential backoff
  - Safe retry logic (idempotent operations only)
- **Never**:
  - Hard-code API keys
  - Assume all models support identical function calling
  - Use LLM for amounts, dates, or status decisions

### Source-of-truth rules (never violate)
| Who | Decides |
|---|---|
| **SQLite** | amounts, dates, invoice status, attached documents, what was approved/sent |
| **Hindsight** | why customers pay or don't, who to contact, what was required, what changed, how risky |
| **Code** | rule checks, days late, missed runs, risk level from signals, business-hours limits |
| **LLM** | message wording, JSON plans, summaries — always from evidence passed in |

Hindsight is never asked for a number the system must act on. The LLM never decides if an amount, GSTIN or PO is correct.

## 2. Modules
| Module | Path | Responsibility | Depends on |
|---|---|---|---|
| Config | `munshi/config.py` | env settings, Hindsight/Band/Groq credentials | — |
| DB | `munshi/db/` | 12 SQLModel tables, session, seed | config |
| LLM | `munshi/llm/` | **only** place calling Groq API; Groq client, disk cache, JSON utils | config |
| Memory | `munshi/memory/` | **only** place importing `hindsight_client`; bank setup, retain templates, queries, parsing, outbox | config, db |
| Checks | `munshi/checks/` | GSTIN, rules R1–R9, readiness combiner | db, memory findings passed in |
| Agents | `munshi/agents/` | Policy interface, Collector, Risk, drafting, prompts | memory, llm, db |
| Services | `munshi/services/` | clock, daily loop, WhatsApp link | agents, db |
| API | `munshi/api/` | HTTP routers (includes Band command handler) | all above |
| Band | `munshi/band/` | run agents (External Agent setup), bridge (backend→room), command parsing | API (HTTP) only |
| Simulator | `sim/` | seeded world, personas, scenarios | api (HTTP) or services |
| Evaluation | `eval/` | arms A/B/C, metrics, report | agents.policy, sim |
| Frontend | `frontend/` | 7 pages, 9 components | API (HTTP) only |

### Integration rules
- **Hindsight**: Only `memory/client.py` imports `hindsight_client`. Never in `agents/`, `checks/`, `api/`.
- **Groq**: Only `llm/groq_client.py` calls Groq API. Never in `agents/`, `checks/`, `api/`.
- **Band SDK**: Only `band/run_agents.py` uses `band-sdk`. Never in `agents/`, `checks/`, `api/`.
- **Shared contracts**: App and evaluation share `agents/policy.py`. Prompts live in `agents/prompts/*.md`.
- **Data order**: SQLite first → retain in Hindsight → post to Band. If any step fails, state machine must roll back or retry.


## 3. Component interaction and data flow (one follow-up)
1. Daily loop finds INV-1042 two days before the customer's usual payment run.
2. Collector calls `reflect` on the customer's memory → JSON plan + evidence ids.
3. Code clamps time to 09:00–19:00 IST and checks the reminder cap (max 2/week); LLM writes wording; amounts/dates are injected by code.
4. Draft saved in SQLite (`DRAFTED`), posted to Band room and web inbox.
5. Owner approves (either surface; first decision wins). Message is "delivered" (simulated customer, or WhatsApp link).
6. Only then the action is retained in Hindsight as an experience fact.
7. Customer reply and payment are stored in SQLite and retained in Hindsight (linked to the reminder).
8. Hindsight consolidates; playbook and beliefs update before the next decision (UI shows "memory updating" while pending).

**Write order for every state-changing endpoint:** SQLite first → retain in Hindsight. If retain fails, `memory_event.retained_at` stays NULL and a background task retries (outbox).

## 4. Hindsight memory design

### 4.1 Purpose and responsibilities
Hindsight is the **long-term memory** system. It stores:
- Historical events (experience facts)
- Customer payment patterns (observations with trends)
- Customer playbooks (mental models)
- Evidence links (based_on for explainability)
- Customer document requirements
- Communication preferences (contact person, phone numbers stay in SQLite)

**Hindsight never**:
- Stores phone numbers, bank account numbers, or unsent drafts
- Decides invoice validity or payment receipt (comes from SQLite)
- Replaces SQLite as the source of truth

### 4.2 Integration boundary
Only `backend/munshi/memory/` may import and use the Hindsight SDK.

### 4.3 Core modules
| Module | Purpose |
|--------|---------|
| `memory/client.py` | Hindsight SDK client, bank initialization, configuration |
| `memory/bank_setup.py` | Bank naming (`munshi-<slug>`, `eval-<run>-C-s<seed>`), directives, missions, disposition |
| `memory/events.py` | Event tagging (`customer:<id>`, `kind:<event>`), retain templates, writing rules |
| `memory/queries.py` | Reflect, recall, memory types (experience facts, observations, mental models) |
| `memory/parsing.py` | LLM output parsing, JSON schema validation, fallback handling |
| `memory/outbox.py` | Retry mechanism for failed retains (memory_event.retained_at IS NULL) |

### 4.4 Bank naming and configuration
| Bank | Purpose | Tags |
|------|---------|------|
| `munshi-<business-slug>` | Production/demo | `customer:<id>`, `kind:<event>` |
| `eval-<run-id>-C-s<seed>` | Evaluation | `arm:<A|B|C>`, `seed:<seed>`, `run:<run-id>` |

**Bank configuration** (exact text from PDF):
- **Retain mission**: Extract facts that affect when/how supplier gets paid: payment-run days, who approves/releases payments, required invoice details/documents, hold reasons, promises and whether kept, contact changes, signs of financial stress.
- **Observations mission**: Consolidate durable patterns per customer: payment timing, which follow-ups work or fail, document requirements, changes in behaviour. Note when newer evidence contradicts older pattern.
- **Reflect mission**: You are Munshi, the accounts clerk for {business}. Help owner get paid on time without harming customer relationships. Base every recommendation on evidence. Say when evidence is thin or stale.
- **Disposition**: Skepticism 4, literalism 3, empathy 3.
- **Directives** (6 global, untagged):
  1. Never threaten legal action or use coercive language. Escalation needs owner approval.
  2. Never recommend contacting a customer outside 09:00–19:00 IST.
  3. Never reveal one customer's information to another.
  4. Never state that an invoice is valid or that a payment was received; those come from the ledger.
  5. Cite the evidence behind every recommendation. If none, say so.
  6. Mention MSME payment-term rules only when business marked as registered.

### 4.5 What gets retained (one event per call)
| Event | Example content | Expected fact type |
|-------|-----------------|-------------------|
| Invoice sent | On 2026-03-01 I sent invoice INV-1042 for ₹48,200 to Priya at Reddy Traders, with PO 4471 and signed challan attached. | Experience |
| Invoice held | On 2026-02-12 Reddy Traders held INV-1037 because the PO number was missing. | World |
| Reminder sent | On 2026-03-03 I reminded Priya on WhatsApp about INV-1042, two days before their usual payment run. | Experience |
| Customer reply | On 2026-03-03 Priya (accounts, Reddy Traders) replied: "Payment run is on the 5th, will release with this batch." | World |
| Promise to pay | On 2026-04-21 Rahul (Reddy Traders) promised payment of INV-1060 by 2026-04-28. | World |
| Payment received | On 2026-03-05 Reddy Traders paid INV-1042 in full, 4 days late and 2 days after my reminder to Priya. | World, linked to reminder |
| Contact change | On 2026-04-02 Priya said Rahul now handles payables at Reddy Traders. | World |
| Owner confirmation | On 2026-04-03 Owner confirmed: Rahul is the payables contact at Reddy Traders. | World, high authority |

**Writing rules**:
- Phrase Munshi's own actions in first person ("I sent", "I reminded") → experience facts
- Always use absolute dates and full names with roles (never "yesterday" or "he")
- Quote customer words briefly (no whole chat logs)
- **Never retain**: phone numbers, bank numbers, unsent drafts

### 4.6 How each part uses memory
| Caller | Operation | Query (shortened) | Result used for |
|--------|-----------|-------------------|-----------------|
| Readiness check | Reflect, tagged to customer | What details/documents has this customer required, why past invoices held, requirements changed? | JSON requirements/conflicts |
| Collector agent | Reflect + recall experience facts | Invoice X is N days overdue. Best next step: whom to contact, when, with what attachments and tone? | Draft plan |
| Risk agent | Recall observations + reflect | Has payment behaviour, contact or requirements changed recently? Rate Normal/Watch/High. | Risk level |
| Customer page | Mental model (stored query) | Playbook: How do we get paid on time by {customer}? | Playbook card |
| Approvals inbox | Reflect based_on | Why this? Evidence behind draft. | "Why this?" panel |

### 4.7 Day 1–2 must-verify list
1. Does retain use supplied timestamp for temporal recall and trends?
2. Are first-person actions classified as experience facts?
3. Do observations form per customer and change after contradicting evidence?
4. Do mental models auto-refresh?
5. How long do retain/reflect take, and how many LLM calls?

Every SDK call marked `# VERIFY` must be checked against the installed version.

## 5. Readiness engine
Rules R1–R9 (fixed code): GSTIN format, checksum, match with buyer record, state code (IGST vs CGST+SGST), PO present, PO amount (1% tolerance), duplicate number, due date (warning), required docs.
Memory findings via reflect JSON: `requirements[]` (codes `PO_REF, SIGNED_CHALLAN, GRN_COPY, EWAY_BILL, EINVOICE_IRN, CONTACT_PERSON, OTHER`) and `conflicts[]`.
Combination order:
1. any rule Blocker → **Blocker**
2. else a required memory requirement with ≥1 evidence id and not attached → **Blocker** ("learned" badge)
3. else any conflict (memory vs buyer record, or old vs new memory) → **Conflict** (owner confirms; confirmation retained)
4. else single-evidence requirement, evidence >180 days old, or consolidation pending → **Uncertain**
5. else **Ready**
Owner-confirmed learned requirements are written to the customer record and become rules (R5/R9); memory keeps watching.

## 6. Agents and Band

### 6.1 Agent purposes

| Agent | Trigger | Reads | Does | Never does |
|-------|---------|-------|------|------------|
| **Collector** | Daily check / due / overdue / new reply | Reflect + Recall + ledger | Drafts messages with recipient/timing/attachments; posts for approval; asks Risk on distress cues | Sends anything without approval |
| **Risk** | Each new payment/reply/day / Collector request | Observations + trends + reflect | Sets risk level (NORMAL/WATCH/HIGH); flags conflicts; alerts owner with evidence and suggested action | Changes credit terms or holds dispatch itself |
| **Readiness** (service, not agent) | Invoice created/edited | Rules + reflect | Returns READY/BLOCKER/CONFLICT/UNCERTAIN | Approves invoice on memory alone |

### 6.2 Band AI desktop integration

**Purpose**: Multi-agent collaboration surface where Collector and Risk agents work with the owner in a shared "AR Desk" room.

**Two distinct components**:
1. **Desktop application** (download from band.ai): Used by owner for collaborative work
2. **Programmatic integration** (SDK in `band/run_agents.py`): Backend connects agents as External Agents

**Integration boundary**: Only `backend/munshi/band/` may import and use `band-sdk`.

### 6.3 Band core modules

| Module | Purpose |
|--------|---------|
| `band/run_agents.py` | External Agent setup (Collector, Risk), SDK initialization, agent lifecycle |
| `band/bridge.py` | Backend events → Band room posts (drafts, risk alerts) |
| `band/commands.py` | Regex patterns for inbound room messages (approve A-n, edit A-n, reject A-n, @Risk handoff) |

### 6.4 Band message formats (regex parsed, **not** LLM)

| Format | Example | Handled by |
|--------|---------|------------|
| Collector draft | `[DRAFT A-231] To Priya (Reddy Traders), WhatsApp, today 10:30. <message>. Why: <evidence>. Reply: approve A-231 / edit A-231: <text> / reject A-231` | `band/commands.py` |
| Risk alert | `[RISK] Reddy Traders: Watch → High. Signals: missed 5th and 20th; "cash flow tight" on 21 Apr. Suggest: hold next dispatch or ask 30% advance. @owner` | `band/commands.py` |
| Collector→Risk handoff | `@Risk reply from Rahul mentions cash-flow trouble on INV-1060, please assess` | `band/commands.py` |
| Owner question | Plain text (no prefix) | `POST /api/explain` endpoint |

### 6.5 Approval flow

1. Collector creates draft in SQLite with status `DRAFTED`
2. Draft appears in Band room **and** web Approvals inbox (same backend endpoint)
3. Owner approves, edits or rejects from either surface (first decision wins)
4. On approval, message delivered (simulated customer in demo, WhatsApp link in real use)
5. Action retained in Hindsight as experience fact
6. Customer reply and payment stored in SQLite and retained in Hindsight

### 6.6 Fallback
If Band is unavailable:
- Web app provides identical functionality (approvals inbox, risk alerts)
- Backend event bridge posts to room only if Band is reachable
- No automatic fallback (owner must use web app if Band is down)

## 7. Database design
See [DATABASE_DESIGN.md](DATABASE_DESIGN.md). Amounts in integer paise. Simulated time everywhere via `services/clock.py`.

## 8. API communication
JSON under `/api`, no auth in the prototype (single demo business), frontend polls every 3 s, no websockets. See [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## 9. Integration strategy

### 9.1 Technology verification order
1. **Day 1–2 Spike**: Verify Hindsight SDK against pinned version (check timestamps, experience facts, observations, mental models)
2. **Day 2**: Verify Band SDK (External Agent setup, message formats, fallback to web)
3. **Day 3**: Verify Groq SDK (structured outputs, function calling per model, rate limits)
4. **Day 4**: Integrate DB+rules with verified memory
5. **Day 5**: Integrate agents with verified Band
6. **Day 6**: Full demo with all three technologies

### 9.2 Integration boundaries (enforced by module structure)
- **Hindsight**: `memory/client.py` only → never in `agents/`, `checks/`, `api/`, `band/`
- **Groq**: `llm/groq_client.py` only → never in `agents/`, `checks/`, `api/`, `band/`, `memory/`
- **Band SDK**: `band/run_agents.py` only → never in `agents/`, `checks/`, `api/`, `memory/`

### 9.3 Fallbacks
| Technology | Production fallback | Development fallback |
|------------|--------------------|---------------------|
| Hindsight | Cloud instance (`munshi-<slug>`); local Docker (`munshi-local`) | `memory/fake.py` (in-memory store with retain/reflect stubs) |
| Groq | Cloud API; cache layer on disk | `llm/fake.py` (cached responses for development) |
| Band | Desktop app + external agents | Web app (approvals inbox, risk alerts only) |

### 9.4 Integration order
1. DB+rules → memory spike (Day 1–2) → verifier tests against pinned Hindsight version
2. LLM layer → cached calls → verify Groq structured outputs and function calling
3. Band → External Agent setup → verify message formats and fallback to web
4. Readiness → memory findings + rule checks → end-to-end test
5. Agents → memory + LLM → golden scenario (Reddy Traders)
6. Daily loop → SQLite first, retain, Band → approval flow end-to-end
7. Simulator + eval → A/B/C arms → learning curve comparison
8. Frontend → all backends → 60-second demo rehearsed

### 9.5 Testing strategy for each technology
- **Hindsight**: Integration test + golden scenario; verify timestamps honoured; verify experience facts extracted; verify observations change on contradiction
- **Groq**: Test structured output schemas per model; test function-calling error handling; test rate-limit retry logic
- **Band**: Test External Agent connection; test message format parsing; test fallback to web app

### 9.6 Error handling
| Technology | Error handling approach |
|------------|------------------------|
| Hindsight | SQLite write succeeds → retain fails → `memory_event.retained_at` NULL → background retry |
| Groq | Structured output parse fails → log and retry with fallback prompt; rate limit → exponential backoff |
| Band | Room post fails → log but don't block backend operation; owner uses web app |
