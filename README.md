# Munshi — AI collections agent with persistent memory

> Built for HackWithHyderabad 3.0. **Status: project skeleton. No features are implemented yet.**
> Start with [AGENTS.md](AGENTS.md) if you are an AI coding assistant.

## Problem statement
Small Indian B2B suppliers wait about 73 days to be paid (Recordent SME Receivables Report 2026). What would speed this up lives in one person's head and scattered WhatsApp chats: which customer pays on which day, who releases funds, which document a buyer always asks for, and the first signs of trouble. Invoices get held for a missing PO number, an unsigned challan or a wrong GSTIN, and the owner finds out weeks later. Contacts change silently. When the accountant leaves, the knowledge leaves too.

## Proposed solution
Munshi learns *why* each customer pays late and runs one loop:
1. **Prevent** — before an invoice is sent, check it against fixed rules plus this buyer's remembered holds and requirements (Ready / Blocker / Conflict / Uncertain, with evidence).
2. **Follow up** — when an invoice is near due or overdue, draft the right message to the right person at the right time. **The owner approves every message.**
3. **Revise** — when a contact, requirement or payment habit changes, flag the conflict rather than trust old memory; the Risk agent warns before a default.

Scope: one persona (owner/accountant of a small manufacturer), one workflow (invoice → cash), simulated customers, human approval on every outgoing message, no automatic sending.

## Features
- Tally-style CSV import; invoice form with document uploads
- Readiness check: rules R1–R9 + learned requirements with evidence
- Collector agent (drafts follow-ups) and Risk agent (NORMAL / WATCH / HIGH)
- Approvals inbox (web and Band room) with "Why this?" evidence, "Open in WhatsApp" handoff
- Customer playbook card (Hindsight mental model), beliefs with trend arrows, timeline
- Simulator (seeded, deterministic) + 3-way evaluation: A fixed schedule, B structured DB memory, C Hindsight

## Technology stack
| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLModel, SQLite, pydantic-settings, uv |
| Memory | Hindsight (Cloud for demo, Docker locally) |
| Agents / collaboration | Band (`band-sdk`) — agents are backend modules |
| LLM | Groq: `gpt-oss-120b` (agents), `qwen3-32b` (simulated customers) |
| Frontend | React 18, Vite, TypeScript, Tailwind, TanStack Query, Recharts |
| Tooling | Docker Compose, Makefile, pytest, ruff, GitHub Actions |

## Prerequisites
Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, Docker, a Groq API key, Hindsight (Cloud access or local Docker), a Band account with two External Agents (Collector, Risk) created.

## Installation
```bash
cp .env.example .env            # fill in keys (never commit .env)
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
```
Local Hindsight (verify env var names against the Hindsight README):
```bash
docker compose up hindsight     # API :8888, web UI :9999
```

## How to run
```bash
make dev      # backend :8000 + frontend :5173
make seed     # demo business, customers, fresh bank, mental models
make agents   # Collector and Risk connect to the Band room
make test     # unit tests (integration tests need a reachable Hindsight)
make eval     # A/B/C evaluation across seeds 1,2,3
make spike    # Day 1–2 go/no-go memory test
```
Currently most commands will run but do nothing useful: modules are placeholders. See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md).

## Folder structure
```
munshi/
├── AGENTS.md  CLAUDE.md          # entry points for AI assistants
├── README.md ARCHITECTURE.md DEVELOPMENT_RULES.md
├── IMPLEMENTATION_ROADMAP.md API_DOCUMENTATION.md DATABASE_DESIGN.md
├── .env.example  docker-compose.yml  Makefile  LICENSE  .gitignore
├── .github/                      # CI + PR template
├── docs/                         # MODULE_CONTRACTS, ASSUMPTIONS_AND_RISKS, AI_CREDIT_PLAN, hindsight, evaluation, demo-script
├── backend/
│   ├── pyproject.toml  Dockerfile
│   ├── munshi/
│   │   ├── main.py config.py
│   │   ├── db/        # models (12 tables), session, seed            [P3]
│   │   ├── api/       # one router file per resource                 [P3]
│   │   ├── memory/    # Hindsight wrapper, bank config, events       [P1]
│   │   ├── checks/    # GSTIN, rules R1–R9, readiness combiner       [P3]
│   │   ├── agents/    # collector, risk, drafting, policy, prompts   [P1]
│   │   ├── llm/       # Groq client, cache, json utils               [P3]
│   │   ├── band/      # run_agents, bridge, commands                 [P3]
│   │   └── services/  # clock, daily_loop, whatsapp_link             [P3]
│   ├── sim/           # profiles, calibrate, world, personas, scenarios  [P2]
│   ├── eval/          # run_eval, arms A/B/C, metrics, report, results  [P2]
│   ├── scripts/       # prewarm_demo_bank, spike_one_customer
│   └── tests/
└── frontend/src/      # pages, components, hooks, api, lib            [P4]
```
Owners P1–P4 come from the project document; a solo developer simply takes all roles but should still respect the module boundaries.

## Development workflow
1. Pick the next module from [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md).
2. Read its entry in [docs/MODULE_CONTRACTS.md](docs/MODULE_CONTRACTS.md) (inputs, outputs, allowed files, checklist).
3. Branch `feat/<module>`, implement only the allowed files, tick the checklist, open a PR.
4. Follow [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md).

## Testing
`make test` (pytest). Fixed rules and simulator get full unit tests; memory uses integration tests and a golden scenario (`demo.yaml`: Reddy Traders' playbook must mention Rahul, the 5th and 20th, and the signed challan by month 4). Frontend: `npm run build` in CI; a Playwright smoke test is planned.

## Documentation index
[ARCHITECTURE](ARCHITECTURE.md) · [API](API_DOCUMENTATION.md) · [DATABASE](DATABASE_DESIGN.md) · [RULES](DEVELOPMENT_RULES.md) · [ROADMAP](IMPLEMENTATION_ROADMAP.md) · [MODULE_CONTRACTS](docs/MODULE_CONTRACTS.md) · [ASSUMPTIONS_AND_RISKS](docs/ASSUMPTIONS_AND_RISKS.md) · [AI_CREDIT_PLAN](docs/AI_CREDIT_PLAN.md)
