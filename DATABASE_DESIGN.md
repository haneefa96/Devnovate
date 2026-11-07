# DATABASE DESIGN

SQLite via SQLModel (`backend/munshi/db/models.py` already contains the schema). SQLite is the **source of truth** for amounts, dates and statuses. Hindsight (knowledge) is a second store, described in ARCHITECTURE.md §4; it is never asked for numbers. All `*_at` / `*_on` values hold **simulated time** in demo and evaluation runs.

## Tables
`PK` primary key, `FK` foreign key, `?` nullable.

| Table | Fields (type) | Notes / constraints |
|---|---|---|
| **business** | id PK int; name str; gstin str; state_code str(2); msme_registered bool; bank_id str | One row per supplier. `bank_id` names its Hindsight bank. Prototype has one row. |
| **customer** | id PK; business_id FK→business; name; gstin; state_code; credit_days int; po_required bool; required_docs JSON list; contact_name; contact_role; contact_phone; risk_level enum; risk_updated_at? | `po_required`/`required_docs` change only on owner confirmation. Phone stays here only. |
| **invoice** | id PK; customer_id FK; number str; issue_date date; due_date date; amount_paise int; po_number?; status enum; readiness? enum; created_at | UNIQUE (customer_id, number) — enforced by rule R7 first, constraint as backstop. |
| **invoice_document** | id PK; invoice_id FK; doc_type enum; file_path; uploaded_at | doc_type: INVOICE_PDF, PO_COPY, SIGNED_CHALLAN, GRN, EWAY_BILL, OTHER |
| **readiness_check** | id PK; invoice_id FK; run_at; result enum; findings JSON | finding = {code, source RULE\|MEMORY, message, evidence_ids} |
| **action** | id PK; invoice_id FK; customer_id FK; kind enum; channel; recipient; body; attachments JSON; planned_for?; status enum; decided_by?; decided_at?; sent_at?; memory_event_id? | Collector drafts/sent messages. Drafts are never retained until SENT. |
| **inbound_message** | id PK; customer_id FK; invoice_id? FK; channel; sender_name; body; received_at; memory_event_id? | From simulator or pasted by owner. |
| **payment** | id PK; invoice_id FK; amount_paise int; paid_on date; reference?; memory_event_id? | Part payments allowed (sum ≥ amount → PAID). |
| **promise** | id PK; invoice_id FK; promised_by str; promised_date date; kept bool? | `kept` NULL until the date passes. |
| **risk_alert** | id PK; customer_id FK; from_level; to_level; signals JSON; suggestion?; evidence JSON; status enum; created_at | status OPEN, ACKNOWLEDGED, DISMISSED |
| **memory_event** | id PK str (`evt_…`); kind; customer_id? FK; invoice_id? FK; occurred_on date; content_hash; retained_at?; hindsight_document_id? | Audit link + outbox: `retained_at IS NULL` = retry pending. |
| **sim_run** | id PK; arm str (A/B/C); seed int; config JSON; metrics JSON; started_at; finished_at? | Evaluation only. |

## Enumerations
- invoice.status: DRAFT, READY, SENT, HELD, PARTLY_PAID, PAID, DISPUTED, WRITTEN_OFF
- invoice.readiness: READY, BLOCKER, CONFLICT, UNCERTAIN
- action.kind: REMINDER, DOC_SEND, THANK_YOU, ESCALATION_REQUEST
- action.status: DRAFTED, APPROVED, EDITED, REJECTED, SENT
- customer.risk_level: NORMAL, WATCH, HIGH

## Relationships
```
business 1─* customer 1─* invoice 1─* invoice_document
                │             ├─* readiness_check
                │             ├─* action
                │             ├─* payment
                │             └─* promise
                ├─* inbound_message
                ├─* risk_alert
                └─* memory_event (also optionally → invoice)
sim_run (standalone)
```

## Constraints and conventions
- Money: integer paise only. Dates: simulated clock. Enums stored as strings and constrained to their documented values.
- Deleting a customer must also delete their Hindsight memories by document id (`memory_event.hindsight_document_id`). Implement as a service function; no ON DELETE CASCADE to memory.
- Status transitions: action DRAFTED → APPROVED/EDITED → SENT or DRAFTED → REJECTED (first decision wins; later attempts get 409).
- No migrations tool in the prototype: tables are created at startup (`SQLModel.metadata.create_all`); `make seed` rebuilds the demo DB. Add Alembic only if the schema must survive changes.

## Sample (abridged SQL equivalent)
```sql
CREATE TABLE invoice (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customer(id),
  number TEXT NOT NULL,
  issue_date DATE NOT NULL, due_date DATE NOT NULL,
  amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
  po_number TEXT, status TEXT NOT NULL DEFAULT 'DRAFT',
  readiness TEXT, created_at DATETIME NOT NULL,
  UNIQUE (customer_id, number)
);
```
Note: the model file does not yet declare the UNIQUE constraint or CHECK; add them when implementing the DB module (`db/models.py` owner).
