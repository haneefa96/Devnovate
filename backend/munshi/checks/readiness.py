"""Combine deterministic invoice rules with evidence-backed customer requirements."""

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_
from sqlmodel import Session, select

from munshi.checks.rules import RuleResult, run_all_rules
from munshi.config import clock
from munshi.db.models import Invoice, MemoryEvent

logger = logging.getLogger(__name__)


_REQUIREMENT_CODES = {
    "PO_REF",
    "SIGNED_CHALLAN",
    "GRN_COPY",
    "EWAY_BILL",
    "EINVOICE_IRN",
    "CONTACT_PERSON",
    "OTHER",
}


class ReadinessResult:
    """Public outcome of an invoice readiness check."""

    def __init__(
        self,
        status: str,
        findings: list[dict[str, Any]] | None = None,
        memory_pending: bool = False,
    ) -> None:
        self.status = status
        self.findings = findings or []
        self.memory_pending = memory_pending

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness": self.status,
            "findings": self.findings,
            "memory_pending": self.memory_pending,
        }


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _evidence_ids(requirement: Any) -> list[str]:
    values = _value(requirement, "evidence_ids", []) or []
    return [str(value) for value in values if value]


def _required_memory_item_is_missing(code: str, invoice: Invoice) -> bool:
    customer = invoice.customer
    if code == "PO_REF":
        return not invoice.po_number
    if code == "SIGNED_CHALLAN":
        return not _has_document(invoice, "SIGNED_CHALLAN")
    if code == "GRN_COPY":
        return not _has_document(invoice, "GRN")
    if code == "EWAY_BILL":
        return not _has_document(invoice, "EWAY_BILL")
    if code == "EINVOICE_IRN":
        return True
    if code == "CONTACT_PERSON":
        return not (customer and customer.contact_name)
    if code == "OTHER":
        return not _has_document(invoice, "OTHER")
    return False


def _has_document(invoice: Invoice, doc_type: str) -> bool:
    return any(
        (document.doc_type.value if hasattr(document.doc_type, "value") else str(document.doc_type))
        == doc_type
        for document in invoice.documents
    )


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _evidence_age(
    requirement: Any,
    evidence_ids: list[str],
    session: Session | None,
) -> bool | None:
    evidence_dates = [
        parsed
        for item in (_value(requirement, "evidence_dates", []) or [])
        if (parsed := _as_date(item)) is not None
    ]
    if session and evidence_ids:
        events = session.exec(
            select(MemoryEvent).where(
                or_(
                    MemoryEvent.id.in_(evidence_ids),
                    MemoryEvent.hindsight_document_id.in_(evidence_ids),
                )
            )
        ).all()
        evidence_dates.extend(event.occurred_on for event in events)
    if not evidence_dates:
        return None
    today = clock.now().date()
    return any((today - evidence_date).days > 180 for evidence_date in evidence_dates)


def combine_readiness(
    rule_results: list[RuleResult],
    memory_findings: dict[str, Any] | None = None,
    session: Session | None = None,
    memory_pending: bool = False,
    invoice: Invoice | None = None,
) -> ReadinessResult:
    """Apply the documented blocker, conflict, uncertainty, ready precedence."""
    findings = [result.to_dict() for result in rule_results if result.is_blocker or result.warning]
    if any(result.is_blocker for result in rule_results):
        return ReadinessResult("BLOCKER", findings, memory_pending)

    memory_findings = memory_findings or {}
    requirements = memory_findings.get("requirements", []) or []
    conflicts = memory_findings.get("conflicts", []) or []
    memory_blockers: list[dict[str, Any]] = []
    uncertainty_findings: list[dict[str, Any]] = []

    for requirement in requirements:
        code = str(_value(requirement, "code", "")).upper()
        if code not in _REQUIREMENT_CODES:
            continue
        if not _value(requirement, "required", True):
            continue
        evidence_ids = _evidence_ids(requirement)
        evidence_count = _value(requirement, "evidence_count", len(evidence_ids)) or 0
        missing = bool(invoice and _required_memory_item_is_missing(code, invoice))
        description = _value(requirement, "description", code)

        if missing and evidence_ids:
            memory_blockers.append({
                "code": code,
                "source": "MEMORY",
                "message": f"Customer requirement not met: {description}",
                "evidence_ids": evidence_ids,
            })
        elif missing or not evidence_ids or evidence_count == 1 or len(evidence_ids) == 1:
            uncertainty_findings.append({
                "code": code,
                "source": "MEMORY",
                "message": (
                    "Learned requirement has insufficient evidence"
                    if not evidence_ids or evidence_count == 0
                    else "Evidence is thin (single source)"
                ),
                "evidence_ids": evidence_ids,
            })
        else:
            evidence_is_old = _evidence_age(requirement, evidence_ids, session)
            if evidence_is_old is True:
                uncertainty_findings.append({
                    "code": code,
                    "source": "MEMORY",
                    "message": "Learned requirement evidence is older than 180 days",
                    "evidence_ids": evidence_ids,
                })
            elif evidence_is_old is None:
                uncertainty_findings.append({
                    "code": code,
                    "source": "MEMORY",
                    "message": "Learned requirement evidence age cannot be verified",
                    "evidence_ids": evidence_ids,
                })

    if memory_blockers:
        return ReadinessResult("BLOCKER", findings + memory_blockers, memory_pending)

    if conflicts:
        conflict_findings = [
            {
                "code": str(_value(conflict, "code", "MEMORY_CONFLICT")),
                "source": "MEMORY",
                "message": str(
                    _value(conflict, "description", "Memory has conflicting information")
                ),
                "evidence_ids": _evidence_ids(conflict),
            }
            for conflict in conflicts
        ]
        return ReadinessResult("CONFLICT", findings + conflict_findings, memory_pending)

    consolidation_pending = bool(
        memory_pending
        or memory_findings.get("updating", False)
        or memory_findings.get("consolidation_pending", False)
    )
    if consolidation_pending:
        uncertainty_findings.append({
            "code": "MEMORY_PENDING",
            "source": "MEMORY",
            "message": "Customer memory is unavailable or still consolidating",
            "evidence_ids": [],
        })
    if uncertainty_findings:
        return ReadinessResult("UNCERTAIN", findings + uncertainty_findings, consolidation_pending)

    return ReadinessResult("READY", findings, False)


async def check_readiness(
    invoice: Invoice,
    session: Session | None = None,
    *,
    invoice_gstin: str | None = None,
    po_amount_paise: int | None = None,
    memory_findings: dict[str, Any] | None = None,
    memory_pending: bool | None = None,
) -> ReadinessResult:
    """Run R1-R9 and fetch customer requirements through the existing memory service."""
    rule_results = run_all_rules(
        invoice,
        session=session,
        invoice_gstin=invoice_gstin,
        po_amount_paise=po_amount_paise,
    )

    if memory_findings is None:
        from munshi.memory import queries

        customer = invoice.customer
        business = customer.business if customer else None
        if not business or not customer:
            memory_findings = {}
            memory_pending = True
            logger.warning(
                "Readiness memory unavailable: invoice has no buyer or supplier relation"
            )
        elif not queries.memory_store.is_available:
            memory_findings = {}
            memory_pending = True
            logger.warning("Readiness memory unavailable for customer %s", customer.id)
        else:
            from munshi.memory.client import HindsightUnavailable

            try:
                memory_findings = await queries.get_memory_for_readiness(
                    bank_name=business.bank_id,
                    customer_id=str(customer.id),
                )
                if memory_pending is None:
                    memory_pending = not any(
                        memory_findings.get(key)
                        for key in ("requirements", "conflicts", "playbook")
                    )
            except HindsightUnavailable:
                memory_findings = {}
                memory_pending = True
                logger.warning("Readiness memory service unavailable for customer %s", customer.id)

    return combine_readiness(
        rule_results,
        memory_findings=memory_findings,
        session=session,
        memory_pending=bool(memory_pending),
        invoice=invoice,
    )
