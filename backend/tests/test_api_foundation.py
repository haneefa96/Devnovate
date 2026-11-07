"""
Munshi - API Foundation Tests

Tests for FastAPI application and API foundation:
- Application setup & configuration
- Dependency injection & database session management
- Health-check endpoint (/health, /api/health)
- CORS headers for local frontend development
- Documented error format {"error": {"code": ..., "message": ..., "details": ...}}
- 404 Not Found, 409 Conflict, 422 Validation Error handling
- API endpoints contract compliance (API_DOCUMENTATION.md)
"""

import io
from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from munshi.config import clock
from munshi.db.models import (
    Action,
    ActionKind,
    ActionStatus,
    Business,
    Customer,
    CustomerRiskLevel,
    Invoice,
    InvoiceReadiness,
    InvoiceStatus,
    RiskAlert,
    RiskAlertStatus,
)
from munshi.db.seed import seed_demo_data
from munshi.db.session import get_session, init_db, reset_db
from munshi.main import app


@pytest.fixture(name="client")
def fixture_client():
    """TestClient with an isolated in-memory SQLite database."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)

    def _override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session

    with Session(test_engine) as session:
        seed_demo_data(session)

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    app.dependency_overrides.clear()
    reset_db(test_engine)


# ─── 1. Health Checks & Metadata ──────────────────────────────────────────────

def test_health_check(client):
    """Test the single health-check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert client.get("/api/health").status_code == 404


def test_documented_api_routes_are_registered():
    """Register every documented route without adding undocumented API routes."""
    routes = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if path.startswith("/api/")
    }
    expected = {
        ("POST", "/api/import/tally-csv"),
        ("GET", "/api/dashboard"),
        ("GET", "/api/customers"),
        ("GET", "/api/customers/{customer_id}"),
        ("PATCH", "/api/customers/{customer_id}"),
        ("POST", "/api/invoices"),
        ("POST", "/api/invoices/{invoice_id}/documents"),
        ("POST", "/api/invoices/{invoice_id}/check"),
        ("POST", "/api/invoices/{invoice_id}/confirm"),
        ("POST", "/api/invoices/{invoice_id}/send"),
        ("GET", "/api/actions"),
        ("POST", "/api/actions/{action_id}/approve"),
        ("GET", "/api/actions/{action_id}/handoff"),
        ("POST", "/api/actions/{action_id}/confirm-delivery"),
        ("POST", "/api/actions/{action_id}/reject"),
        ("GET", "/api/actions/{action_id}/explain"),
        ("POST", "/api/messages/inbound"),
        ("POST", "/api/payments"),
        ("GET", "/api/risk/alerts"),
        ("POST", "/api/risk/alerts/{alert_id}/ack"),
        ("POST", "/api/explain"),
        ("POST", "/api/sim/reset"),
        ("POST", "/api/sim/tick"),
        ("POST", "/api/sim/inject"),
        ("GET", "/api/eval/results"),
    }
    assert routes == expected


def test_cors_headers(client):
    """Test CORS headers allow local development frontend."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    r = client.options("/api/dashboard", headers=headers)
    assert r.status_code in (200, 204)
    assert "access-control-allow-origin" in r.headers


# ─── 2. Error Handling Format & Validation ────────────────────────────────────

def test_404_error_format(client):
    """Test 404 Not Found returns documented error envelope."""
    r = client.get("/api/customers/999999")
    assert r.status_code == 404
    data = r.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "Customer 999999 not found" in data["error"]["message"]


def test_422_validation_error_format(client):
    """Test 422 Unprocessable Entity returns VALIDATION_ERROR code."""
    # Amount paise must be positive (> 0)
    invalid_invoice = {
        "customer_id": 1,
        "number": "INV-TEST-ERR",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-31",
        "amount_paise": -500,  # Invalid
    }
    r = client.post("/api/invoices", json=invalid_invoice)
    assert r.status_code == 422
    data = r.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]


def test_internal_error_format(client):
    def failing_session():
        raise RuntimeError("test database failure")
        yield

    app.dependency_overrides[get_session] = failing_session
    response = client.get("/api/dashboard")
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL",
            "message": "Internal server error",
            "details": {},
        }
    }


def test_409_conflict_error(client):
    """Test 409 Conflict when approving an already-decided action."""
    # Action 1 is DRAFTED in seed data
    approve_payload = {"decided_by": "owner"}
    r1 = client.post("/api/actions/1/approve", json=approve_payload)
    assert r1.status_code == 200

    # Second approval attempt must return 409 CONFLICT
    r2 = client.post("/api/actions/1/approve", json=approve_payload)
    assert r2.status_code == 409
    data = r2.json()
    assert "error" in data
    assert data["error"]["code"] == "CONFLICT"


# ─── 3. Dashboard API ─────────────────────────────────────────────────────────

def test_get_dashboard(client):
    """Test GET /api/dashboard returns summary totals and counts."""
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "total_receivable_paise" in data
    assert "overdue_paise" in data
    assert "at_risk_customers" in data
    assert "pending_drafts" in data
    assert "blockers_caught_this_month" in data
    assert isinstance(data["at_risk_customers"], list)


# ─── 4. Customers API ─────────────────────────────────────────────────────────

def test_list_and_get_customers(client):
    """Test GET /api/customers and GET /api/customers/{id}."""
    r = client.get("/api/customers")
    assert r.status_code == 200
    custs = r.json()
    assert len(custs) == 3
    # Check fields in list response
    c1 = custs[0]
    assert "id" in c1
    assert "name" in c1
    assert "risk_level" in c1
    assert "open_invoices" in c1
    assert "overdue_paise" in c1

    # Detail view
    r_detail = client.get(f"/api/customers/{c1['id']}")
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert "customer" in detail
    assert "playbook" in detail
    assert "beliefs" in detail
    assert "timeline" in detail
    # Phone numbers are not returned in customer detail
    assert "contact_phone" not in detail["customer"]


def test_patch_customer(client):
    """Test PATCH /api/customers/{id} updates record and retains owner confirmation."""
    patch_payload = {
        "contact_name": "Vikram",
        "contact_role": "VP Finance",
        "po_required": True,
        "credit_days": 40,
    }
    r = client.patch("/api/customers/1", json=patch_payload)
    assert r.status_code == 200
    updated = r.json()
    assert updated["contact_name"] == "Vikram"
    assert updated["contact_role"] == "VP Finance"
    assert updated["credit_days"] == 40

    invalid_docs = client.patch(
        "/api/customers/1",
        json={"required_docs": ["UNDOCUMENTED_DOC_TYPE"]},
    )
    assert invalid_docs.status_code == 422
    assert invalid_docs.json()["error"]["code"] == "VALIDATION_ERROR"


# ─── 5. Invoices API ──────────────────────────────────────────────────────────

def test_create_invoice_and_readiness(client):
    """Test POST /api/invoices creates invoice and runs readiness check."""
    payload = {
        "customer_id": 1,
        "number": "INV-NEW-99",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-31",
        "amount_paise": 4820000,
        "po_number": "PO-99",
        "invoice_gstin": "36FGHIJ1234K5Z6",
        "po_amount_paise": 4820000,
    }
    r = client.post("/api/invoices", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "DRAFT"
    assert "readiness" in data
    assert "findings" in data
    assert data["invoice_gstin"] == payload["invoice_gstin"]
    assert data["po_amount_paise"] == payload["po_amount_paise"]
    inv_id = data["id"]

    # Re-run check
    r_check = client.post(f"/api/invoices/{inv_id}/check")
    assert r_check.status_code == 200
    check_data = r_check.json()
    assert "readiness" in check_data
    assert "findings" in check_data

    # Send blocked invoice without override -> 409
    if data["readiness"] == "BLOCKER":
        r_send_fail = client.post(f"/api/invoices/{inv_id}/send", json={"override": False})
        assert r_send_fail.status_code == 409

    # Send with override=true -> 200
    r_send_ok = client.post(f"/api/invoices/{inv_id}/send", json={"override": True})
    assert r_send_ok.status_code == 200
    assert r_send_ok.json()["status"] == "SENT"


def test_upload_invoice_document(client, tmp_path, monkeypatch):
    """Test POST /api/invoices/{id}/documents uploads document file."""
    from munshi.api import invoices

    monkeypatch.setattr(invoices, "_UPLOAD_DIR", tmp_path / "uploads")
    file_bytes = b"%PDF-1.4 test document content"
    files = {"file": ("signed_challan.pdf", io.BytesIO(file_bytes), "application/pdf")}
    data = {"doc_type": "SIGNED_CHALLAN"}

    r = client.post("/api/invoices/1/documents", data=data, files=files)
    assert r.status_code == 201
    resp = r.json()
    assert resp["doc_type"] == "SIGNED_CHALLAN"
    assert "id" in resp


def test_tally_csv_import(client):
    """Test POST /api/import/tally-csv imports customers and invoices."""
    csv_content = (
        "customer_name,gstin,state_code,invoice_number,issue_date,due_date,amount_rupees,po_number\n"
        "Modern Steel,27AAACM1234A1Z1,27,INV-TALLY-01,2026-01-10,2026-02-10,50000.00,PO-M01\n"
        "Modern Steel,27AAACM1234A1Z1,27,INV-TALLY-02,2026-01-15,2026-02-15,35000.00,PO-M02\n"
        "Bad Row Customer,,,,,,,\n"
    )
    files = {"file": ("tally.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = client.post("/api/import/tally-csv", files=files)
    assert r.status_code == 200
    data = r.json()
    assert data["customers_created"] >= 1
    assert data["invoices_created"] == 2
    assert len(data["rows_skipped"]) == 1


# ─── 6. Actions & Approvals API ───────────────────────────────────────────────

def test_actions_workflow(client):
    """Test actions inbox, explain, approve, and reject."""
    # List drafted actions
    r = client.get("/api/actions?status=DRAFTED")
    assert r.status_code == 200
    actions = r.json()
    assert len(actions) >= 1
    action_id = actions[0]["id"]

    # Explain action
    r_exp = client.get(f"/api/actions/{action_id}/explain")
    assert r_exp.status_code == 200
    assert "summary" in r_exp.json()
    assert "evidence" in r_exp.json()

    # Reject action
    r_reject = client.post(f"/api/actions/{action_id}/reject", json={"reason": "Timing too early"})
    assert r_reject.status_code == 200
    assert r_reject.json()["status"] == "REJECTED"


def test_approval_handoff_and_owner_confirmation_are_truthful(client, monkeypatch):
    """Approval prepares a handoff; only an owner report marks it sent."""
    local_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    monkeypatch.setattr(clock, "now", lambda: local_time)
    action_id = client.get("/api/actions?status=DRAFTED").json()[0]["id"]

    approved = client.post(f"/api/actions/{action_id}/approve", json={})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["sent_at"] is None
    assert approved.json()["handoff_url"] == f"/api/actions/{action_id}/handoff"

    handoff = client.get(
        f"/api/actions/{action_id}/handoff",
        follow_redirects=False,
    )
    assert handoff.status_code == 302
    assert handoff.headers["location"].startswith("https://wa.me/")
    opened = client.get("/api/actions?status=APPROVED").json()[0]
    opened_at = datetime.fromisoformat(opened["handoff_opened_at"].replace("Z", "+00:00"))
    assert opened_at.astimezone(local_time.tzinfo) == local_time

    confirmed = client.post(
        f"/api/actions/{action_id}/confirm-delivery",
        json={"confirmed_by": "owner"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "SENT"
    assert confirmed.json()["delivery_confirmation_source"] == "OWNER_REPORTED"
    assert confirmed.json()["provider_confirmed"] is False
    assert client.post(
        f"/api/actions/{action_id}/confirm-delivery",
        json={"confirmed_by": "owner"},
    ).status_code == 409


def test_approval_without_contact_number_has_no_handoff(client):
    """A missing contact number does not create a broken handoff URL."""
    cleared = client.patch("/api/customers/1", json={"contact_phone": None})
    assert cleared.status_code == 200
    action_id = client.get("/api/actions?status=DRAFTED").json()[0]["id"]

    approved = client.post(f"/api/actions/{action_id}/approve", json={})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["handoff_url"] is None
    assert approved.json()["handoff_status"] == "NO_VALID_CONTACT_NUMBER"
    assert client.get(f"/api/actions/{action_id}/handoff").status_code == 409


def test_whatsapp_handoff_is_blocked_outside_contact_hours(client, monkeypatch):
    """Owner approval cannot bypass the 09:00–19:00 IST contact window."""
    after_hours = datetime(2026, 1, 1, 20, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    monkeypatch.setattr(clock, "now", lambda: after_hours)
    action_id = client.get("/api/actions?status=DRAFTED").json()[0]["id"]
    assert client.post(f"/api/actions/{action_id}/approve", json={}).status_code == 200

    handoff = client.get(f"/api/actions/{action_id}/handoff")
    assert handoff.status_code == 409
    assert "09:00 and 19:00 IST" in handoff.json()["error"]["message"]


# ─── 7. Inbound Messages API ──────────────────────────────────────────────────

def test_record_inbound_message(client):
    """Test POST /api/messages/inbound stores reply and performs risk assessment."""
    payload = {
        "customer_id": 1,
        "invoice_id": 1,
        "channel": "WHATSAPP",
        "sender_name": "Priya",
        "body": "We have forwarded the invoice to our accounts team.",
    }
    r = client.post("/api/messages/inbound", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert "memory_event_id" in data
    assert data["risk_assessment_status"] == "COMPLETED"
    assert data["risk_assessment_error"] is None


# ─── 8. Payments API ──────────────────────────────────────────────────────────

def test_record_payment(client):
    """Test POST /api/payments records payment and updates status."""
    payload = {
        "invoice_id": 1,
        "amount_paise": 4820000,
        "paid_on": "2026-03-05",
        "reference": "UTR123456",
    }
    r = client.post("/api/payments", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["invoice_status"] == "PAID"
    assert "days_late" in data


def test_payment_commits_even_if_risk_assessment_fails(client, monkeypatch):
    """A failed secondary assessment is reported without undoing a recorded payment."""
    from munshi.agents.risk import RiskAgent

    async def fail_assessment(self, session, payment_id):
        raise RuntimeError("test-only failure")

    monkeypatch.setattr(RiskAgent, "on_payment", fail_assessment)
    before = client.get("/api/dashboard").json()["total_receivable_paise"]
    response = client.post(
        "/api/payments",
        json={
            "invoice_id": 2,
            "amount_paise": 10000,
            "paid_on": "2026-03-05",
            "reference": "TEST-REF",
        },
    )
    assert response.status_code == 201
    assert response.json()["risk_assessment_status"] == "FAILED"
    assert response.json()["risk_assessment_error"]
    after = client.get("/api/dashboard").json()["total_receivable_paise"]
    assert after == before - 10000


# ─── 9. Risk Alerts API ───────────────────────────────────────────────────────

def test_risk_alerts_and_ack(client):
    """Test GET /api/risk/alerts and POST /api/risk/alerts/{id}/ack."""
    r = client.get("/api/risk/alerts?status=OPEN")
    assert r.status_code == 200
    alerts = r.json()
    assert len(alerts) >= 1
    alert_id = alerts[0]["id"]

    # Acknowledge
    r_ack = client.post(f"/api/risk/alerts/{alert_id}/ack", json={"status": "ACKNOWLEDGED"})
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "ACKNOWLEDGED"


# ─── 10. Explain API ──────────────────────────────────────────────────────────

def test_explain_endpoint(client):
    """Test POST /api/explain plain-language explanation query."""
    payload = {
        "customer_id": 1,
        "question": "Why is Reddy Traders requiring a signed challan?",
    }
    r = client.post("/api/explain", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "evidence" in data


def test_customer_detail_returns_only_customer_scoped_memory(client, monkeypatch):
    """Customer detail normalizes timestamps and excludes other customers' memories."""
    from munshi.memory import queries as memory_queries

    recalled_at = datetime(2026, 3, 5, 9, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    class FakeMemoryStore:
        is_available = True

        async def recall(self, **kwargs):
            assert kwargs["customer_id"] == "1"
            return [
                {
                    "id": "memory-1",
                    "customer_id": "1",
                    "timestamp": recalled_at,
                    "content": "Pays after the 5th",
                    "metadata": {"trend": "stable"},
                },
                {
                    "id": "memory-2",
                    "customer_id": "2",
                    "timestamp": recalled_at,
                    "content": "Another customer's private context",
                    "metadata": {},
                },
            ]

    async def fake_reflect(**kwargs):
        assert kwargs["customer_id"] == "1"
        return {"playbook": "Customer-scoped learned context"}

    monkeypatch.setattr(memory_queries, "memory_store", FakeMemoryStore())
    monkeypatch.setattr(memory_queries, "get_memory_for_collector", fake_reflect)
    response = client.get("/api/customers/1")

    assert response.status_code == 200
    result = response.json()
    assert result["memory_status"] == "AVAILABLE"
    assert result["playbook"]["text"] == "Customer-scoped learned context"
    assert [belief["text"] for belief in result["beliefs"]] == ["Pays after the 5th"]
    assert result["beliefs"][0]["evidence"][0]["date"] == "2026-03-05"


# ─── 11. Simulation Controls API ──────────────────────────────────────────────

def test_simulation_controls(client):
    """Test day/hour clock advancement and the documented injection/reset routes."""
    clock.reset()
    r_hours = client.post("/api/sim/tick?days=0&hours=10")
    assert r_hours.status_code == 200
    assert "T10:00:00" in r_hours.json()["clock"]
    assert client.post("/api/sim/tick?days=0&hours=0").status_code == 422
    assert client.post("/api/sim/tick?days=0&hours=24").status_code == 422

    # Tick
    r_tick = client.post("/api/sim/tick?days=5")
    assert r_tick.status_code == 200
    assert "clock" in r_tick.json()

    # Inject
    inject_payload = {
        "customer_id": 1,
        "type": "CONTACT_CHANGE",
        "payload": {"new_contact": "Arun"},
    }
    r_inj = client.post("/api/sim/inject", json=inject_payload)
    assert r_inj.status_code == 200
    assert r_inj.json()["ok"] is True

    # Reset
    r_reset = client.post("/api/sim/reset")
    assert r_reset.status_code == 200
    assert "clock" in r_reset.json()


# ─── 12. Evaluation Results API ───────────────────────────────────────────────

def test_eval_results_endpoint(client):
    """Test GET /api/eval/results returns evaluation structure."""
    r = client.get("/api/eval/results")
    assert r.status_code == 200
    data = r.json()
    assert "git_hash" in data
    assert "arms" in data
    assert "test_months" in data
    assert "seeds" in data
