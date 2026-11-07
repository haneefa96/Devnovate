"""
Munshi - Test memory parsing utilities
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from munshi.memory.parsing import (
    Requirement,
    Conflict,
    Playbook,
    ReflectResponse,
    parse_reflect_response,
    parse_playbook,
    parse_memory_events,
    extract_requirements_from_text,
    validate_timestamp,
)


class TestRequirement:
    """Test Requirement model."""
    
    def test_requirement_valid(self):
        """Test valid requirement."""
        req = Requirement(
            code="req_1",
            description="Need GSTIN",
            required=True,
            evidence_ids=["doc_1"],
            evidence_count=1,
        )
        assert req.code == "req_1"
        assert req.description == "Need GSTIN"
    
    def test_requirement_minimal(self):
        """Test minimal requirement."""
        req = Requirement(
            code="req_1",
            description="Test",
        )
        assert req.code == "req_1"
        assert req.required is True
        assert req.evidence_ids == []
    
    def test_requirement_invalid_code(self):
        """Test invalid requirement code."""
        with pytest.raises(ValidationError):
            Requirement(description="Test")


class TestConflict:
    """Test Conflict model."""
    
    def test_conflict_valid(self):
        """Test valid conflict."""
        conf = Conflict(
            code="conf_1",
            description="GSTIN not provided",
            evidence_ids=["doc_1"],
        )
        assert conf.code == "conf_1"
        assert conf.description == "GSTIN not provided"
    
    def test_conflict_minimal(self):
        """Test minimal conflict."""
        conf = Conflict(
            code="conf_1",
            description="Test",
        )
        assert conf.code == "conf_1"
        assert conf.evidence_ids == []


class TestPlaybook:
    """Test Playbook model."""
    
    def test_playbook_valid(self):
        """Test valid playbook."""
        playbook = Playbook(
            title="Payment Collection",
            steps=["Call customer", "Send reminder"],
            key_points=["Be polite"],
            warnings=["Don't threaten legal action"],
        )
        assert playbook.title == "Payment Collection"
        assert len(playbook.steps) == 2
    
    def test_playbook_minimal(self):
        """Test minimal playbook."""
        playbook = Playbook()
        assert playbook.title == ""
        assert playbook.steps == []


class TestReflectResponse:
    """Test ReflectResponse model."""
    
    def test_response_valid(self):
        """Test valid response."""
        response = ReflectResponse(
            requirements=[
                Requirement(code="req_1", description="Need GSTIN"),
            ],
            conflicts=[
                Conflict(code="conf_1", description="GSTIN not provided"),
            ],
            playbook="Ask for GSTIN first",
        )
        assert len(response.requirements) == 1
        assert len(response.conflicts) == 1
        assert response.playbook == "Ask for GSTIN first"
    
    def test_response_empty(self):
        """Test empty response."""
        response = ReflectResponse()
        assert response.requirements == []
        assert response.conflicts == []
        assert response.playbook == ""


class TestParseReflectResponse:
    """Test parse_reflect_response function."""
    
    def test_parse_valid_response(self):
        """Test parsing valid response."""
        raw = {
            "requirements": [
                {"code": "req_1", "description": "Need GSTIN"},
            ],
            "conflicts": [
                {"code": "conf_1", "description": "GSTIN not provided"},
            ],
            "playbook": "Ask for GSTIN first",
        }
        
        result = parse_reflect_response(raw)
        
        assert len(result.requirements) == 1
        assert result.requirements[0].code == "req_1"
        assert result.playbook == "Ask for GSTIN first"
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        raw = {}
        result = parse_reflect_response(raw)
        
        assert result.requirements == []
        assert result.conflicts == []
        assert result.playbook == ""
    
    def test_parse_string_requirements(self):
        """Test parsing requirements as strings."""
        raw = {
            "requirements": ["Need GSTIN", "Need delivery address"],
            "conflicts": [],
            "playbook": "",
        }
        
        result = parse_reflect_response(raw)
        
        assert len(result.requirements) == 2
        assert result.requirements[0].code == "req_0"
        assert "Need GSTIN" in result.requirements[0].description
    
    def test_parse_string_conflicts(self):
        """Test parsing conflicts as strings."""
        raw = {
            "requirements": [],
            "conflicts": ["GSTIN not provided"],
            "playbook": "",
        }
        
        result = parse_reflect_response(raw)
        
        assert len(result.conflicts) == 1
        assert result.conflicts[0].code == "conf_0"
        assert "GSTIN not provided" in result.conflicts[0].description


class TestParsePlaybook:
    """Test parse_playbook function."""
    
    def test_parse_json_playbook(self):
        """Test parsing JSON playbook."""
        playbook_text = """{
            "title": "Payment Collection",
            "steps": ["Call customer", "Send reminder"],
            "key_points": ["Be polite"],
            "warnings": ["Don't threaten legal action"]
        }"""
        
        result = parse_playbook(playbook_text)
        
        assert result.title == "Payment Collection"
        assert len(result.steps) == 2
    
    def test_parse_text_playbook_with_steps(self):
        """Test parsing text playbook with steps."""
        playbook_text = """
Steps:
- Call customer
- Send reminder
Key Points:
- Be polite
Warnings:
- Don't threaten legal action
"""
        
        result = parse_playbook(playbook_text)
        
        assert len(result.steps) == 2
        assert len(result.key_points) == 1
        assert len(result.warnings) == 1
    
    def test_parse_text_playbook_plain(self):
        """Test parsing plain text playbook."""
        playbook_text = "Call customer. Send reminder. Be polite."
        
        result = parse_playbook(playbook_text)
        
        # Plain text becomes the playbook without parsing
        assert result.title == "Payment Collection Playbook"


class TestParseMemoryEvents:
    """Test parse_memory_events function."""
    
    def test_parse_basic_events(self):
        """Test parsing basic events."""
        events = [
            {
                "document_id": "doc_1",
                "timestamp": datetime(2024, 1, 15, 10, 30, 0),
                "content": "Sent invoice INV-001",
                "tags": ["customer:cust_1", "kind:action"],
            },
        ]
        
        result = parse_memory_events(events)
        
        assert len(result) == 1
        assert result[0]["id"] == "doc_1"
        assert result[0]["content"] == "Sent invoice INV-001"
    
    def test_parse_events_missing_fields(self):
        """Test parsing events with missing fields."""
        events = [
            {
                "content": "Sent invoice",
            },
        ]
        
        result = parse_memory_events(events)
        
        assert len(result) == 1
        assert result[0]["content"] == "Sent invoice"
        assert result[0]["id"] is None
    
    def test_parse_events_with_id(self):
        """Test parsing events with 'id' field."""
        events = [
            {
                "id": "doc_1",
                "content": "Sent invoice",
            },
        ]
        
        result = parse_memory_events(events)
        
        assert result[0]["id"] == "doc_1"


class TestExtractRequirementsFromText:
    """Test extract_requirements_from_text function."""
    
    def test_extract_numbered_requirements(self):
        """Test extracting numbered requirements."""
        text = """
1. Need GSTIN
2. Need delivery address
3. Payment must be within 30 days
"""
        
        result = extract_requirements_from_text(text)
        
        assert len(result) == 3
        assert "Need GSTIN" in result[0].description
        assert "delivery address" in result[1].description
    
    def test_extract_bulleted_requirements(self):
        """Test extracting bulleted requirements."""
        text = """
- Need GSTIN
- Need delivery address
"""
        
        result = extract_requirements_from_text(text)
        
        assert len(result) >= 2
    
    def test_extract_empty_text(self):
        """Test extracting from empty text."""
        result = extract_requirements_from_text("")
        
        assert result == []


class TestValidateTimestamp:
    """Test validate_timestamp function."""
    
    def test_validate_datetime(self):
        """Test validating datetime object."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = validate_timestamp(dt)
        
        assert result == dt
    
    def test_validate_iso_string(self):
        """Test validating ISO string."""
        result = validate_timestamp("2024-01-15T10:30:00")
        
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_validate_date_string(self):
        """Test validating date string."""
        result = validate_timestamp("2024-01-15")
        
        assert result is not None
        assert result.year == 2024
    
    def test_validate_invalid_string(self):
        """Test validating invalid string."""
        result = validate_timestamp("invalid")
        
        assert result is None
    
    def test_validate_none(self):
        """Test validating None."""
        result = validate_timestamp(None)
        
        assert result is None
