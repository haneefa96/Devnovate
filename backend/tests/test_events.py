"""
Munshi - Test memory events
"""

import pytest
from datetime import datetime

from munshi.memory.events import (
    generate_event_tags,
    format_event_content,
    create_retain_payload,
    format_invoice_sent,
    format_invoice_held,
    format_reminder_sent,
    format_customer_reply,
    format_promise_to_pay,
    format_payment_received,
    format_contact_change,
    format_owner_confirmation,
    EVENT_TEMPLATES,
)


class TestGenerateEventTags:
    """Test event tag generation."""
    
    def test_generate_event_tags_with_customer(self):
        """Test tag generation with customer ID."""
        tags = generate_event_tags(customer_id="cust_123", event_kind="action")
        assert "customer:cust_123" in tags
        assert "kind:action" in tags
    
    def test_generate_event_tags_with_invoice(self):
        """Test tag generation with invoice ID."""
        tags = generate_event_tags(invoice_id="inv_456", event_kind="payment")
        assert "invoice:inv_456" in tags
        assert "kind:payment" in tags
    
    def test_generate_event_tags_with_all(self):
        """Test tag generation with all parameters."""
        tags = generate_event_tags(
            customer_id="cust_123",
            invoice_id="inv_456",
            event_kind="reminder"
        )
        assert "customer:cust_123" in tags
        assert "invoice:inv_456" in tags
        assert "kind:reminder" in tags
    
    def test_generate_event_tags_without_customer(self):
        """Test tag generation without customer ID."""
        tags = generate_event_tags(event_kind="action")
        assert "customer:" not in " ".join(tags)
        assert "kind:action" in tags
    
    def test_generate_event_tags_empty(self):
        """Test tag generation with minimal parameters."""
        tags = generate_event_tags()
        assert tags == ["kind:action"]


class TestFormatEventContent:
    """Test event content formatting."""
    
    def test_format_invoice_sent(self):
        """Test invoice sent formatting."""
        details = {
            "date": "2024-01-15",
            "invoice_number": "INV-001",
            "amount": "50000",
            "contact": "Ramesh Patel",
            "customer": "Reddy Traders",
            "po": "PO-123",
            "challan": "CH-456",
        }
        content = format_event_content("invoice_sent", details)
        assert "INV-001" in content
        assert "50000" in content
        assert "Ramesh Patel" in content
    
    def test_format_invoice_held(self):
        """Test invoice held formatting."""
        details = {
            "date": "2024-01-15",
            "customer": "Reddy Traders",
            "invoice_number": "INV-001",
            "reason": "Missing GSTIN",
        }
        content = format_event_content("invoice-held", details)
        assert "INV-001" in content
        assert "Missing GSTIN" in content
    
    def test_format_reminder_sent(self):
        """Test reminder sent formatting."""
        details = {
            "date": "2024-01-15",
            "contact": "Ramesh Patel",
            "channel": "whatsapp",
            "invoice_number": "INV-001",
            "days": "2",
        }
        content = format_event_content("reminder_sent", details)
        assert "whatsapp" in content
        assert "INV-001" in content
    
    def test_format_customer_reply(self):
        """Test customer reply formatting."""
        details = {
            "date": "2024-01-15",
            "contact": "Ramesh Patel",
            "role": "Accounts Payable",
            "customer": "Reddy Traders",
            "reply": "We will pay by Friday",
        }
        content = format_event_content("customer_reply", details)
        assert "Ramesh Patel" in content
        assert "Accounts Payable" in content
    
    def test_format_promise_to_pay(self):
        """Test promise to pay formatting."""
        details = {
            "date": "2024-01-15",
            "contact": "Ramesh Patel",
            "role": "Owner",
            "customer": "Reddy Traders",
            "invoice_number": "INV-001",
            "promise_date": "2024-01-20",
        }
        content = format_event_content("promise_to_pay", details)
        assert "INV-001" in content
        assert "2024-01-20" in content
    
    def test_format_payment_received(self):
        """Test payment received formatting."""
        details = {
            "date": "2024-01-15",
            "customer": "Reddy Traders",
            "invoice_number": "INV-001",
            "days_late": "3",
        }
        content = format_event_content("payment_received", details)
        assert "INV-001" in content
        assert "3" in content
    
    def test_format_contact_change(self):
        """Test contact change formatting."""
        details = {
            "date": "2024-01-15",
            "old_contact": "Suresh",
            "new_contact": "Ramesh Patel",
            "customer": "Reddy Traders",
        }
        content = format_event_content("contact_change", details)
        assert "Suresh" in content
        assert "Ramesh Patel" in content
    
    def test_format_owner_confirmation(self):
        """Test owner confirmation formatting."""
        details = {
            "date": "2024-01-15",
            "contact": "Ramesh Patel",
            "customer": "Reddy Traders",
        }
        content = format_event_content("owner_confirmation", details)
        assert "Ramesh Patel" in content
    
    def test_format_unknown_event(self):
        """Test unknown event type."""
        details = {"key": "value"}
        content = format_event_content("unknown_event", details)
        assert "Event: unknown_event" in content
    
    def test_format_missing_required_field(self):
        """Test missing required field logs warning."""
        details = {"invoice_number": "INV-001"}  # Missing required fields
        content = format_event_content("invoice_sent", details)
        assert "invoice_sent" in content


class TestCreateRetainPayload:
    """Test retain payload creation."""
    
    def test_create_retain_payload_basic(self):
        """Test basic retain payload creation."""
        payload = create_retain_payload(
            bank_name="munshi-test",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            customer_id="cust_123",
            invoice_id="inv_456",
            event_type="invoice_sent",
            details={"invoice_number": "INV-001"},
        )
        
        assert payload["bank_id"] == "munshi-test"
        assert payload["customer_id"] == "cust_123"
        assert payload["invoice_id"] == "inv_456"
        assert "content" in payload
        assert "tags" in payload
    
    def test_create_retain_payload_tags(self):
        """Test retain payload tags."""
        payload = create_retain_payload(
            bank_name="munshi-test",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            customer_id="cust_123",
            invoice_id="inv_456",
            event_type="invoice_sent",
            details={"invoice_number": "INV-001"},
        )
        
        tags = payload["tags"]
        assert "customer:cust_123" in tags
        assert "invoice:inv_456" in tags
        assert "kind:invoice_sent" in tags


class TestFormatFunctions:
    """Test individual event formatting functions."""
    
    def test_format_invoice_sent_function(self):
        """Test format_invoice_sent helper function."""
        result = format_invoice_sent(
            date=datetime(2024, 1, 15),
            invoice_number="INV-001",
            amount=50000,
            contact="Ramesh Patel",
            customer="Reddy Traders",
            po="PO-123",
            challan="CH-456",
        )
        
        assert result["date"] == "2024-01-15"
        assert result["invoice_number"] == "INV-001"
        assert result["amount"] == "50000"
        assert result["contact"] == "Ramesh Patel"
    
    def test_format_invoice_held_function(self):
        """Test format_invoice_held helper function."""
        result = format_invoice_held(
            date=datetime(2024, 1, 15),
            customer="Reddy Traders",
            invoice_number="INV-001",
            reason="Missing GSTIN",
        )
        
        assert result["customer"] == "Reddy Traders"
        assert result["reason"] == "Missing GSTIN"
    
    def test_format_reminder_sent_function(self):
        """Test format_reminder_sent helper function."""
        result = format_reminder_sent(
            date=datetime(2024, 1, 15),
            contact="Ramesh Patel",
            channel="whatsapp",
            invoice_number="INV-001",
            days_before=2,
        )
        
        assert result["channel"] == "whatsapp"
        assert result["days"] == "2"
    
    def test_format_customer_reply_function(self):
        """Test format_customer_reply helper function."""
        result = format_customer_reply(
            date=datetime(2024, 1, 15),
            contact="Ramesh Patel",
            role="Accounts Payable",
            customer="Reddy Traders",
            reply="We will pay by Friday",
        )
        
        assert result["contact"] == "Ramesh Patel"
        assert result["role"] == "Accounts Payable"
        assert result["reply"] == "We will pay by Friday"
    
    def test_format_customer_reply_truncates_long_reply(self):
        """Test that long replies are truncated."""
        long_reply = "A" * 300
        result = format_customer_reply(
            date=datetime(2024, 1, 15),
            contact="Ramesh Patel",
            role="Accounts Payable",
            customer="Reddy Traders",
            reply=long_reply,
        )
        
        assert len(result["reply"]) <= 200
    
    def test_format_promise_to_pay_function(self):
        """Test format_promise_to_pay helper function."""
        result = format_promise_to_pay(
            date=datetime(2024, 1, 15),
            contact="Ramesh Patel",
            role="Owner",
            customer="Reddy Traders",
            invoice_number="INV-001",
            promise_date=datetime(2024, 1, 20),
        )
        
        assert result["invoice_number"] == "INV-001"
        assert result["promise_date"] == "2024-01-20"
    
    def test_format_payment_received_function(self):
        """Test format_payment_received helper function."""
        result = format_payment_received(
            date=datetime(2024, 1, 15),
            customer="Reddy Traders",
            invoice_number="INV-001",
            days_late=3,
            amount=50000,
        )
        
        assert result["customer"] == "Reddy Traders"
        assert result["days_late"] == "3"
        assert result["amount"] == "50000"
    
    def test_format_contact_change_function(self):
        """Test format_contact_change helper function."""
        result = format_contact_change(
            date=datetime(2024, 1, 15),
            old_contact="Suresh",
            new_contact="Ramesh Patel",
            customer="Reddy Traders",
            reason="Promotion",
        )
        
        assert result["old_contact"] == "Suresh"
        assert result["new_contact"] == "Ramesh Patel"
        assert result["reason"] == "Promotion"
    
    def test_format_owner_confirmation_function(self):
        """Test format_owner_confirmation helper function."""
        result = format_owner_confirmation(
            date=datetime(2024, 1, 15),
            contact="Ramesh Patel",
            customer="Reddy Traders",
            role="payables contact",
        )
        
        assert result["contact"] == "Ramesh Patel"
        assert result["role"] == "payables contact"


class TestEventTemplates:
    """Test event templates."""
    
    def test_all_templates_have_required_fields(self):
        """Test that all templates have required_fields."""
        for event_type, template in EVENT_TEMPLATES.items():
            assert "template" in template
            assert "required_fields" in template
    
    def test_invoice_sent_template(self):
        """Test invoice_sent template structure."""
        template = EVENT_TEMPLATES["invoice_sent"]
        assert "invoice_number" in template["required_fields"]
        assert "amount" in template["required_fields"]
        assert "contact" in template["required_fields"]
        assert "customer" in template["required_fields"]
    
    def test_invoice_held_template(self):
        """Test invoice-held template structure."""
        template = EVENT_TEMPLATES["invoice-held"]
        assert "customer" in template["required_fields"]
        assert "invoice_number" in template["required_fields"]
        assert "reason" in template["required_fields"]
