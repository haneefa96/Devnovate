"""
Munshi - Test bank setup configuration
"""

import pytest

from munshi.memory.bank_setup import (
    get_bank_name,
    get_bank_directives,
    get_retain_mission,
    get_observations_mission,
    get_reflect_mission,
    get_disposition,
    get_bank_config,
    validate_bank_name,
)


class TestGetBankName:
    """Test bank name generation."""
    
    def test_production_bank_name(self):
        """Test production bank name format."""
        name = get_bank_name("acme-suppliers")
        assert name == "munshi-acme-suppliers"
    
    def test_demo_bank_name(self):
        """Test demo bank name format."""
        name = get_bank_name("acme-suppliers", is_demo=True)
        assert name == "munshi-acme-suppliers"
    
    def test_evaluation_bank_name(self):
        """Test evaluation bank name format."""
        name = get_bank_name("run-123", run_id="run-123", seed=42)
        assert name == "eval-run-123-C-s42"
    
    def test_evaluation_bank_name_with_demo(self):
        """Test that evaluation overrides demo flag."""
        name = get_bank_name("run-123", is_demo=True, run_id="run-123", seed=42)
        assert name == "eval-run-123-C-s42"
    
    def test_empty_business_slug(self):
        """Test empty business slug."""
        name = get_bank_name("")
        assert name == "munshi-"


class TestGetBankDirectives:
    """Test bank directives."""
    
    def test_directives_count(self):
        """Test that all 6 directives are present."""
        directives = get_bank_directives()
        assert len(directives) == 6
    
    def test_directives_content(self):
        """Test directive content."""
        directives = get_bank_directives()
        
        # Check for key requirements
        assert "legal action" in directives[0].lower()
        assert "09:00-19:00 IST" in directives[1]
        assert "one customer's information" in directives[2]
        assert "invoice is valid" in directives[3]
        assert "evidence" in directives[4]
        assert "MSME" in directives[5]
    
    def test_directives_are_strings(self):
        """Test that directives are strings."""
        directives = get_bank_directives()
        assert all(isinstance(d, str) for d in directives)


class TestGetRetainMission:
    """Test retain mission string."""
    
    def test_retain_mission_contains_payment(self):
        """Test retain mission mentions payment."""
        mission = get_retain_mission()
        assert "payment" in mission.lower()
    
    def test_retain_mission_contains_contact(self):
        """Test retain mission mentions contact changes."""
        mission = get_retain_mission()
        assert "contact" in mission.lower()
    
    def test_retain_mission_ignores_small_talk(self):
        """Test retain mission mentions ignoring small talk."""
        mission = get_retain_mission()
        assert "small talk" in mission.lower() or "greetings" in mission.lower()


class TestGetObservationsMission:
    """Test observations mission string."""
    
    def test_observations_mission_contains_timing(self):
        """Test observations mission mentions timing."""
        mission = get_observations_mission()
        assert "timing" in mission.lower() or "payment" in mission.lower()
    
    def test_observations_mission_contains_follow_ups(self):
        """Test observations mission mentions follow-ups."""
        mission = get_observations_mission()
        assert "follow" in mission.lower()


class TestGetReflectMission:
    """Test reflect mission string."""
    
    def test_reflect_mission_contains_business_name(self):
        """Test reflect mission includes business name."""
        mission = get_reflect_mission("Acme Suppliers")
        assert "Acme Suppliers" in mission
    
    def test_reflect_mission_contains_munshi(self):
        """Test reflect mission mentions Munshi."""
        mission = get_reflect_mission("Acme Suppliers")
        assert "Munshi" in mission
    
    def test_reflect_mission_contains_recommendation(self):
        """Test reflect mission mentions recommendations."""
        mission = get_reflect_mission("Acme Suppliers")
        assert "recommendation" in mission.lower()


class TestGetDisposition:
    """Test disposition traits."""
    
    def test_disposition_has_skepticism(self):
        """Test skepticism trait exists."""
        disposition = get_disposition()
        assert "skepticism" in disposition
        assert isinstance(disposition["skepticism"], int)
    
    def test_disposition_has_literalism(self):
        """Test literalism trait exists."""
        disposition = get_disposition()
        assert "literalism" in disposition
        assert isinstance(disposition["literalism"], int)
    
    def test_disposition_has_empathy(self):
        """Test empathy trait exists."""
        disposition = get_disposition()
        assert "empathy" in disposition
        assert isinstance(disposition["empathy"], int)
    
    def test_disposition_values_in_range(self):
        """Test disposition values are in valid range (1-5)."""
        disposition = get_disposition()
        for key, value in disposition.items():
            assert 1 <= value <= 5, f"{key} should be between 1 and 5"


class TestGetBankConfig:
    """Test complete bank configuration."""
    
    def test_config_has_all_sections(self):
        """Test config contains all required sections."""
        config = get_bank_config("test-bank")
        assert "directives" in config
        assert "retained_mission" in config
        assert "observations_mission" in config
        assert "reflect_mission" in config
        assert "disposition" in config
    
    def test_config_business_name(self):
        """Test config uses business name."""
        config = get_bank_config("test-bank", "Acme Suppliers")
        assert "Acme Suppliers" in config["reflect_mission"]
    
    def test_config_directives_count(self):
        """Test config directives count."""
        config = get_bank_config("test-bank")
        assert len(config["directives"]) == 6


class TestValidateBankName:
    """Test bank name validation."""
    
    def test_valid_production_name(self):
        """Test valid production name."""
        assert validate_bank_name("munshi-acme-suppliers") is True
        assert validate_bank_name("munshi-test-123") is True
    
    def test_valid_evaluation_name(self):
        """Test valid evaluation name."""
        assert validate_bank_name("eval-run-1-C-s42") is True
        assert validate_bank_name("eval-abc-C-s1") is True
    
    def test_invalid_name_missing_prefix(self):
        """Test invalid name without prefix."""
        assert validate_bank_name("acme-suppliers") is False
        assert validate_bank_name("test-bank") is False
    
    def test_invalid_name_wrong_format(self):
        """Test invalid name format."""
        assert validate_bank_name("munshi_") is False
        assert validate_bank_name("eval-run-C-s") is False
        assert validate_bank_name("eval-1-C-s") is False
    
    def test_empty_name(self):
        """Test empty name."""
        assert validate_bank_name("") is False
        assert validate_bank_name(None) is False
    
    def test_none_name(self):
        """Test None name."""
        assert validate_bank_name(None) is False
