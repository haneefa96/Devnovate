# IMPLEMENTATION ROADMAP

The source plan is ~10 relative days with three gates (days are relative; deadline unconfirmed). Compress middle phases if needed; **never** skip the Day 1–2 spike or the demo rehearsals.

## Technology requirements (hackathon mandatory)

| Technology | Purpose | Integration boundary | Verification |
|------------|---------|---------------------|--------------|
| **Hindsight** | Long-term memory (experience facts, observations, mental models) | `backend/munshi/memory/` only | Day 1–2 test: timestamps, experience facts, mental models |
| **Band AI** | Multi-agent collaboration (Collector, Risk external agents) | `backend/munshi/band/` only | Day 2 test: External Agent setup, message formats, fallback |
| **Groq** | LLM inference (gpt-oss-120b for agents, qwen3-32b for customers) | `backend/munshi/llm/` only | Day 2–3 test: structured outputs, function calling, rate limits |

## Dependency graph
```
config ─► db ─► checks(rules) ─► readiness ─► api/invoices
   │        └──────────────────────────────► api/*
   └─► llm ─┐
   └─► memory ─► agents(policy, collector, risk) ─► services(daily_loop) ─► api/sim
                                                     └► band ► (HTTP to api)
sim ─► eval(arms A,B,C using agents.policy) ─► api/eval ─► frontend /eval
frontend ─► api (HTTP only)
```

## Phases and module order
| # | Phase | Modules (in order) | Testing checkpoint |
|---|---|---|---|
| 0 | Setup | pin versions, `.env`, Docker Hindsight, git | `docker compose up hindsight` reachable; `make test` runs |
| 1 | **Spike (Day 1–2)** | `memory/client.py`, `bank_setup.py`, `events.py`, `scripts/spike_one_customer.py`, minimal `sim/world.py` | **Gate 1 (go/no-go)**: one customer, 6 months; right beliefs form, reflect changes next plan, a belief weakens after contact change. Else apply fallbacks (ARCHITECTURE §4) |
| 2 | **Technology verification (Day 2)** | `llm/groq_client.py`, `band/run_agents.py`, `band/commands.py` | **Gate 1.5**: Hindsight timestamps honoured, Groq structured outputs per model, Band External Agent connection and fallback verified |
| 3 | Data + rules | `db/models.py`, `session.py`, `checks/gstin.py`, `rules.py` (R1–R9) | `test_gstin`, `test_rules` pass |
| 4 | LLM layer | `llm/cache.py`, `json_utils.py`, `memory/parsing.py` | `test_parsing`; one cached call works |
| 5 | Readiness | `memory/queries.py` (readiness), `checks/readiness.py`, `api/invoices.py`, `api/imports.py` | `test_readiness` all 5 outcomes |
| 6 | Agents | `agents/policy.py` (exists), `collector.py`, `risk.py`, `drafting.py`, `memory/outbox.py` | golden scenario on demo.yaml |
| 7 | Loop + API | `services/clock.py`, `daily_loop.py`, `whatsapp_link.py`, `api/actions.py`, `messages.py`, `payments.py`, `risk.py`, `explain.py`, `dashboard.py`, `sim.py`, `main.py`, `db/seed.py` | curl walk-through of "approve a draft" |
| 8 | Simulator + eval | `sim/profiles.py`, `world.py`, `personas.py`, `calibrate.py`, `eval/arms/*`, `metrics.py`, `report.py`, `run_eval.py` | `test_world_rules`; **Gate 2 (Day 4)**: A/B/C on 6 customers, 1 seed; C leads B on ≥2 metrics else rethink memory contents |
| 9 | Frontend core | `types.ts`, `api/client.ts`, `lib/format.ts`, hooks, Dashboard, Approvals, InvoiceNew + ReadinessPanel | manual run against seeded backend |
| 10 | Frontend memory UI | Customer page (PlaybookCard, BeliefList, Timeline), EvidencePopover, Risk, SimConsole, Evaluation | demo story visible |
| 11 | Band integration | `band/bridge.py`, `band/run_agents.py` (if not done) | draft appears in room; `approve A-n` works; fallback verified |
| 12 | Full evaluation | run `make eval` (≤2 full runs, overnight, keep cache) | **Gate 3 (Day 8)**: results frozen and committed with git hash |
| 13 | Demo + deploy | `prewarm_demo_bank.py`, demo script, recorded video, README GIF | 60-second core rehearsed twice; backup video |

## Integration milestones
1. **M1** rules + readiness (without memory) via API.
2. **M2** memory spike result recorded in `docs/hindsight.md`.
3. **M3** daily loop produces a draft end-to-end in SQLite.
4. **M4** web approvals → retain → playbook updates.
5. **M5** Band room mirrors drafts/alerts.
6. **M6** eval results visible on `/eval`.

## Technology verification milestones (Day 1–2 spike)
1. **Hindsight verification**: retain event → recall finds it; timestamp honoured; experience facts extracted; mental models change on contradiction.
2. **Groq verification**: structured output schema per model; function-calling error handling; rate-limit retry logic.
3. **Band verification**: External Agent connects; message format parsing (regex); fallback to web app.

## Deployment steps
Prototype only (no production hosting required by the source doc):
1. `docker compose up` (hindsight, backend, frontend) or Hindsight Cloud + local backend.
2. Night before: `scripts/prewarm_demo_bank.py` into `munshi-demo-final`; keep a local copy.
3. One hour before: check Hindsight, Groq, Band reachability; start backend, frontend, agents; open five tabs.
4. Backups: cached LLM responses, local Hindsight, Band screen recording, full video on a second laptop.
Optional hosting (assumption): frontend on a static host, backend on one small VM/container; not required.

