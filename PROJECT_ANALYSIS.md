# PROJECT ANALYSIS: Munshi

## Complete Project Understanding

### Project Objective and Problem Statement
**Munshi** is an AI collections agent for small Indian B2B suppliers targeting a national problem: delayed payments to MSMEs.

- **Problem**: Small suppliers wait ~73 days on average to be paid (Recordent SME Receivables Report 2026). Knowledge about payment habits lives in one person's head and scattered WhatsApp chats, not in databases.
- **Root causes**: Weak collections and payment discipline (not long credit terms). Invoices get held for missing PO numbers, unsigned challans, wrong GSTIN. Contacts change silently. When the accountant leaves, knowledge leaves.

### Target Users and Use Cases
**Primary persona**: Ravi, owner of a packaging unit near Hyderabad with ~80 business customers.

- Invoices made in Tally, payments chased on WhatsApp and phone by Ravi and one accountant
- Remembers payment run days and whom to call, but not reliably across 80 customers
- Finds out about held invoices weeks later
- Early signs of trouble noticed too late

**Use cases**:
1. Import customers and open invoices from Tally-style CSV
2. Create new invoices with readiness check before sending
3. Review and approve drafted follow-up messages
4. Monitor customer risk levels and memory evolution
5. Simulate and evaluate the system's learning behavior

### Proposed Solution
Munshi runs a single loop across three moments:

1. **Prevent** — Before an invoice is sent, check it against fixed rules (R1–R9) plus learned requirements (e.g., "needs signed challan") with evidence
2. **Follow up** — When an invoice is due/overdue, draft the right message to the right person at the right time. Owner approves every message.
3. **Revise** — When contact, requirements, or payment habits change, flag conflicts. The Risk agent warns before default.

**Key innovation**: Uses Hindsight's learning layer (experience facts, observations, mental models, directives, disposition) instead of just retain/recall. Proves learning with a three-way comparison (no memory, structured DB memory, Hindsight) on held-out months.

### Functional Requirements

| Category | Requirement |
|----------|-------------|
| Data ingestion | Tally-style CSV import; invoice form with document uploads (INVOICE_PDF, PO_COPY, SIGNED_CHALLAN, GRN, EWAY_BILL, OTHER) |
| Readiness check | Rules R1–R9 (fixed): GSTIN format/checksum/buyer match/state code; PO present/amount within 1%; duplicate number; required docs; due date warning |
| Readiness states | READY, BLOCKER, CONFLICT, UNCERTAIN (with evidence) |
| Risk assessment | Levels: NORMAL (stable), WATCH (one signal), HIGH (≥2 signals) |
| Follow-up workflow | Collector agent drafts messages; owner approves via web app or Band room; WhatsApp handoff (simulated in demo) |
| Memory updates | Experience facts retained in Hindsight after action sent; observations consolidated; mental models updated |
| Simulator | Deterministic seeded world, personas, scenarios; clock manipulation for demo |
| Evaluation | Arms A (fixed rules only), B (structured DB memory), C (Hindsight); measures early-warning lead time, days late, blocker catch rate |

### Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Technology stack | Hindsight (mandatory), Band AI (mandatory), Groq LLMs (gpt-oss-120b for agents, qwen3-32b for customers) |
| Authentication | None in prototype (single demo business) |
| API communication | REST over `/api`, JSON only; no websockets; frontend polls every 3s |
| Data source of truth | SQLite (amounts, dates, statuses); Hindsight (knowledge/memory) |
| Security | Phone/bank numbers never retained in Hindsight; directives block threats/out-of-hours contact; owner approval before all messages |
| Simulated time | All dates/times use `services/clock.py` for reproducible evaluation |

### Features and Screens

| Screen | Purpose | Key Elements |
|--------|---------|--------------|
| Dashboard | See where money is stuck | Total receivable, overdue, at-risk customers, pending drafts, blockers caught |
| Customer page | Everything Munshi knows about one customer | Playbook card (mental model), beliefs with trend arrows, timeline |
| New invoice + readiness | Catch blockers before sending | Invoice form, document uploads, readiness panel, evidence popovers |
| Approvals inbox | Owner approves every outgoing message | Draft text, recipient, timing, attachments, "Why this?" panel, approve/edit/reject, WhatsApp link |
| Risk alerts | Early warning | Risk level changes with signals and suggested action |
| Simulation console | Run the demo | Simulated clock, fast-forward, inject events (contact change, distress) |
| Evaluation | Show proof | Learning curves for versions A/B/C, metrics comparison |

### Technology Stack and Dependencies

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11+, FastAPI, SQLModel, SQLite, pydantic-settings, uv |
| Memory | Hindsight (Cloud for demo, Docker locally) |
| Agents / collaboration | Band SDK (`band-sdk`) — agents are backend modules |
| LLM | Groq: `gpt-oss-120b` (agents), `qwen3-32b` (simulated customers) |
| Frontend | React 18, Vite, TypeScript, Tailwind, TanStack Query, Recharts |
| Tooling | Docker Compose, Makefile, pytest, ruff (line length 100), GitHub Actions |

### Backend Architecture

**Modules and Responsibilities**:

| Module | Path | Responsibility | Depends on |
|--------|------|----------------|------------|
| Config | `munshi/config.py` | env settings | — |
| DB | `munshi/db/` | 12 SQLModel tables, session, seed | config |
| LLM | `munshi/llm/` | Groq client + disk cache + JSON utils | config |
| Memory | `munshi/memory/` | Hindsight wrapper only; bank setup, retain templates, queries, parsing, outbox | config, db |
| Checks | `munshi/checks/` | GSTIN, rules R1–R9, readiness combiner | db, memory findings passed in |
| Agents | `munshi/agents/` | Policy interface, Collector, Risk, drafting, prompts | memory, llm, db |
| Services | `munshi/services/` | clock, daily loop, WhatsApp link | agents, db |
| API | `munshi/api/` | HTTP routers | all above |
| Band | `munshi/band/` | run agents, bridge, command parsing | API (HTTP) only |
| Simulator | `sim/` | seeded world, personas, scenarios | api (HTTP) or services |
| Evaluation | `eval/` | arms A/B/C, metrics, report | agents.policy, sim |

**Integration rules**:
- Only `memory/client.py` imports Hindsight
- Only `llm/groq_client.py` calls Groq
- App and evaluation share `agents/policy.py`
- Prompts live in `agents/prompts/*.md`

### Database Design

**Tables (12)**: business, customer, invoice, invoice_document, readiness_check, action, inbound_message, payment, promise, risk_alert, memory_event, sim_run

**Key enums**:
- `invoice.status`: DRAFT, READY, SENT, HELD, PARTLY_PAID, PAID, DISPUTED, WRITTEN_OFF
- `invoice.readiness`: READY, BLOCKER, CONFLICT, UNCERTAIN
- `action.kind`: REMINDER, DOC_SEND, THANK_YOU, ESCALATION_REQUEST
- `action.status`: DRAFTED, APPROVED, EDITED, REJECTED, SENT
- `customer.risk_level`: NORMAL, WATCH, HIGH

**Constraints**:
- Money: integer paise only
- Dates: simulated clock
- Enums stored as strings
- UNIQUE (customer_id, invoice_number)

### Readiness Engine

**Rules R1–R9 (fixed, testable code)**:
1. GSTIN format
2. GSTIN checksum
3. GSTIN matches buyer record
4. State code determines IGST vs CGST+SGST
5. PO present (if required)
6. PO amount within 1% tolerance
7. Duplicate invoice number
8. Due date warning
9. Required docs

**Memory findings via reflect JSON**: `requirements[]` (codes: PO_REF, SIGNED_CHALLAN, GRN_COPY, EWAY_BILL, EINVOICE_IRN, CONTACT_PERSON, OTHER) and `conflicts[]`.

**Combination order**:
1. Any rule Blocker → **Blocker**
2. Else a required memory requirement with ≥1 evidence id and not attached → **Blocker** ("learned" badge)
3. Else any conflict (memory vs buyer record, or old vs new memory) → **Conflict** (owner confirms)
4. Else single-evidence requirement, evidence >180 days old, or consolidation pending → **Uncertain**
5. Else **Ready**

**Owner-confirmed learned requirements** become part of the customer record (R5/R9), then become fixed rules.

### AI Agents and Responsibilities

| Agent | Trigger | Reads | Does | Never does |
|-------|---------|-------|------|------------|
| **Collector** | Daily check / due / overdue / new reply | Reflect + Recall + ledger | Drafts messages with recipient/timing/attachments; posts for approval; asks Risk on distress cues | Sends without approval |
| **Risk** | Each new payment/reply/day / Collector request | Observations + trends + reflect | Sets risk level (NORMAL/WATCH/HIGH); flags conflicts; alerts owner with evidence | Changes credit terms or holds dispatch |
| **Readiness** (service, not agent) | Invoice created/edited | Rules + reflect | Returns READY/BLOCKER/CONFLICT/UNCERTAIN | Approves invoice on memory alone |

**Band room "AR Desk: {business}"**:
- Participants: Owner (human), Collector (external agent), Risk (external agent)
- Message formats parsed by regex:
  - `[DRAFT A-231] To Priya (Reddy Traders), WhatsApp, today 10:30. <message>. Why: <evidence>. Reply: approve A-231 / edit A-231: <text> / reject A-231`
  - `[RISK] Reddy Traders: Watch → High. Signals: … Suggest: … @owner`
  - Free-text owner questions → `POST /api/explain`

### Hindsight Memory Integration

**Banks**:
| Bank Naming | Purpose |
|-------------|---------|
| `munshi-<business-slug>` | Production/demo; customers separated by tags `customer:<id>`, `kind:<event>` |
| `eval-<run-id>-C-s<seed>` | Evaluation runs; fresh bank per run+seed |

**Bank configuration**:
- **Directives** (global, untagged):
  1. Never threaten legal action or use coercive language
  2. Never recommend contacting outside 09:00–19:00 IST
  3. Never reveal one customer's information to another
  4. Never state invoice validity or payment receipt (come from ledger)
  5. Cite evidence behind every recommendation; say so if none
  6. Mention MSME rules only when business marked registered

- **Disposition**: Skepticism 4, literalism 3, empathy 3
- **Retain mission**: Extract facts that affect when/how supplier gets paid
- **Observations mission**: Consolidate durable patterns per customer
- **Reflect mission**: Help owner get paid on time without harming relationships

**What gets retained** (one event per call):
- Invoice sent, held, reminder sent
- Customer reply (quoted briefly)
- Promise to pay + whether kept
- Contact change (absolute date, full name, role)
- Owner confirmation (high authority)
- Never retain: phone/bank numbers, unsent drafts

**Uses**:
- Readiness check → reflect → JSON requirements/conflicts
- Collector → reflect + recall experience facts
- Risk → recall observations + reflect for level
- Customer page → mental model
- Approvals "Why this?" → reflect `based_on`

### Band Agent Collaboration

- Two agents (Collector, Risk) + owner share one Band room
- Agent logic lives in backend; Band is the collaboration surface
- Inbound room messages matched against command patterns by regex (not LLM)
- Outbound posts from backend events via bridge
- Fallback: web approvals inbox and Risk page are functionally equivalent

### Groq LLM Integration

- **gpt-oss-120b**: Agents, drafting, policy reasoning
- **qwen3-32b**: Simulated customers
- Groq SDK called only from `llm/groq_client.py`
- Disk cache for retries; rate limiting handled with caching

### Simulation and Evaluation Methodology

**Simulator**:
- Deterministic, seeded world
- Personas based on public dataset + supplier interviews
- Clock manipulation for demo/fast-forward

**Evaluation arms**:
- **A**: Fixed rules only (GSTIN, PO, required docs)
- **B**: Structured DB memory (customer credit_days, po_required, required_docs columns)
- **C**: Hindsight (experience facts, observations, mental models, trends)

**Metrics**:
- Early-warning lead time (days before payment run that a warning would appear)
- Days late by month
- Blocker catch rate (invoiced with readiness BLOCKER vs held after sending)

**Three-version test**: Run arms A/B/C on held-out months (months 4–6) with 3 seeds; compare learning curves.

### Security, Privacy and Business Rules

**Directives enforced by LLM**:
1. No threats or coercive language
2. Only contact 09:00–19:00 IST
3. Never disclose one customer's info to another
4. Never state invoice validity/payment (ledger decides)
5. Cite evidence or say so
6. Mention MSME rules only if business registered

**Data minimisation**:
- Phone/bank numbers stay in SQLite only
- One Hindsight bank per business
- Deleting a customer deletes their memories by document id

**Human-in-the-loop**:
- Owner approves every outgoing message
- No automatic sending (real use goes through owner's WhatsApp)
- Risk suggests; owner decides

**Out of scope**:
- Real WhatsApp API
- Tally integration
- OCR of scanned invoices
- Payment processing
- Buyer portal submission
- Multi-user login
- Mobile layout
- Dispute agent (stretch only)

### Testing and Deployment Requirements

**Testing requirements**:
- Fixed code (GSTIN, rules, readiness combiner, risk level rule, simulator rules, retain templates, parsing) needs unit tests
- Memory-dependent code: integration test + golden scenario; never assert exact LLM wording
- Golden scenario: `demo.yaml`; check Reddy Traders' playbook mentions Rahul, 5th/20th, signed challan by month 4

**Deployment steps** (prototype only):
1. `docker compose up` (hindsight, backend, frontend) or Hindsight Cloud + local backend
2. Night before: `prewarm_demo_bank.py` into `munshi-demo-final`
3. One hour before: check Hindsight, Groq, Band reachability; start backend, frontend, agents
4. Backups: cached LLM responses, local Hindsight, Band screen recording, full video on second laptop

**Commands**:
- `make dev`: backend :8000 + frontend :5173
- `make seed`: demo business, customers, fresh bank, mental models
- `make agents`: Collector and Risk connect to Band room
- `make test`: unit tests (integration needs Hindsight reachable)
- `make eval`: A/B/C evaluation across seeds 1,2,3
- `make spike`: Day 1–2 go/no-go memory test

---

## Architecture Overview

```
 Web app (React) ──REST──┐
 Band room (AR Desk) ─SDK─┼──► FastAPI backend ──records──► SQLite  (facts)
 Simulator ────events────┘     │  readiness · collector · risk · daily loop
                               ├──retain/recall/reflect──► Hindsight (knowledge)
                               └──prompts (cached)───────► Groq LLMs
```

**Source-of-truth rules**:
| Decides | Authority |
|---------|-----------|
| SQLite | amounts, dates, invoice status, attached documents, what was approved/sent |
| Hindsight | why customers pay or don't, who to contact, what was required, what changed, how risky |
| Code | rule checks, days late, missed runs, risk level from signals, business-hours limits |
| LLM | message wording, JSON plans, summaries — always from evidence passed in |

**Data flow for one follow-up**:
1. Daily loop finds invoice near due
2. Collector calls reflect → JSON plan + evidence ids
3. Code clamps time to 09:00–19:00 IST and checks cap; LLM writes wording
4. Draft saved in SQLite, posted to Band and web inbox
5. Owner approves (first decision wins)
6. Message delivered (simulated customer or WhatsApp link)
7. Action retained in Hindsight as experience fact
8. Customer reply and payment stored in SQLite and retained in Hindsight
9. Hindsight consolidates; playbook and beliefs update

---

## Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Backend | Python 3.11+, FastAPI | REST API |
| ORM | SQLModel | 12 tables |
| Database | SQLite | Source of truth |
| Memory | Hindsight | Cloud for demo, Docker locally |
| Agents | Band SDK | `band-sdk` |
| LLM | Groq | gpt-oss-120b, qwen3-32b |
| Frontend | React 18, Vite, TypeScript | Tailwind, TanStack Query, Recharts |
| Tooling | Docker Compose, Makefile, pytest, ruff | CI via GitHub Actions |

---

## Feature Breakdown

| Phase | Modules | Deliverable |
|-------|---------|-------------|
| Spike (Days 1–2) | memory/client.py, bank_setup.py, events.py, sim/world.py | **Gate 1**: one customer, 6 months; beliefs form, change on contact change |
| Data + rules | db/models.py, session.py, checks/gstin.py, rules.py (R1–R9) | `test_gstin`, `test_rules` pass |
| LLM layer | llm/cache.py, json_utils.py, groq_client.py, memory/parsing.py | Cached call works |
| Readiness | memory/queries.py, checks/readiness.py, api/invoices.py | `test_readiness` all 5 outcomes |
| Agents | agents/policy.py, collector.py, risk.py, drafting.py, memory/outbox.py | Golden scenario passes |
| Loop + API | services/clock.py, daily_loop.py, whatsapp_link.py, api/*.py | curl walk-through of approve |
| Simulator + eval | sim/profiles.py, world.py, personas.py, calibrate.py, eval/arms/* | Gate 2: A/B/C on 6 customers, 1 seed; C leads B on ≥2 metrics |
| Frontend core | types.ts, api/client.ts, Dashboard, Approvals, InvoiceNew | Manual run |
| Frontend memory UI | Customer page (PlaybookCard, BeliefList, Timeline), Risk, SimConsole | Demo story visible |
| Band | band/commands.py, bridge.py, run_agents.py | Draft appears in room; approve A-n works |
| Full evaluation | make eval | Gate 3: results frozen with git hash |

---

## Module Responsibilities

| Owner | Folders | Responsibility |
|-------|---------|----------------|
| P1 (memory lead) | `backend/munshi/memory/`, `backend/munshi/agents/` | Hindsight integration, policy interface, Collector, Risk |
| P2 (simulator + eval) | `backend/sim/`, `backend/eval/` | World, personas, scenarios, arms A/B/C, metrics, report |
| P3 (backend + Band) | `backend/munshi/db/`, `api/`, `checks/`, `band/`, `services/`, `llm/`, config.py, main.py | Core backend, DB, LLM, API, Band bridge |
| P4 (frontend + story) | `frontend/`, `docs/`, README | React app, documentation, demo script, video |

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Hindsight SDK | Pin Day 1 | Memory store |
| band-sdk | Pin Day 1 | Agent collaboration |
| Groq | — | LLM inference |
| fastapi | — | API framework |
| sqlmodel | — | ORM |
| uv | — | Python package management |
| pytest | — | Unit/integration tests |
| ruff | — | Linter |
| react | 18 | Frontend |
| vite | — | Frontend build |
| tailwind | — | Styling |

---

## Risks and Unresolved Questions

### High Risk
- **Hindsight ignores timestamps**: If Hindsight doesn't honour supplied timestamps, trends follow ingest time. *Mitigation*: Day 1–2 test, fallback is date-aware reflect prompts.
- **Observations/mental models lag**: Memory updating can lag new writes during demo. *Mitigation*: Prewarmed bank, "memory updating" shown, wait in evaluation.
- **Groq/Hindsight rate limits**: During evaluation. *Mitigation*: Cache, overnight runs, smaller world if needed.
- **Version C does not beat B**: Memory on what columns miss. *Mitigation*: Section 16 fallback: refocus memory on what columns miss, re-run.

### Medium Risk
- **LLM drafts contain wrong facts**: Amounts/dates are filled by code, not LLM. *Mitigation*: Verify amounts/dates never come from LLM.
- **Scope creep**: Adding features outside scope. *Mitigation*: Out-of-scope list, team consent required.
- **Band SDK differs from docs**: *Mitigation*: Web inbox does same job; Band integration is thin layer.

### Unresolved Questions

| Question | Source |
|----------|--------|
| **CSV import columns layout**: README mentions open assumption; API spec lists expected columns but doesn't validate. | API_DOCUMENTATION.md |
| **Bank naming convention**: `eval-<run-id>-C-s<seed>` vs `eval-<run-id>-C-s<seed>` — same? | PDF Section 7 |
| **Exact SDK class names for Band**: Code marked `# VERIFY` against installed SDK version. | PDF Section 8 |
| **Memory event retention format**: Exact schema not specified beyond "first person for Munshi's actions". | PDF Section 7 |
| **Hindsight concurrency model**: How to handle multiple retain calls for same event id? | PDF Section 7 |
| **Evaluation run duration**: How many days/months per seed? | PDF Section 16 |
| **Exact Hindsight version**: Pin on Day 1. | PDF Section 7 |
| **What "simulated time" means for real deployments**: Only for demo/eval? | DATABASE_DESIGN.md |

---

## List of Decisions Requiring Confirmation

| Decision | Context |
|----------|---------|
| **Do we keep the open CSV import assumptions?** | API_DOCUMENTATION.md lists expected columns but README calls it an open assumption. |
| **How to handle Hindsight versioning?** | PDF says "Pin one Hindsight version on Day 1"; needs specific version number. |
| **What exactly constitutes "simulated customers"?** | PDF says "based on public receivables dataset"; needs dataset name and licence check. |
| **Do we need a Dispute agent (stretch goal)?** | Listed as optional; not in core 12 phases. |
| **How to handle "memory updating" UI state?** | PDF mentions UI shows "memory updating" but no endpoint specified. |
| **What's the exact Band message format for plain questions?** | PDF mentions `POST /api/explain` for owner questions but format not specified. |
| **Should we use ULID or sequential IDs for memory events?** | PDF says `evt_<ulid or counter>`; needs decision. |
| **What's the fallback if Hindsight Cloud credits run out?** | PDF says `MEMHACK99` promo code but doesn't specify fallback plan. |
| **Do we implement Tally integration?** | Listed as "Out of scope" but README mentions "Tally-style CSV import". |
| **What's the exact evaluation seeding strategy?** | PDF mentions seeds 1,2,3 but not how to generate reproducible seeds. |

---

## Files Status Summary

| File | Status | Notes |
|------|--------|-------|
| **Munshi — Complete Project Documentation.pdf** | ✓ Read | 48 pages; primary source |
| **README.md** | ✓ Read | Project overview |
| **ARCHITECTURE.md** | ✓ Read | System architecture, modules, Hindsight design |
| **API_DOCUMENTATION.md** | ✓ Read | 22 endpoints, error codes, schemas |
| **DATABASE_DESIGN.md** | ✓ Read | 12 tables, enums, constraints |
| **IMPLEMENTATION_ROADMAP.md** | ✓ Read | 12 phases, dependencies, gates |
| **MODULE_CONTRACTS.md** | ✗ Empty | No content |
| **ASSUMPTIONS_AND_OPEN_ITEMS.md** | ✗ Empty | No content |
| **AI_CREDIT_USAGE_PLAN.md** | ✗ Empty | No content |
| **docs/AI_PROGRESS.md** | ✗ Empty | No content |
| **AGENTS.md** | ✗ Empty | No content |
| **DEVELOPMENT_RULES.md** | ✓ Read | Coding standards, file rules, git workflow |

---

## Concise Report

**What was inspected**:
1. **PDF** (primary source, 48 pages): Full project specification including executive summary, problem statement, solution design, architecture, Hindsight integration, agents, evaluation methodology, and implementation roadmap.
2. **README.md**: Project overview, problem statement, features, tech stack, folder structure, workflow.
3. **ARCHITECTURE.md**: System architecture, module responsibilities, Hindsight memory design, readiness engine, agents and Band, database design.
4. **API_DOCUMENTATION.md**: All 22 API endpoints with request/response schemas, error codes.
5. **DATABASE_DESIGN.md**: 12 SQLModel tables, enums, relationships, constraints.
6. **IMPLEMENTATION_ROADMAP.md**: 12 phases with dependencies, testing checkpoints, deployment steps.
7. **DEVELOPMENT_RULES.md**: Coding standards, naming conventions, folder ownership, file modification rules, git workflow, testing requirements.
8. **Empty files**: MODULE_CONTRACTS.md, ASSUMPTIONS_AND_OPEN_ITEMS.md, AI_CREDIT_USAGE_PLAN.md, docs/AI_PROGRESS.md, AGENTS.md.

**What remains unclear**:
1. **CSV import columns**: API spec lists expected columns but README calls it an open assumption.
2. **Exact Hindsight version**: Needs pinning on Day 1; current docs refer to pinned version but don't specify it.
3. **Simulated customer dataset**: PDF mentions "public receivables dataset" but doesn't name it or specify licence.
4. **Exact Band SDK class names**: Code marked `# VERIFY` but no actual verification in docs.
5. **Memory event ID format**: PDF says `evt_<ulid or counter>` — needs decision.
6. **Evaluation run duration**: PDF mentions months 1–6 split but not exact days per simulated month.
7. **Hindsight concurrency model**: Not specified how to handle multiple retain calls for same event id.
8. **Fallback if Hindsight Cloud credits run out**: No plan documented despite promo code mention.

**Critical dependencies requiring external confirmation**:
1. Hindsight Cloud access and `MEMHACK99` promo code validity
2. Band AI desktop download and External Agent setup
3. Groq API key and model availability (gpt-oss-120b, qwen3-32b)
4. Hindsight SDK version compatibility with documentation

**Immediate next steps for the team** (not to be implemented yet):
1. Pin Hindsight version against Day 1 test
2. Download and set up Band AI desktop with External Agents
3. Register for Hindsight Cloud with `MEMHACK99` promo
4. Verify Groq API key and model access
5. Confirm simulated customer dataset and licence
