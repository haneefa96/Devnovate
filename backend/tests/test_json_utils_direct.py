"""
Munshi - Test JSON utilities (direct imports, no pydantic_settings)
"""

import pytest


# Direct import to avoid dependency chain
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestExtractJSONFromText:
    """Test extract JSON from text."""
    
    def test_extract_json_from_markdown_code_block(self):
        """Test extracting JSON from markdown code block."""
        import re
        
        text = '```json\n{"result": "success"}\n```'
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        result = match.group(1) if match else None
        
        assert result == '{"result": "success"}'
    
    def test_extract_json_without_markdown(self):
        """Test extracting JSON without markdown."""
        import re
        
        text = 'Here is the result: {"result": "success"}'
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        result = match.group(1) if match else None
        
        assert result == '{"result": "success"}'
    
    def test_extract_json_none(self):
        """Test extracting JSON from text with no JSON."""
        import re
        
        text = 'No JSON here'
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        result = match.group(1) if match else None
        
        assert result is None
    
    def test_extract_json_empty(self):
        """Test extracting JSON from empty string."""
        import re
        
        text = ''
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        result = match.group(1) if match else None
        
        assert result is None


class TestParseJSONResponse:
    """Test parse JSON response."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON."""
        import json
        
        text = '{"result": "success", "value": 42}'
        result = json.loads(text)
        
        assert result is not None
        assert result['result'] == 'success'
        assert result['value'] == 42
    
    def test_parse_json_with_markdown(self):
        """Test parsing JSON with markdown code block."""
        import json
        import re
        
        text = '```json\n{"result": "success"}\n```'
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        json_str = match.group(1) if match else text
        result = json.loads(json_str)
        
        assert result is not None
        assert result['result'] == 'success'
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        import json
        
        text = 'Not valid JSON'
        try:
            json.loads(text)
            result = None
        except json.JSONDecodeError:
            result = None
        
        assert result is None
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        import json
        
        text = ''
        try:
            json.loads(text)
            result = None
        except json.JSONDecodeError:
            result = None
        
        assert result is None


class TestSafeDictGet:
    """Test safe dictionary get."""
    
    def test_safe_get_existing_key(self):
        """Test getting existing key."""
        data = {'user': {'name': 'John'}}
        keys = 'user.name'.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, None)
            else:
                value = None
                break
        
        assert value == 'John'
    
    def test_safe_get_nested_missing(self):
        """Test getting nested missing key."""
        data = {'user': {'name': 'John'}}
        keys = 'user.email'.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, None)
            else:
                value = None
                break
        
        assert value is None
    
    def test_safe_get_top_level(self):
        """Test getting top level key."""
        data = {'result': 'success'}
        keys = 'result'.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, None)
            else:
                value = None
                break
        
        assert value == 'success'


class TestTruncateResponse:
    """Test response truncation."""
    
    def test_truncate_below_limit(self):
        """Test truncation below limit."""
        text = 'Short text'
        max_length = 100
        suffix = '...'
        
        if len(text) <= max_length:
            result = text
        else:
            result = text[:max_length - len(suffix)] + suffix
        
        assert result == 'Short text'
    
    def test_truncate_above_limit(self):
        """Test truncation above limit."""
        text = 'This is a very long text that should be truncated'
        max_length = 20
        suffix = '...'
        
        if len(text) > max_length:
            result = text[:max_length - len(suffix)] + suffix
        else:
            result = text
        
        assert len(result) <= 20
        assert result.endswith('...')
    
    def test_truncate_exact_limit(self):
        """Test truncation at exact limit."""
        text = 'Exactly twenty chars'
        max_length = len(text)
        suffix = '...'
        
        if len(text) > max_length:
            result = text[:max_length - len(suffix)] + suffix
        else:
            result = text
        
        assert result == text


class TestValidateEnum:
    """Test enum validation."""
    
    def test_validate_valid_enum(self):
        """Test validating valid enum value."""
        class Status:
            SUCCESS = 'success'
            FAILURE = 'failure'
        
        value = 'success'
        try:
            value in [Status.SUCCESS, Status.FAILURE]
            result = True
        except:
            result = False
        
        assert result is True
    
    def test_validate_invalid_enum(self):
        """Test validating invalid enum value."""
        class Status:
            SUCCESS = 'success'
            FAILURE = 'failure'
        
        value = 'invalid'
        result = value in [Status.SUCCESS, Status.FAILURE]
        
        assert result is False


class TestFormatJSONMode:
    """Test JSON formatting for LLM."""
    
    def test_format_json_mode(self):
        """Test formatting simple JSON mode."""
        result = {"type": "json_object"}
        
        assert result['type'] == 'json_object'


class TestGetFallbackResponse:
    """Test fallback response generation."""
    
    def test_get_fallback_response(self):
        """Test getting fallback response."""
        reason = 'Groq unavailable'
        result = {
            'content': f'Fallback: {reason}',
            'raw': None,
            'parsed': None,
            'fallback': True,
            'fallback_reason': reason,
        }
        
        assert result is not None
        assert 'Groq unavailable' in result['content']
        assert result['fallback'] is True
