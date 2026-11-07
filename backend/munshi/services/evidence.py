"""Resolve ledger evidence references for owner-facing explanations."""

from datetime import date

from sqlmodel import Session, select

from munshi.db.models import InboundMessage, Invoice, MemoryEvent, Payment, Promise


def resolve_evidence(session: Session, evidence_ids: list[str]) -> list[dict[str, str]]:
    resolved: list[dict[str, str]] = []
    for evidence_id in dict.fromkeys(evidence_ids):
        prefix, separator, identifier = evidence_id.partition(":")
        if not separator:
            event = session.exec(
                select(MemoryEvent).where(
                    (MemoryEvent.id == evidence_id)
                    | (MemoryEvent.hindsight_document_id == evidence_id)
                )
            ).first()
            if event:
                resolved.append(_item(
                    evidence_id,
                    event.occurred_on,
                    event.content,
                    event.id,
                ))
            continue

        try:
            row_id = int(identifier)
        except ValueError:
            continue
        if prefix == "invoice":
            row = session.get(Invoice, row_id)
            if row:
                item = _item(
                    evidence_id,
                    row.issue_date,
                    f"Invoice {row.number}: {row.amount_paise} paise, due {row.due_date}.",
                    evidence_id,
                )
                resolved.append(item)
        elif prefix == "payment":
            row = session.get(Payment, row_id)
            if row:
                resolved.append(_item(
                    evidence_id,
                    row.paid_on,
                    f"Ledger payment recorded: {row.amount_paise} paise.",
                    evidence_id,
                ))
        elif prefix == "promise":
            row = session.get(Promise, row_id)
            if row:
                state = "kept" if row.kept is True else "missed" if row.kept is False else "unresolved"
                resolved.append(_item(
                    evidence_id,
                    row.promised_date,
                    f"Payment promise for {row.promised_date} is {state}.",
                    evidence_id,
                ))
        elif prefix in {"inbound_message", "message"}:
            row = session.get(InboundMessage, row_id)
            if row:
                resolved.append(_item(
                    evidence_id,
                    row.received_at.date(),
                    f"Inbound {row.channel} message: {row.body}",
                    evidence_id,
                ))
    return resolved


def _item(
    evidence_id: str,
    happened_on: date,
    text: str,
    event_id: str,
) -> dict[str, str]:
    return {
        "id": evidence_id,
        "date": happened_on.isoformat(),
        "text": text,
        "event_id": event_id,
    }
