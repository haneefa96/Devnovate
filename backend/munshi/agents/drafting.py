"""
Munshi - Drafting utilities

This module handles message drafting with LLM templates.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from munshi.llm.groq_client import groq_client


class MessageDraft:
    """Draft message."""
    
    def __init__(
        self,
        recipient: str,
        channel: str,
        body: str,
        attachments: List[str] = None,
        planned_for: Optional[datetime] = None,
        evidence: str = "",
    ):
        self.recipient = recipient
        self.channel = channel
        self.body = body
        self.attachments = attachments or []
        self.planned_for = planned_for
        self.evidence = evidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recipient": self.recipient,
            "channel": self.channel,
            "body": self.body,
            "attachments": self.attachments,
            "planned_for": self.planned_for.isoformat() if self.planned_for else None,
            "evidence": self.evidence,
        }


class DraftingService:
    """Service for drafting messages."""
    
    # Templates (in agents/prompts/)
    TEMPLATES = {
        "reminder": "Reminder about overdue invoice {invoice_number}.",
        "doc_request": "Request for {doc_type} for invoice {invoice_number}.",
        "thank_you": "Thank you for payment of invoice {invoice_number}.",
        "escalation": "Request for escalation on invoice {invoice_number}.",
    }
    
    def __init__(self):
        self.llm = groq_client
    
    async def draft_reminder(
        self,
        customer_name: str,
        invoice_number: str,
        days_overdue: int,
        payment_run_day: str,
    ) -> MessageDraft:
        """
        Draft a reminder message.
        
        Args:
            customer_name: Customer name
            invoice_number: Invoice number
            days_overdue: Days overdue
            payment_run_day: Customer's payment run day
        
        Returns:
            Message draft
        """
        # TODO: Call LLM with template
        return MessageDraft(
            recipient=customer_name,
            channel="WHATSAPP",
            body=f"Reminder: Invoice {invoice_number} is {days_overdue} days overdue. Payment run day is {payment_run_day}.",
            evidence=f"Overdue by {days_overdue} days",
        )
    
    async def draft_doc_request(
        self,
        customer_name: str,
        invoice_number: str,
        doc_type: str,
    ) -> MessageDraft:
        """Draft a document request message."""
        # TODO: Implement
        return MessageDraft(
            recipient=customer_name,
            channel="WHATSAPP",
            body=f"Please provide {doc_type} for invoice {invoice_number}.",
            evidence=f"Missing {doc_type}",
        )
    
    async def draft_thank_you(
        self,
        customer_name: str,
        invoice_number: str,
        amount: str,
    ) -> MessageDraft:
        """Draft a thank you message."""
        # TODO: Implement
        return MessageDraft(
            recipient=customer_name,
            channel="WHATSAPP",
            body=f"Thank you for payment of {amount} for invoice {invoice_number}.",
            evidence=f"Invoice paid in full",
        )


# Global instance
drafting_service = DraftingService()
