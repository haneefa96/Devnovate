# MUNSHI — MODULE CONTRACTS

## 1. Purpose

This document defines the responsibilities, inputs, outputs, dependencies, ownership and integration rules for every major module in Munshi.

The objective is to allow four developers or multiple AI coding assistants to implement different modules independently without creating integration conflicts.

**Core principle:** Every module must follow its defined contract. A developer must not independently change another module's interfaces.

## 2. Overall System Structure

Munshi consists of:

- React frontend.
- FastAPI backend.
- SQLite database using SQLModel.
- Hindsight persistent memory.
- Groq-hosted LLMs.
- Band multi-agent collaboration.
- Customer simulation engine.
- Evaluation engine.

All application surfaces communicate through the FastAPI backend.

The agents are backend modules, not separate business-logic services.

## 3. Module Ownership

| Module | Main responsibility | Owner |
|---|---|---|
| Memory | Hindsight integration, retain, recall, reflect and beliefs | P1 |
| Agents | Collector and Risk decision logic | P1 |
| Simulator | Customer behaviour and deterministic outcomes | P2 |
| Evaluation | A/B/C comparison and metrics | P2 |
| Database | SQLModel entities and persistence | P3 |
| API | FastAPI endpoints and validation | P3 |
| Checks | GSTIN and invoice readiness rules | P3 |
| Band | Agent connections and message bridge | P3 |
| Services | Daily workflow and clock | P3 |
| Frontend | Seven application screens and shared components | P4 |
| Documentation | User guides, architecture and demo documentation | P4 |

## 4. Module Contracts

### 4.1 Database Module

Location: `backend/munshi/db/`

Responsibilities:
- Define all 12 database tables.
- Manage database connections.
- Provide CRUD operations.
- Store invoice amounts in paise.
- Store dates and statuses.
- Maintain relationships and constraints.
- Support deterministic simulation timestamps.

Input:
- Validated application data.
- Customer, invoice, payment, action and event information.

Output:
- Persisted SQLModel entities.
- Retrieved records.
- Updated statuses.

Important rules:
- SQLite is the source of truth for financial amounts, invoice dates and statuses.
- Hindsight must never be used to retrieve authoritative financial values.
- Use transactions for related database changes.
- Never store secrets in the database.

Expected files:
- `models.py`
- `session.py`
- `seed.py`

### 4.2 Memory Module

Location: `backend/munshi/memory/`

Responsibilities:
- Connect to Hindsight.
- Create and configure business-specific memory banks.
- Retain business events.
- Recall customer-specific facts.
- Reflect on customer behaviour.
- Retrieve mental models and observations.
- Track evidence behind recommendations.
- Handle failed retain operations through an outbox.

Input:
- Customer ID.
- Event ID.
- Event type.
- Absolute event date.
- Event description.
- Customer-specific query.

Output:
- Retained memory event.
- Retrieved facts.
- Reflect-generated text.
- Evidence IDs.
- Customer playbook information.

Integration rules:
- Only `memory/client.py` may import the Hindsight SDK.
- Every customer query must be scoped using customer tags.
- Use one Hindsight bank per supplier business.
- Use a separate bank for every evaluation run.
- Never retain phone numbers or bank account numbers.
- Never retain unsent drafts.
- Retain an outgoing action only after owner approval and successful delivery or handoff.
- Every recommendation must include evidence or explicitly state that evidence is unavailable.

### 4.3 Collector Agent

Location: `backend/munshi/agents/collector.py`

Responsibilities:
- Identify invoices requiring attention.
- Retrieve customer payment behaviour.
- Determine appropriate follow-up timing.
- Identify the appropriate contact.
- Determine relevant attachments.
- Generate follow-up plans.
- Create drafts for owner approval.

Input:
- Customer record.
- Invoice record.
- Current date or simulated date.
- Hindsight memory results.
- Previous reminder history.

Output:

```json
{
  "send_on": "2026-03-03",
  "recipient": "Priya",
  "channel": "WhatsApp",
  "attachments": [],
  "tone": "gentle",
  "reason": "Reminder before the usual payment run",
  "evidence_ids": []
}
```

Rules:
- Never send messages independently.
- Respect business hours: 09:00–19:00 IST.
- Do not exceed two reminders per invoice per week.
- Never invent payment information.
- Use ledger data for invoice amounts and dates.
- If structured output fails twice, use the documented safe fallback and label it as having no memory support.

### 4.4 Risk Agent

Location: `backend/munshi/agents/risk.py`

Responsibilities:
- Monitor customer payment behaviour.
- Identify missed payment runs.
- Identify broken promises.
- Detect distress signals.
- Detect contact changes.
- Monitor weakening or stale beliefs.
- Generate risk alerts.

Input:
- Customer record.
- Payment history.
- Promise history.
- Hindsight observations.
- Relevant customer messages.

Output:

```json
{
  "level": "HIGH",
  "signals": [
    "Missed two payment runs",
    "Payment behaviour weakening"
  ],
  "suggestion": "Review the next dispatch",
  "evidence_ids": []
}
```

Risk classification:
- NORMAL: No significant risk signals.
- WATCH: One meaningful warning signal.
- HIGH: Two or more warning signals.

Rules:
- The risk classification threshold is computed in code.
- The LLM may identify conversational warning signals but cannot independently change credit terms.
- The owner makes all final business decisions.
- Every alert must include its supporting signals and evidence.

### 4.5 Readiness Check Module

Location: `backend/munshi/checks/`

Responsibilities:
- Validate invoice information.
- Execute fixed GSTIN and invoice rules.
- Retrieve learned customer requirements.
- Compare requirements against uploaded documents.
- Identify conflicts and uncertainty.

Input:
- Invoice details.
- Customer details.
- Attached document types.
- Memory findings.

Output:

```json
{
  "result": "BLOCKER",
  "findings": [
    {
      "code": "SIGNED_CHALLAN",
      "source": "MEMORY",
      "message": "Customer previously required a signed challan",
      "evidence_ids": []
    }
  ]
}
```

Possible results:
- READY
- BLOCKER
- CONFLICT
- UNCERTAIN

Fixed rules:
- R1: GSTIN format.
- R2: GSTIN checksum.
- R3: GSTIN match.
- R4: State code match.
- R5: PO requirement.
- R6: PO amount.
- R7: Duplicate invoice.
- R8: Due date.
- R9: Required documents.

Important:
- An LLM must never decide whether a GSTIN, amount or invoice number is valid.
- Learned requirements must have supporting evidence.
- Owner-confirmed requirements become structured customer rules.

### 4.6 API Module

Location: `backend/munshi/api/`

Responsibilities:
- Expose backend functionality.
- Validate incoming requests.
- Call appropriate services.
- Return consistent JSON responses.
- Handle exceptions and error responses.

All API routes must:
- Use the `/api` prefix.
- Use JSON request and response bodies.
- Follow the API_DOCUMENTATION.md contract.
- Avoid directly implementing business logic inside route handlers.

The API must not directly import the Hindsight SDK.

### 4.7 Band Integration Module

Location: `backend/munshi/band/`

Responsibilities:
- Connect Collector and Risk agents.
- Receive owner commands.
- Parse approval, edit and rejection commands.
- Forward commands to backend endpoints.
- Post drafts and alerts.
- Support plain-language questions through the explain endpoint.

Message conventions:

- `[DRAFT A-231]`
- `approve A-231`
- `edit A-231: <text>`
- `reject A-231`
- `[RISK]`

Rules:
- Band is a collaboration interface, not a second source of truth.
- Approval decisions must use the same backend endpoint as the web interface.
- First valid approval decision wins.
- If Band is unavailable, the web interface must remain functional.

### 4.8 Simulator Module

Location: `backend/munshi/sim/`

Responsibilities:
- Generate simulated customer profiles.
- Maintain hidden customer traits.
- Simulate invoice payment behaviour.
- Simulate customer replies.
- Inject changes in contacts and requirements.
- Simulate financial distress.
- Maintain deterministic outcomes.

Important:
- Payment outcomes must be determined by fixed seeded rules.
- LLMs may generate customer reply wording only.
- LLMs must not determine whether a payment succeeds.
- Same seed and same configuration must produce identical outcomes.

### 4.9 Evaluation Module

Location: `backend/eval/`

Responsibilities:
- Execute evaluation versions A, B and C.
- Use identical scenarios and seeds.
- Calculate evaluation metrics.
- Generate JSON results.
- Generate charts.
- Produce a reproducible evaluation report.

Versions:
- A: Fixed schedule without memory.
- B: Structured database memory.
- C: Hindsight-based memory.

Evaluation must measure months 4–6 after months 1–3 of learning.

Never change the evaluation methodology independently of the simulator.

### 4.10 Frontend Module

Location: `frontend/src/`

Responsibilities:
- Display dashboard information.
- Display customer playbooks.
- Create invoices.
- Display readiness findings.
- Display approval drafts.
- Display risk alerts.
- Provide simulation controls.
- Display evaluation charts.

Pages:
- Dashboard
- Customer
- New Invoice
- Approvals
- Risk
- Simulation Console
- Evaluation

Rules:
- Use typed API functions.
- Do not access SQLite or Hindsight directly.
- Do not implement business rules in frontend code.
- All financial and risk calculations must come from the backend.
- Use Indian currency formatting and IST dates.

## 5. Integration Contracts

| From | To | Communication |
|---|---|---|
| Frontend | FastAPI | HTTP JSON |
| FastAPI | SQLite | SQLModel |
| FastAPI | Memory | MemoryStore interface |
| Collector | Memory | Recall and reflect |
| Risk | Memory | Recall and reflect |
| Readiness | Memory | Customer requirements |
| Agents | Groq | LLM client |
| Backend | Band | Band bridge |
| Simulator | Backend | Shared services and database |
| Evaluation | Policy interface | Same business decision interface |
| Frontend | Evaluation API | HTTP JSON |

## 6. Shared Interfaces

The following interfaces must be agreed upon before parallel development:

1. Database model names and field names.
2. API request and response schemas.
3. Readiness result structure.
4. FollowUpPlan structure.
5. RiskAssessment structure.
6. Memory evidence ID structure.
7. Simulator event structure.
8. Evaluation metric names.

Changes to these contracts require agreement from affected module owners.

## 7. Module Completion Checklist

Before declaring any module complete:

- [ ] Responsibilities implemented.
- [ ] Expected input format followed.
- [ ] Expected output format followed.
- [ ] Unit tests written.
- [ ] Error handling implemented.
- [ ] No unrelated modules modified.
- [ ] No hardcoded secrets.
- [ ] Integration contract followed.
- [ ] README or module documentation updated.
- [ ] Changes committed to Git.

## 8. Integration Rule

Do not integrate unfinished modules directly into the main application.

Each module must first pass its independent tests.

After testing, merge the module into the shared development branch and run integration tests.

The backend API and shared data models are the central integration contracts for the project.