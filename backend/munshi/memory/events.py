"""
Munshi - Memory event handling

This module handles event tagging and retain templates.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def generate_event_tags(
    customer_id: Optional[str] = None,
    event_kind: str = "action",
    invoice_id: Optional[str] = None,
) -> List[str]:
    """
    Generate Hindsight event tags.
    
    Tags format:
    - customer:<id>
    - kind:<event_kind>
    - invoice:<id>
    
    Args:
        customer_id: Customer ID
        event_kind: Event category (action, observation, reminder, promise, payment)
        invoice_id: Invoice ID
    
    Returns:
        List of tag strings
    """
    tags = []
    if customer_id:
        tags.append(f"customer:{customer_id}")
    tags.append(f"kind:{event_kind}")
    if invoice_id:
        tags.append(f"invoice:{invoice_id}")
    return tags


def format_event_content(event_type: str, details: Dict[str, Any]) -> str:
    """
    Format event content for retention.
    
    Writing rules:
    - First person for Munshi's actions
    - Absolute dates (never "yesterday")
    - Full names with roles
    - Brief quotes from customers
    - Never retain phone/bank numbers, unsent drafts
    
    Args:
        event_type: Type of event (from EVENT_TEMPLATES)
        details: Event details dict
    
    Returns:
        Formatted content string
    """
    template_info = EVENT_TEMPLATES.get(event_type)
    if not template_info:
        return f"Event: {event_type} - {details}"
    
    template = template_info["template"]
    required = template_info.get("required_fields", [])
    
    # Validate required fields
    for field in required:
        if field not in details:
            logger.warning(f"Missing required field '{field}' for event type '{event_type}'")
    
    # Format the template
    try:
        return template.format(**details)
    except KeyError as e:
        logger.error(f"Template formatting error for {event_type}: {e}")
        return f"Event: {event_type} - {details}"


def create_retain_payload(
    bank_name: str,
    timestamp: datetime,
    customer_id: Optional[str],
    invoice_id: Optional[str],
    event_type: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create payload for retain call.
    
    Parameters:
    - bank_name: Bank name (munshi-<slug> or eval-<run>-C-s<seed>)
    - timestamp: Event timestamp (for temporal recall)
    - customer_id: Customer ID (optional)
    - invoice_id: Invoice ID (optional)
    - event_type: Type of event
    - details: Event details
    
    Returns:
    - Dictionary ready for Hindsight retain call
    """
    from munshi.memory.events import format_event_content, generate_event_tags
    
    return {
        "bank_id": bank_name,
        "timestamp": timestamp,
        "document_id": f"evt_{timestamp.isoformat()}",
        "content": format_event_content(event_type, details),
        "tags": generate_event_tags(customer_id, event_type, invoice_id),
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "metadata": {
            "event_type": event_type,
            **details,
        },
    }


def format_invoice_sent(
    date: datetime,
    invoice_number: str,
    amount: float,
    contact: str,
    customer: str,
    po: str = None,
    challan: str = None,
) -> Dict[str, Any]:
    """
    Format invoice sent event.
    
    Args:
        date: Invoice date
        invoice_number: Invoice number
        amount: Invoice amount
        contact: Contact person
        customer: Customer name
        po: PO number (optional)
        challan: Challan number (optional)
    
    Returns:
        Event details dict
    """
    return {
        "date": date.strftime("%Y-%m-%d"),
        "invoice_number": invoice_number,
        "amount": str(amount),
        "contact": contact,
        "customer": customer,
        "po": po or "no PO",
        "challan": challan or "no challan",
    }


def format_invoice_held(
    date: datetime,
    customer: str,
    invoice_number: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Format invoice held event.
    
    Args:
        date: Date invoice was held
        customer: Customer name
        invoice_number: Invoice number
        reason: Reason for holding
    
    Returns:
        Event details dict
    """
    return {
        "date": date.strftime("%Y-%m-%d"),
        "customer": customer,
        "invoice_number": invoice_number,
        "reason": reason,
    }


def format_reminder_sent(
    date: datetime,
    contact: str,
    channel: str,
    invoice_number: str,
    days_before: int,
) -> Dict[str, Any]:
    """
    Format reminder sent event.
    
    Args:
        date: Date reminder was sent
        contact: Contact person
        channel: Communication channel (call, sms, whatsapp, email)
        invoice_number: Invoice number
        days_before: Days before payment run
    
    Returns:
        Event details dict
    """
    return {
        "date": date.strftime("%Y-%m-%d"),
        "contact": contact,
        "channel": channel,
        "invoice_number": invoice_number,
        "days": str(days_before),
    }


def format_customer_reply(
    date: datetime,
    contact: str,
    role: str,
    customer: str,
    reply: str,
) -> Dict[str, Any]:
    """
    Format customer reply event.
    
    Args:
        date: Date of reply
        contact: Contact person
        role: Contact's role
        customer: Customer name
        reply: Reply content (brief quote)
    
    Returns:
        Event details dict
    """
    return {
        "date": date.strftime("%Y-%m-%d"),
        "contact": contact,
        "role": role,
        "customer": customer,
        "reply": reply[:200] if reply else "",  # Truncate long quotes
    }


def format_promise_to_pay(
    date: datetime,
    contact: str,
    role: str,
    customer: str,
    invoice_number: str,
    promise_date: datetime,
) -> Dict[str, Any]:
    """
    Format promise to pay event.
    
    Args:
        date: Date promise was made
        contact: Contact person
        role: Contact's role
        customer: Customer name
        invoice_number: Invoice number
        promise_date: Date payment is promised
    
    Returns:
        Event details dict
    """
    return {
        "date": date.strftime("%Y-%m-%d"),
        "contact": contact,
        "role": role,
        "customer": customer,
        "invoice_number": invoice_number,
        "promise_date": promise_date.strftime("%Y-%m-%d"),
    }


def format_payment_received(
    date: datetime,
    customer: str,
    invoice_number: str,
    days_late: int,
    amount: float = None,
) -> Dict[str, Any]:
    """
    Format payment received event.
    
    Args:
        date: Date payment was received
        customer: Customer name
        invoice_number: Invoice number
        days_late: Days late (0 if on time)
        amount: Amount received (optional)
    
    Returns:
        Event details dict
    """
    details = {
        "date": date.strftime("%Y-%m-%d"),
        "customer": customer,
        "invoice_number": invoice_number,
        "days_late": str(days_late),
    }
    if amount is not None:
        details["amount"] = str(amount)
    return details


def format_contact_change(
    date: datetime,
    old_contact: str,
    new_contact: str,
    customer: str,
    reason: str = None,
) -> Dict[str, Any]:
    """
    Format contact change event.
    
    Args:
        date: Date of change
        old_contact: Previous contact person
        new_contact: New contact person
        customer: Customer name
        reason: Reason for change (optional)
    
    Returns:
        Event details dict
    """
    details = {
        "date": date.strftime("%Y-%m-%d"),
        "old_contact": old_contact,
        "new_contact": new_contact,
        "customer": customer,
    }
    if reason:
        details["reason"] = reason
    return details


def format_owner_confirmation(
    date: datetime,
    contact: str,
    customer: str,
    role: str = "payables contact",
) -> Dict[str, Any]:
    """
    Format owner confirmation event.
    
    Args:
        date: Date of confirmation
        contact: Contact person
        customer: Customer name
        role: Role being confirmed
    
    Returns:
        Event details dict
    """
    return {
        "date": date.strftime("%Y-%m-%d"),
        "contact": contact,
        "customer": customer,
        "role": role,
    }


# Event type templates
EVENT_TEMPLATES = {
    "invoice_sent": {
        "template": "On {date} I sent invoice {invoice_number} for ₹{amount} to {contact} at {customer}, with {po} and {challan} attached.",
        "required_fields": ["date", "invoice_number", "amount", "contact", "customer"],
    },
    "invoice-held": {
        "template": "On {date} {customer} held {invoice_number} because {reason}.",
        "required_fields": ["date", "customer", "invoice_number", "reason"],
    },
    "reminder_sent": {
        "template": "On {date} I reminded {contact} on {channel} about {invoice_number}, {days} days before their usual payment run.",
        "required_fields": ["date", "contact", "channel", "invoice_number", "days"],
    },
    "customer_reply": {
        "template": "On {date} {contact} ({role}, {customer}) replied: \"{reply}\"",
        "required_fields": ["date", "contact", "role", "customer", "reply"],
    },
    "promise_to_pay": {
        "template": "On {date} {contact} ({role}, {customer}) promised payment of {invoice_number} by {promise_date}.",
        "required_fields": ["date", "contact", "role", "customer", "invoice_number", "promise_date"],
    },
    "payment_received": {
        "template": "On {date} {customer} paid {invoice_number} in full, {days_late} days late.",
        "required_fields": ["date", "customer", "invoice_number", "days_late"],
    },
    "contact_change": {
        "template": "On {date} {old_contact} said {new_contact} now handles payables at {customer}.",
        "required_fields": ["date", "old_contact", "new_contact", "customer"],
    },
    "owner_confirmation": {
        "template": "On {date} Owner confirmed: {contact} is the payables contact at {customer}.",
        "required_fields": ["date", "contact", "customer"],
    },
}
