# SKELETON AUDIT: Munshi Project

**Date**: 2026-11-06  
**Auditor**: Kiro AI Software Architect  
**Scope**: Backend and frontend skeleton structure against project documentation

---

## Executive Summary

The Munshi skeleton has been created following the documented architecture. **All required modules exist**, but several placeholder files lack proper implementation scaffolding, and some API endpoints have incomplete route coverage. Technology isolation is correctly enforced in the module structure.

**Status**: ⚠️ REQUIRES FIXES - Missing scaffolding for implementation

---

## 1. Module Structure Checklist

| Module | Status | Notes |
|--------|--------|-------|
| `backend/munshi/db/` | ✅ Complete | models.py, session.py, seed.py |
| `backend/munshi/api/` | ⚠️ Partial | 11 route files, missing imports.py |
| `backend/munshi/checks/` | ✅ Complete | gstin.py, rules.py, readiness.py |
| `backend/munshi/memory/` | ✅ Complete | client.py, bank_setup.py, events.py, queries.py, parsing.py, outbox.py |
| `backend/munshi/llm/` | ✅ Complete | groq_client.py, cache.py, json_utils.py |
| `backend/munshi/agents/` | ✅ Complete | policy.py, collector.py, risk.py, drafting.py, prompts/ |
| `backend/munshi/band/` | ✅ Complete | run_agents.py, bridge.py, commands.py |
| `backend/munshi/services/` | ✅ Complete | clock.py, daily_loop.py, whatsapp_link.py |
| `backend/sim/` | ✅ Complete | profiles.py, calibrate.py, world.py, personas.py, scenarios/ |
| `backend/eval/` | ✅ Complete | run_eval.py, metrics.py, report.py, arms/ |
| `backend/scripts/` | ✅ Complete | prewarm_demo_bank.py, spike_one_customer.py |
| `backend/tests/` | ✅ Complete | 6 test files covering rules, readiness, world |

**Missing module**: `backend/munshi/api/imports.py` - Required for `POST /api/import/tally-csv`

---

## 2. API Endpoints Verification

| Endpoint | Path | Status | Notes |
|----------|------|--------|-------|
| POST | /api/import/tally-csv | ❌ MISSING | Required but `api/imports.py` doesn't exist |
| GET | /api/dashboard | ⚠️ Stub | `dashboard.py` exists with stub implementation |
| GET | /api/customers | ⚠️ Stub | `customers.py` exists with stub implementation |
| GET | /api/customers/{id} | ⚠️ Stub | No PATCH endpoint for customer edits |
| PATCH | /api/customers/{id} | ❌ MISSING | Required for owner edits |
| POST | /api/invoices | ⚠️ Stub | `invoices.py` exists |
| POST | /api/invoices/{id}/documents | ⚠️ Stub | Missing multipart upload handler |
| POST | /api/invoices/{id}/check | ⚠️ Stub | |
| POST | /api/invoices/{id}/confirm | ❌ MISSING | Required for resolving Conflict/Uncertain |
| POST | /api/invoices/{id}/send | ❌ MISSING | Required to mark invoice as sent |
| GET | /api/actions?status=DRAFTED | ⚠️ Stub | `actions.py` exists |
| POST | /api/actions/{id}/approve | ⚠️ Stub | |
| POST | /api/actions/{id}/reject | ⚠️ Stub | |
| GET | /api/actions/{id}/explain | ❌ MISSING | Required for "Why this?" panel |
| POST | /api/messages/inbound | ⚠️ Stub | `messages.py` exists |
| POST | /api/payments | ⚠️ Stub | `payments.py` exists |
| GET | /api/risk/alerts | ⚠️ Stub | `risk.py` exists |
| POST | /api/risk/alerts/{id}/ack | ❌ MISSING | Required for acknowledging alerts |
| POST | /api/explain | ❌ MISSING | Required for owner questions |
| POST | /api/sim/reset | ⚠️ Stub | `simulation.py` exists |
| POST | /api/sim/tick | ⚠️ Stub | |
| POST | /api/sim/inject | ⚠️ Stub | |
| GET | /api/eval/results | ⚠️ Stub | `evaluation.py` exists |

**Deficiencies**:
1. Missing `imports.py` for CSV import endpoint
2. Missing `confirm`, `send`, `explain` endpoints in `api/`
3. Missing PATCH endpoint for customer updates
4. Missing ack endpoint for risk alerts
5. Many endpoints have stub implementations only

---

## 3. Database Entities Verification

| Table | Status | Notes |
|-------|--------|-------|
| business | ✅ | Implemented |
| customer | ✅ | Implemented |
| invoice | ✅ | Implemented |
| invoice_document | ✅ | Implemented |
| readiness_check | ✅ | Implemented |
| action | ✅ | Implemented |
| inbound_message | ✅ | Implemented |
| payment | ✅ | Implemented |
| promise | ✅ | Implemented |
| risk_alert | ✅ | Implemented |
| memory_event | ✅ | Implemented |
| sim_run | ✅ | Implemented |

**Note**: DATABASE_DESIGN.md mentions missing UNIQUE constraint on `(customer_id, number)` and CHECK on `amount_paise`. These are documented in comments but not enforced in code.

---

## 4. Technology Isolation Verification

### Hindsight Memory (Memory Module Only)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Hindsight SDK only in `memory/` | ✅ PASS | `memory/client.py` has import placeholder with comment |
| Never in `agents/`, `checks/`, `api/`, `band/` | ✅ PASS | No imports found in those modules |

### Groq LLM (LLM Module Only)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Groq SDK only in `llm/` | ✅ PASS | `llm/groq_client.py` has import placeholder |
| Never in other modules | ✅ PASS | No imports found elsewhere |

### Band SDK (Band Module Only)
| Requirement | Status | Notes |
|-------------|--------|-------|
| Band SDK only in `band/` | ✅ PASS | `band/run_agents.py` has import placeholder |
| External Agent setup only here | ✅ PASS | |

**Conclusion**: ✅ All three technologies are correctly isolated in their modules.

---

## 5. Separation of Concerns

| Component | Location | Status |
|-----------|----------|--------|
| Collector agent | `backend/munshi/agents/collector.py` | ✅ |
| Risk agent | `backend/munshi/agents/risk.py` | ✅ |
| Policy interface | `backend/munshi/agents/policy.py` | ✅ Shared with eval |
| Simulation world | `backend/sim/` | ✅ Separate from app |
| Evaluation arms | `backend/eval/arms/` | ✅ Separate from app |
| Agent prompts | `backend/munshi/agents/prompts/` | ✅ Separate from logic |

**Note**: `agents/policy.py` is shared between app and eval, which is documented in IMPLEMENTATION_ROADMAP.md.

---

## 6. Environment Variables Documentation

| Category | Variables | Status | Notes |
|----------|-----------|--------|-------|
| Hindsight | `HINDSIGHT_API_KEY`, `HINDSIGHT_LOCAL_URL` | ✅ | Documented |
| Groq | `GROQ_API_KEY`, `GROQ_AGENT_MODEL`, `GROQ_CUSTOMER_MODEL` | ✅ | Documented |
| Band | `BAND_API_KEY`, `BAND_ROOM_ID`, `BAND_COLLECTOR_AGENT_ID`, `BAND_RISK_AGENT_ID`, `BAND_WEBHOOK_URL` | ✅ | Documented |
| App | `APP_ENV`, `DEBUG`, `LOG_LEVEL`, `DATABASE_URL`, `SIM_MODE` | ✅ | Documented |
| Frontend | `VITE_API_URL` | ✅ | Documented |

**Missing**: No mention of `HINDSIGHT_LOCAL_URL` in `memory/client.py` comments - needs to reference this.

---

## 7. Four-Developer Independence

| Developer | Focus | Files Owned | Conflict Risk |
|-----------|-------|-------------|---------------|
| P1 (memory) | `backend/munshi/memory/` | client.py, bank_setup.py, events.py, queries.py, parsing.py, outbox.py | Low - isolated module |
| P2 (sim/eval) | `backend/sim/`, `backend/eval/` | All sim and eval files | Low - separate folders |
| P3 (backend/Band) | `backend/munshi/*` | All backend modules except sim/eval | Medium - api/ may need coordination |
| P4 (frontend) | `frontend/` | All frontend files | Low - isolated |

**Recommendation**: Add `frontend/src/api/types.ts` shared types to prevent sync issues.

---

## 8. Documentation Integrity

| Document | Status | Notes |
|----------|--------|-------|
| Original PDF | ✅ Preserved | Unchanged |
| PROJECT_ANALYSIS.md | ✅ Created | Contains full analysis |
| ARCHITECTURE.md | ✅ Updated | Hindsight/Band/Groq sections added |
| DEVELOPMENT_RULES.md | ✅ Updated | Integration rules added |
| IMPLEMENTATION_ROADMAP.md | ✅ Updated | Technology verification phases added |
| API_DOCUMENTATION.md | ✅ Preserved | Unchanged |
| DATABASE_DESIGN.md | ✅ Preserved | Unchanged |
| MODULE_CONTRACTS.md | ✅ Created | Module contracts added |
| EXTERNAL_INTEGRATIONS.md | ✅ Created | Hindsight/Band/Groq integration specs |
| INTEGRATION_VERIFICATION.md | ✅ Created | Day 1-2 verification tests |

**All documentation preserved and enhanced**.

---

## 9. Missing Scaffolding Fixes Required

### Critical Fixes (Before Implementation Can Begin)

1. **Add `backend/munshi/api/imports.py`** for `POST /api/import/tally-csv` endpoint
2. **Add `confirm` endpoint** to handle Conflict/Uncertain resolution
3. **Add `send` endpoint** to mark invoice as sent
4. **Add `explain` endpoint** to provide evidence for drafts
5. **Add `PATCH /api/customers/{id}`** for owner edits
6. **Add `ack` endpoint** for risk alert acknowledgment
7. **Add multipart upload** to document endpoint handlers
8. **Add UNIQUE constraint and CHECK** to invoice model (documented in code comments)

### Medium Priority Fixes

9. **Add missing route in `backend/munshi/api/__init__.py`** to import imports.py
10. **Add `band/webhook.py`** for Band webhook events
11. **Add `frontend/src/api/types.ts`** shared types file
12. **Add `backend/munshi/api/explain.py`** separate module for explain endpoint

---

## 10. Unresolved Decisions

| Decision | Context | Required Action |
|----------|---------|-----------------|
| Hindsight SDK version | PDF says "Pin on Day 1" | Verify against installed version |
| Groq function-calling support | PDF marked `# VERIFY` | Test on Day 2 |
| Band SDK class names | PDF marked `# VERIFY` | Verify against installed version |
| Memory event ID format | PDF says `evt_<ulid or counter>` | Decide before implementation |
| CSV import columns | README calls it "open assumption" | Finalize before implementation |

---

## 11. Remaining Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hindsight timestamps not honored | Medium | High | Use date-aware reflect prompts as fallback |
| Band SDK differs from docs | Medium | High | Web fallback available |
| Groq function-calling fails for qwen3-32b | Medium | Medium | Use JSON mode fallback |
| Missing API endpoints delay implementation | High | High | Fixes required before implementation |
| UNIQUE constraint missing | Low | Medium | Add before production |

---

## 12. Summary of Changes Made

### Files Created (100+ files)
- All backend modules with placeholder implementations
- Frontend structure with React pages and components
- Documentation files (MODULE_CONTRACTS.md, EXTERNAL_INTEGRATIONS.md, INTEGRATION_VERIFICATION.md)

### Files Modified (5 files)
- `ARCHITECTURE.md` - Added Hindsight/Band/Groq integration sections
- `IMPLEMENTATION_ROADMAP.md` - Added Day 1-2 technology verification phases
- `DEVELOPMENT_RULES.md` - Added integration boundaries and rules
- `MODULE_CONTRACTS.md` - Created new file with module contracts
- `AI_CREDIT_USAGE_PLAN.md` - Created new file with cost estimates
- `AGENTS.md` - Updated with technology requirements

---

## 13. Audit Conclusion

**Skeleton Quality**: ⭐⭐⭐☆☆ (3/5)

**Strengths**:
- ✅ All required modules exist with correct boundaries
- ✅ Technology isolation correctly enforced
- ✅ Database schema complete with 12 tables
- ✅ Separation of concerns maintained
- ✅ Documentation comprehensive and enhanced

**Weaknesses**:
- ⚠️ 7 critical API endpoints missing or incomplete
- ⚠️ Placeholder files need implementation scaffolding
- ⚠️ Missing integration files (imports.py, explain.py, webhook.py)
- ⚠️ Frontend needs shared types file

**Verdict**: Skeleton is **structurally correct** but **not yet ready for implementation**. Critical API endpoints must be added before implementation can begin.

---

## Next Steps

1. **Implement missing API files** (imports.py, confirm, send, explain, patch customer, ack risk, explain)
2. **Add database constraints** (UNIQUE, CHECK)
3. **Create shared types** for frontend
4. **Add webhook handler** for Band messages
5. **Run Day 1-2 verification** per INTEGRATION_VERIFICATION.md

---

## Files Audited

| Type | Files |
|------|-------|
| PDF | Munshi — Complete Project Documentation.pdf |
| Markdown | README.md, PROJECT_ANALYSIS.md, ARCHITECTURE.md, DEVELOPMENT_RULES.md, IMPLEMENTATION_ROADMAP.md, API_DOCUMENTATION.md, DATABASE_DESIGN.md, MODULE_CONTRACTS.md |
| New Docs | EXTERNAL_INTEGRATIONS.md, INTEGRATION_VERIFICATION.md |
| Backend | 80+ Python files in munshi/, sim/, eval/, scripts/, tests/ |
| Frontend | 30+ TypeScript/TSX files in src/ |

---

**End of Audit**
