# API DOCUMENTATION

Base path `/api`. JSON in/out (except CSV and file uploads: multipart). **Authentication: none** in the prototype (single demo business). Money = integer paise. Dates ISO 8601; times carry the IST offset (simulated time in demo/eval). Frontend polls every 3 s.

**Error format (assumption, applies everywhere):**
```json
{"error": {"code": "NOT_FOUND", "message": "Customer 12 not found", "details": {}}}
```
Codes: `VALIDATION_ERROR` (422), `NOT_FOUND` (404), `CONFLICT` (409, e.g. action already decided), `MEMORY_UNAVAILABLE` (503, only for reflect-dependent reads; writes degrade to the outbox), `SIM_DISABLED` (403 when `SIM_MODE=false`), `INTERNAL` (500).

**Write rule:** every state-changing endpoint writes SQLite first, then retains in Hindsight; if retain fails the response is still success and `memory_event.retained_at` stays NULL for retry.

Shared shapes:
- `Finding`: `{code, source: "RULE"|"MEMORY", message, evidence_ids: []}`
- `Readiness`: `READY|BLOCKER|CONFLICT|UNCERTAIN`; `RiskLevel`: `NORMAL|WATCH|HIGH`
- `Evidence`: `{id, date, text, event_id}`

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | /api/import/tally-csv | Import customers + open invoices |
| GET | /api/dashboard | Totals and counts |
| GET | /api/customers | List with risk level |
| GET | /api/customers/{id} | Record, playbook, beliefs, timeline |
| PATCH | /api/customers/{id} | Owner edits contact, po_required, required_docs |
| POST | /api/invoices | Create + readiness check |
| POST | /api/invoices/{id}/documents | Upload document with doc_type |
| POST | /api/invoices/{id}/check | Re-run readiness |
| POST | /api/invoices/{id}/confirm | Resolve Conflict/Uncertain; retained |
| POST | /api/invoices/{id}/send | Mark sent (after readiness) |
| GET | /api/actions?status=DRAFTED | Approvals inbox |
| POST | /api/actions/{id}/approve | Approve (optional edited text) |
| POST | /api/actions/{id}/reject | Reject (optional reason) |
| GET | /api/actions/{id}/explain | Evidence behind a draft |
| POST | /api/messages/inbound | Record customer reply |
| POST | /api/payments | Record payment |
| GET | /api/risk/alerts | Open alerts |
| POST | /api/risk/alerts/{id}/ack | Acknowledge/dismiss |
| POST | /api/explain | Plain-language question |
| POST | /api/sim/reset · /tick?days=N · /inject | Simulator (SIM_MODE only) |
| GET | /api/eval/results | Evaluation results |

## Details

### POST /api/import/tally-csv
multipart `file`. CSV column layout is an **open assumption** (see ASSUMPTIONS_AND_RISKS): expected columns `customer_name, gstin, state_code, invoice_number, issue_date, due_date, amount_rupees, po_number`.
`200 {"customers_created": 12, "invoices_created": 40, "rows_skipped": [{"row": 7, "reason": "bad GSTIN"}]}`

### GET /api/dashboard
`200 {"total_receivable_paise": 0, "overdue_paise": 0, "at_risk_customers": [{"id":1,"name":"","risk_level":"WATCH"}], "pending_drafts": 0, "blockers_caught_this_month": 0}`

### GET /api/customers
`200 [{"id":1,"name":"Reddy Traders","risk_level":"HIGH","open_invoices":2,"overdue_paise":4820000}]`

### GET /api/customers/{id}
```json
{"customer": {"id":1,"name":"","gstin":"","state_code":"36","credit_days":30,"po_required":true,
              "required_docs":["SIGNED_CHALLAN"],"contact_name":"Rahul","contact_role":"Payables","risk_level":"HIGH"},
 "playbook": {"text": "…", "updating": false},
 "beliefs": [{"text":"Pays on the 5th if reminded before it","trend":"weakening","evidence_count":4,"evidence":[Evidence]}],
 "timeline": [{"date":"2026-03-03","kind":"REMINDER|INVOICE|REPLY|PAYMENT|CONTACT_CHANGE","text":""}]}
```
`playbook` and `beliefs` may be empty with `updating: true` while Hindsight consolidates. Phone numbers are not returned.

### PATCH /api/customers/{id}
Body (any subset): `{"contact_name","contact_role","contact_phone","po_required","required_docs":[DocType],"credit_days"}` → `200` updated customer. Retains an owner-confirmation event when contact/requirements change.

### POST /api/invoices
`{"customer_id":1,"number":"INV-1042","issue_date":"2026-03-01","due_date":"2026-03-31","amount_paise":4820000,"po_number":"4471"}`
`201 {"id":55,"status":"DRAFT","readiness":"BLOCKER","findings":[Finding]}` · Errors: 422, 409 (duplicate number is reported as a finding R7, not an error).

### POST /api/invoices/{id}/documents
multipart `file`, `doc_type` ∈ INVOICE_PDF, PO_COPY, SIGNED_CHALLAN, GRN, EWAY_BILL, OTHER → `201 {"id":9,"doc_type":"SIGNED_CHALLAN"}`

### POST /api/invoices/{id}/check
No body → `200 {"readiness":"READY","findings":[Finding],"memory_pending":false}`

### POST /api/invoices/{id}/confirm
`{"finding_code":"PO_REQUIRED","decision":"CONFIRM_NEW"|"KEEP_OLD","note":""}` → `200 {"readiness":"…","customer_updated":true}`. Confirmed learned requirements are written to the customer record (become R5/R9).

### POST /api/invoices/{id}/send
Allowed only if readiness is READY (or owner-overridden with `{"override": true}`) → `200 {"status":"SENT","memory_event_id":"evt_…"}`; `409` if readiness is BLOCKER without override.

### GET /api/actions?status=DRAFTED
`200 [{"id":231,"invoice_id":55,"customer":"Reddy Traders","kind":"REMINDER","recipient":"Rahul","channel":"WHATSAPP","body":"…","planned_for":"2026-03-03T10:30:00+05:30","attachments":[],"status":"DRAFTED","why":"one-line evidence"}]`

### POST /api/actions/{id}/approve
`{"edited_body": null, "decided_by": "owner"}` →
`200 {"id":231,"status":"SENT","sent_at":"2026-03-03T10:30:00+05:30","whatsapp_link":"https://wa.me/91XXXXXXXXXX?text=...","memory_event_id":"evt_0193"}`
`409 CONFLICT` if already decided (first decision wins; Band and web both use this endpoint). In simulator mode, `whatsapp_link` is null and the message goes to the simulated customer.

### POST /api/actions/{id}/reject
`{"reason": "optional", "decided_by":"owner"}` → `200 {"id":231,"status":"REJECTED"}`. Reason retained as an owner note.

### GET /api/actions/{id}/explain
`200 {"summary":"…","evidence":[Evidence]}` (from reflect `based_on`).

### POST /api/messages/inbound
`{"customer_id":1,"invoice_id":null,"channel":"WHATSAPP","sender_name":"Priya","body":"Rahul now handles payables"}` → `201 {"id":77,"memory_event_id":"evt_…","risk_check_queued":true}`

### POST /api/payments
`{"invoice_id":55,"amount_paise":4820000,"paid_on":"2026-03-05","reference":"UTR…"}` → `201 {"id":12,"invoice_status":"PAID","days_late":4}`

### GET /api/risk/alerts
`200 [{"id":3,"customer_id":1,"from_level":"WATCH","to_level":"HIGH","signals":["missed two payment runs"],"suggestion":"hold next dispatch or ask advance","evidence":[Evidence],"status":"OPEN","created_at":"…"}]`

### POST /api/risk/alerts/{id}/ack
`{"status":"ACKNOWLEDGED"|"DISMISSED"}` → `200` alert.

### POST /api/explain
`{"customer_id":1,"question":"why is Reddy at High?"}` → `200 {"answer":"…","evidence":[Evidence]}`; says so if there is no evidence.

### Simulator
- `POST /api/sim/reset {"scenario":"demo"}` → `200 {"clock":"2026-01-01"}`
- `POST /api/sim/tick?days=N` → `200 {"clock":"…","drafts_created":2,"alerts_raised":1}`
- `POST /api/sim/inject {"customer_id":1,"type":"CONTACT_CHANGE|REQUIREMENT_CHANGE|DISTRESS_START","payload":{}}` → `200 {"ok":true}`

### GET /api/eval/results
`200 {"git_hash":"","arms":{"A":{"avg_days_late_by_month":[],"metrics":{}},"B":{…},"C":{…}},"test_months":[4,5,6],"seeds":[1,2,3]}`
