"""
Munshi - Test Band command parsing
"""

import pytest


class TestParseDraftMessage:
    """Test parse_draft_message function."""
    
    def test_parse_full_draft(self):
        """Test parsing full draft message."""
        from munshi.band.commands import parse_draft_message
        
        # Simplified format for testing
        text = "[DRAFT A-231] To Priya, WhatsApp, today 10:30. Payment reminder. Why: Invoice 2 days overdue."
        
        result = parse_draft_message(text)
        
        assert result is not None
        assert result["draft_id"] == "A-231"
        assert result["recipient"] == "Priya"
        assert result["channel"] == "WhatsApp"
        assert "Payment reminder" in result["body"]
        assert "Invoice 2 days overdue" in result["evidence"]
    
    def test_parse_draft_with_reply(self):
        """Test parsing draft with reply section."""
        from munshi.band.commands import parse_draft_message
        
        # Reply section is at end after Why
        text = "[DRAFT A-231] To Priya, WhatsApp, today 10:30. Payment reminder. Why: 2 days overdue. Reply: approve A-231 / edit A-231: text / reject A-231"
        
        result = parse_draft_message(text)
        
        assert result is not None
        # The Reply: part should be captured
        assert result["actions"] == "approve A-231 / edit A-231: text / reject A-231"
    
    def test_parse_invalid_draft(self):
        """Test parsing invalid draft message."""
        from munshi.band.commands import parse_draft_message
        
        text = "Not a draft message"
        result = parse_draft_message(text)
        
        assert result is None
    
    def test_parse_draft_minimal(self):
        """Test parsing minimal draft message."""
        from munshi.band.commands import parse_draft_message
        
        # Minimal draft must have Why: section
        text = "[DRAFT INV-001] To John, email, today 14:00. Follow up. Why: No reason."
        
        result = parse_draft_message(text)
        
        assert result is not None
        assert result["draft_id"] == "INV-001"


class TestParseRiskMessage:
    """Test parse_risk_message function."""
    
    def test_parse_full_risk(self):
        """Test parsing full risk message."""
        from munshi.band.commands import parse_risk_message
        
        text = "[RISK] Reddy Traders: Watch → High. Signals: missed 5th; cash flow tight. Suggest: hold next dispatch @owner"
        
        result = parse_risk_message(text)
        
        assert result is not None
        assert result["customer"] == "Reddy Traders"
        assert result["from_level"] == "Watch"
        assert result["to_level"] == "High"
        assert len(result["signals"]) >= 1
        assert "hold next dispatch" in result["suggestion"]
    
    def test_parse_invalid_risk(self):
        """Test parsing invalid risk message."""
        from munshi.band.commands import parse_risk_message
        
        text = "Not a risk message"
        result = parse_risk_message(text)
        
        assert result is None


class TestParseHandoffMessage:
    """Test parse_handoff_message function."""
    
    def test_parse_handoff(self):
        """Test parsing handoff message."""
        from munshi.band.commands import parse_handoff_message
        
        text = "@Risk reply from Rahul mentions cash-flow trouble on INV-1060, please assess"
        
        result = parse_handoff_message(text)
        
        assert result is not None
        assert result["invoice_id"] == "INV-1060"
        assert "cash-flow trouble" in result["description"]
    
    def test_parse_invalid_handoff(self):
        """Test parsing invalid handoff message."""
        from munshi.band.commands import parse_handoff_message
        
        text = "Not a handoff message"
        result = parse_handoff_message(text)
        
        assert result is None


class TestParseOwnerCommand:
    """Test parse_owner_command function."""
    
    def test_parse_approve(self):
        """Test parsing approve command."""
        from munshi.band.commands import parse_owner_command
        
        result = parse_owner_command("approve A-231")
        
        assert result is not None
        assert result["action"] == "approve"
        assert result["draft_id"] == "A-231"
    
    def test_parse_edit(self):
        """Test parsing edit command."""
        from munshi.band.commands import parse_owner_command
        
        result = parse_owner_command("edit A-231: update message")
        
        assert result is not None
        assert result["action"] == "edit"
        assert result["draft_id"] == "A-231"
        assert result["text"] == "update message"
    
    def test_parse_reject(self):
        """Test parsing reject command."""
        from munshi.band.commands import parse_owner_command
        
        result = parse_owner_command("reject A-231")
        
        assert result is not None
        assert result["action"] == "reject"
        assert result["draft_id"] == "A-231"
    
    def test_parse_invalid_command(self):
        """Test parsing invalid command."""
        from munshi.band.commands import parse_owner_command
        
        result = parse_owner_command("unknown A-231")
        
        assert result is None


class TestParseBandMessage:
    """Test parse_band_message function."""
    
    def test_parse_draft(self):
        """Test parsing draft message."""
        from munshi.band.commands import parse_band_message
        
        text = "[DRAFT A-231] To Priya, WhatsApp, today 10:30. Payment reminder. Why: 2 days overdue."
        msg_type, data = parse_band_message(text)
        
        assert msg_type == "draft"
        assert data is not None
    
    def test_parse_risk(self):
        """Test parsing risk message."""
        from munshi.band.commands import parse_band_message
        
        text = "[RISK] Reddy Traders: Watch → High. Signals: test. Suggest: check."
        msg_type, data = parse_band_message(text)
        
        assert msg_type == "risk"
        assert data is not None
    
    def test_parse_handoff(self):
        """Test parsing handoff message."""
        from munshi.band.commands import parse_band_message
        
        text = "@Risk reply on INV-1060, please assess"
        msg_type, data = parse_band_message(text)
        
        assert msg_type == "handoff"
        assert data is not None
    
    def test_parse_command(self):
        """Test parsing command message."""
        from munshi.band.commands import parse_band_message
        
        msg_type, data = parse_band_message("approve A-231")
        
        assert msg_type == "command"
        assert data is not None
    
    def test_parse_unknown(self):
        """Test parsing unknown message."""
        from munshi.band.commands import parse_band_message
        
        # Empty message should return unknown
        msg_type, data = parse_band_message("")
        
        # This should be unknown since it doesn't match any pattern
        assert msg_type == "unknown"
        assert data is None


class TestFormatMessages:
    """Test message formatting functions."""
    
    def test_format_draft_message(self):
        """Test format_draft_message function."""
        from munshi.band.commands import format_draft_message
        
        draft_data = {
            "id": "A-231",
            "recipient": "Priya",
            "customer": "Reddy Traders",
            "channel": "WhatsApp",
            "time": "10:30",
            "body": "Payment reminder",
            "evidence": "Invoice 2 days overdue",
        }
        
        result = format_draft_message(draft_data)
        
        assert "[DRAFT A-231]" in result
        assert "Priya" in result
        assert "Reddy Traders" in result
    
    def test_format_risk_message(self):
        """Test format_risk_message function."""
        from munshi.band.commands import format_risk_message
        
        alert_data = {
            "customer": "Reddy Traders",
            "from_level": "Watch",
            "to_level": "High",
            "signals": ["missed 5th", "cash flow tight"],
            "suggestion": "hold next dispatch",
        }
        
        result = format_risk_message(alert_data)
        
        assert "[RISK] Reddy Traders" in result
        assert "Watch → High" in result


class TestExtractFunctions:
    """Test extraction helper functions."""
    
    def test_extract_draft_id(self):
        """Test extract_draft_id function."""
        from munshi.band.commands import extract_draft_id
        
        text = "[DRAFT A-231] To Priya (Reddy Traders)"
        result = extract_draft_id(text)
        
        assert result == "A-231"
    
    def test_extract_draft_id_none(self):
        """Test extract_draft_id with no match."""
        from munshi.band.commands import extract_draft_id
        
        text = "No draft here"
        result = extract_draft_id(text)
        
        assert result is None
    
    def test_extract_risk_customer(self):
        """Test extract_risk_customer function."""
        from munshi.band.commands import extract_risk_customer
        
        text = "[RISK] Reddy Traders: Watch → High. Signals: test. Suggest: check."
        result = extract_risk_customer(text)
        
        assert result == "Reddy Traders"
    
    def test_extract_risk_customer_none(self):
        """Test extract_risk_customer with no match."""
        from munshi.band.commands import extract_risk_customer
        
        text = "No risk here"
        result = extract_risk_customer(text)
        
        assert result is None
