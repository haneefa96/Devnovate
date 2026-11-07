# MUNSHI — ASSUMPTIONS, RISKS AND OPEN ITEMS

## 1. Purpose

This document records technical assumptions, unresolved decisions, external dependencies and project risks.

AI coding assistants must read this document before implementing any module.

An assumption must never silently become a confirmed requirement.

## 2. Confirmed Project Decisions

The following decisions are defined in the project documentation:

| Area | Decision |
|---|---|
| Application | AI collections agent for Indian B2B suppliers |
| Primary user | Small manufacturer owner or accountant |
| Main workflow | Invoice to cash |
| Backend | Python FastAPI |
| Frontend | React 18, Vite, TypeScript |
| Database | SQLite with SQLModel |
| Persistent memory | Hindsight |
| Multi-agent platform | Band |
| LLM provider | Groq |
| Agent model | GPT-OSS-120B, subject to model ID verification |
| Simulation model | Qwen3-32B, subject to model ID verification |
| Charts | Recharts |
| Data fetching | TanStack Query |
| Styling | Tailwind CSS |
| Timezone | Asia/Kolkata |
| Approval | Human approval required for every outgoing message |
| Real messaging | Pre-filled WhatsApp link; no automatic sending |

## 3. Technical Assumptions Requiring Verification

### 3.1 Hindsight

Assumptions:
- Hindsight supports business-specific banks.
- Events can be retained with absolute timestamps.
- Customer tags can isolate memories.
- Reflect returns evidence references.
- Observations can consolidate over time.
- Mental models can be retrieved and refreshed.

Must verify:
- Exact SDK initialization.
- Retain argument names.
- Recall filtering syntax.
- Reflect response structure.
- Evidence ID format.
- Timestamp handling.
- Mental model creation and refresh.
- Observation trend field names.
- Background consolidation behaviour.

Fallbacks:
- If supplied timestamps are ignored, use explicit dates in retained text and date-aware reflect prompts.
- If observations do not consolidate correctly, retain owner-confirmed belief summaries.
- If mental models do not refresh automatically, refresh them after each simulated week.
- If trend information is unavailable, compare dated evidence using code and reflect.

Only the memory adapter should change when the Hindsight SDK changes.

### 3.2 Band

Assumptions:
- Band supports external Python agents.
- Collector and Risk can connect independently.
- Backend events can be posted to a shared room.
- Owner commands can be parsed and routed.

Must verify:
- Exact SDK package and import paths.
- Agent initialization.
- Authentication format.
- Framework adapter availability.
- Tool registration.
- Room message event structure.
- Message posting API.

Fallback:
Use the web Approvals inbox and Risk page. Keep Band integration isolated so that the core application continues working without it.

### 3.3 Groq

Must verify:
- Exact model identifiers.
- API availability.
- JSON response format support.
- Rate limits.
- Token limits.
- Current free-tier availability.

Fallback:
- Use cached responses.
- Use template-based simulated replies.
- Reduce evaluation size.
- Avoid repeated calls for identical prompts.

### 3.4 Database

Assumptions:
- SQLite is sufficient for the hackathon prototype.
- SQLModel will manage database entities.
- SQLite JSON columns or serialized JSON fields will store structured findings.

Rules:
- Store amounts as integer paise.
- Use consistent date and datetime representations.
- Store simulated timestamps when simulation mode is enabled.
- Never use Hindsight as the financial ledger.

### 3.5 WhatsApp

Assumption:
The prototype will generate a pre-filled WhatsApp URL.

It will not:
- Send messages automatically.
- Use the WhatsApp Business API.
- Read WhatsApp conversations automatically.

The owner must manually send approved messages.

## 4. Data and Dataset Assumptions

- Customer profiles will be simulated.
- Base payment lateness will be calibrated using the IBM sample accounts-receivable dataset.
- Supplier interviews will help define realistic customer behaviour.
- The dataset must be downloaded separately.
- Its licence must be checked before committing it to the repository.
- No actual customer financial data should be used without permission.

The simulation must clearly distinguish synthetic records from real business records.

## 5. Open Items

### Hackathon-related

- [ ] Confirm submission deadline.
- [ ] Confirm live-demo slot.
- [ ] Confirm exact Band usage expectations.
- [ ] Confirm Hindsight Cloud credit eligibility.
- [ ] Confirm whether simulated data is acceptable.
- [ ] Confirm article, social media and video submission formats.

### Technical

- [ ] Pin a tested Hindsight version.
- [ ] Verify Hindsight timestamp behaviour.
- [ ] Verify observation consolidation.
- [ ] Verify mental model refresh behaviour.
- [ ] Verify Band SDK imports and adapters.
- [ ] Verify Groq model identifiers.
- [ ] Confirm exact package versions.
- [ ] Test local Docker Hindsight.
- [ ] Confirm document upload storage path.
- [ ] Confirm CSV column mapping for Tally-style imports.

### Product

- [ ] Finalise demo customer profiles.
- [ ] Conduct 2–3 supplier interviews.
- [ ] Verify the product name is not already used by a similar product.
- [ ] Review the legal wording before including MSME payment-rule statements.

## 6. Technical Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Hindsight timestamp issues | High | Day 1–2 spike test |
| Delayed memory consolidation | Medium | Prewarm demo bank |
| Groq rate limits | Medium | Prompt caching |
| Band SDK incompatibility | Low | Keep Band integration isolated |
| Incorrect LLM-generated facts | High | Ledger-based validation |
| Evaluation inconsistency | High | Fixed seeds and templates |
| Integration conflicts | High | Module contracts and shared interfaces |
| Scope creep | High | Follow original project scope |

## 7. Security and Safety Assumptions

- No API keys in source code.
- No phone numbers or bank account numbers in Hindsight.
- One memory bank per supplier business.
- Customer memories must be isolated.
- Every outgoing message requires approval.
- No threats or coercive collection language.
- No customer contact outside 09:00–19:00 IST.
- No automatic changes to credit terms.
- No disclosure of one customer's information to another.
- Payment and invoice facts must come from SQLite.

## 8. Out-of-Scope Features

Do not implement these unless the entire team explicitly approves a scope change:

- Real WhatsApp API integration.
- Direct Tally integration.
- OCR of scanned invoices.
- Payment processing.
- Buyer portal submission.
- Multi-user login.
- Mobile-responsive application.
- Dispute agent.
- Automated credit decisions.

## 9. Decision Log

When an open item is resolved, record:

| Date | Item | Decision | Verified by |
|---|---|---|---|
| TBD | Hindsight version | Pending | P1 |
| TBD | Band SDK | Pending | P3 |
| TBD | Groq model IDs | Pending | P1 |
| TBD | Dataset licence | Pending | P2 |
| TBD | Evaluation configuration | Pending | P2 |

## 10. Instructions for AI Coding Assistants

Before implementing an unresolved dependency:

1. Inspect the installed package version.
2. Check the corresponding official documentation.
3. Verify the method names and expected arguments.
4. Write a small isolated test.
5. Record the verified result.
6. Only then implement the full integration.

Never invent SDK methods, API endpoints or configuration variables.

When verification is impossible, create an adapter interface and document the unresolved implementation rather than fabricating a working integration.