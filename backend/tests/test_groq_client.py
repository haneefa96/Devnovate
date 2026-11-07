"""
Munshi - Test Groq client integration
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pydantic import BaseModel


@pytest.fixture(autouse=True)
def isolate_groq_credentials(monkeypatch):
    """Keep local credentials out of tests and prevent accidental live requests."""
    from munshi.config import settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GROQ_AGENT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "GROQ_CUSTOMER_MODEL", "qwen/qwen3-32b")
    monkeypatch.setattr(settings, "GROQ_BASE_URL", "https://api.groq.com")


class TestGroqClientInitialization:
    """Test GroqClient initialization."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.llm import groq_client as gc_module
        gc_module.GroqClient._instance = None
        yield
        gc_module.GroqClient._instance = None
    
    def test_client_singleton(self):
        """Test that GroqClient is a singleton."""
        from munshi.llm.groq_client import get_groq_client, GroqClient
        
        client1 = get_groq_client()
        client2 = get_groq_client()
        
        assert client1 is client2
        assert isinstance(client1, GroqClient)
    
    def test_client_not_available_without_api_key(self):
        """Test client is not available without API key."""
        from munshi.config import settings
        from munshi.llm.groq_client import get_groq_client

        with patch.object(settings, "GROQ_API_KEY", None):
            client = get_groq_client()
            assert client._is_available is False

    def test_client_uses_config_env_vars(self):
        """Test client reads environment variables."""
        from munshi.config import settings
        from munshi.llm.groq_client import get_groq_client

        with patch.multiple(
            settings,
            GROQ_API_KEY="test-key",
            GROQ_AGENT_MODEL="openai/gpt-oss-20b",
            GROQ_CUSTOMER_MODEL="qwen/qwen3.8-27b",
        ):
            client = get_groq_client()
            
            assert client._api_key == 'test-key'
            assert client._agent_model == 'openai/gpt-oss-20b'
            assert client._customer_model == 'qwen/qwen3.8-27b'
    
    def test_get_groq_client_function(self):
        """Test get_groq_client function."""
        from munshi.llm.groq_client import get_groq_client, is_groq_available
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            available = is_groq_available()
            
            assert client is not None
            assert available is True


class TestModelCapabilities:
    """Test model capabilities."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.llm import groq_client as gc_module
        gc_module.GroqClient._instance = None
        yield
        gc_module.GroqClient._instance = None
    
    def test_gpt_oss_120b_capabilities(self):
        """Test GPT-OSS 120B capabilities."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            caps = client.get_model_capabilities('openai/gpt-oss-120b')
            
            assert caps['name'] == 'GPT-OSS 120B'
            assert caps['supports_strict_output'] is True
            assert caps['supports_json_schema'] is True
            assert caps['max_output_tokens'] == 65536
            assert caps['rate_limit_rpm'] == 30
            assert caps['rate_limit_tpm'] == 8000
            assert caps['context_window'] == 131072
    
    def test_qwen_3_8_27b_capabilities(self):
        """Test Qwen 3.8 27B capabilities."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            caps = client.get_model_capabilities('qwen/qwen3.8-27b')
            
            assert caps['name'] == 'Qwen 3.8 27B'
            assert caps['supports_strict_output'] is True
            assert caps['supports_json_schema'] is True
    
    def test_qwen3_32b_capabilities(self):
        """Test Qwen3 32B capabilities."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            caps = client.get_model_capabilities('qwen/qwen3-32b')
            
            assert caps['name'] == 'Qwen3 32B'
            # Note: qwen3-32b doesn't support strict output
            assert caps['supports_strict_output'] is False
            assert caps['supports_json_schema'] is False
    
    def test_unknown_model_capabilities(self):
        """Test unknown model gets defaults."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            caps = client.get_model_capabilities('unknown/model')
            
            assert caps['supports_strict_output'] is False
            assert caps['supports_json_schema'] is False
            assert caps['max_output_tokens'] == 32768


class TestChatCompletion:
    """Test chat completion method."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.llm import groq_client as gc_module
        gc_module.GroqClient._instance = None
        yield
        gc_module.GroqClient._instance = None
    
    @pytest.mark.asyncio
    async def test_successful_completion(self):
        """Test successful chat completion."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            
            # Mock the Groq client
            mock_groq = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"result": "success"}'
            mock_response.headers = {}
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            mock_response.usage.total_tokens = 30
            mock_groq.chat.completions.create.return_value = mock_response
            
            with patch('munshi.llm.groq_client.Groq', return_value=mock_groq):
                result = await client.create_chat_completion(
                    model='openai/gpt-oss-120b',
                    messages=[{'role': 'user', 'content': 'Test'}],
                )
                
                assert result['content'] == '{"result": "success"}'
                assert result['fallback'] is False
    
    @pytest.mark.asyncio
    async def test_completion_with_structured_output(self):
        """Test completion with Pydantic model."""
        from munshi.llm.groq_client import get_groq_client
        
        class TestSchema(BaseModel):
            result: str
            confidence: float
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            
            mock_groq = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"result": "success", "confidence": 0.95}'
            mock_response.headers = {}
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            mock_response.usage.total_tokens = 30
            mock_groq.chat.completions.create.return_value = mock_response
            
            with patch('munshi.llm.groq_client.Groq', return_value=mock_groq):
                result = await client.create_chat_completion(
                    model='openai/gpt-oss-120b',
                    messages=[{'role': 'user', 'content': 'Test'}],
                    response_format=TestSchema,
                )
                
                assert result['content'] == '{"result": "success", "confidence": 0.95}'
                assert result['parsed'] is not None
                assert result['parsed'].result == 'success'
                assert result['parsed'].confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_completion_fallback_on_unavailable(self):
        """Test completion fallback when Groq unavailable."""
        from munshi.config import settings
        from munshi.llm.groq_client import get_groq_client
        
        with patch.object(settings, "GROQ_API_KEY", None):
            client = get_groq_client()
            
            result = await client.create_chat_completion(
                model='openai/gpt-oss-120b',
                messages=[{'role': 'user', 'content': 'Test'}],
            )
            
            assert result['fallback'] is True
            assert 'Groq LLM unavailable' in result['content']
    
    @pytest.mark.asyncio
    async def test_completion_with_rate_limit_headers(self):
        """Test rate limit header parsing."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            
            mock_groq = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"result": "success"}'
            mock_response.headers = {
                'x-ratelimit-remaining-requests': '995',
                'x-ratelimit-reset-requests': '2m30s',
            }
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            mock_response.usage.total_tokens = 30
            mock_groq.chat.completions.create.return_value = mock_response
            
            with patch('munshi.llm.groq_client.Groq', return_value=mock_groq):
                await client.create_chat_completion(
                    model='openai/gpt-oss-120b',
                    messages=[{'role': 'user', 'content': 'Test'}],
                )
                
                assert client._rate_limit_remaining == 995
    
    @pytest.mark.asyncio
    async def test_completion_retry_on_error(self):
        """Test retry logic on API error."""
        from munshi.llm.groq_client import get_groq_client
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            client = get_groq_client()
            
            mock_groq = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"result": "success"}'
            mock_response.headers = {}
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            mock_response.usage.total_tokens = 30
            mock_groq.chat.completions.create.return_value = mock_response
            
            with patch('munshi.llm.groq_client.Groq', return_value=mock_groq):
                with patch('asyncio.sleep', AsyncMock()):
                    result = await client.create_chat_completion(
                        model='openai/gpt-oss-120b',
                        messages=[{'role': 'user', 'content': 'Test'}],
                        max_retries=3,
                    )
                    
                    assert result['fallback'] is False


class TestHelperFunctions:
    """Test helper functions."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        from munshi.llm import groq_client as gc_module
        gc_module.GroqClient._instance = None
        yield
        gc_module.GroqClient._instance = None
    
    @pytest.mark.asyncio
    async def test_generate_reminder_draft(self):
        """Test generate_reminder_draft function."""
        from munshi.llm.groq_client import generate_reminder_draft
        
        messages = [
            {'role': 'system', 'content': 'Generate a reminder draft'},
            {'role': 'user', 'content': 'Reminder for invoice INV-001'},
        ]
        
        with patch.dict('os.environ', {'GROQ_API_KEY': 'test-key'}):
            with patch('munshi.llm.groq_client.Groq') as MockGroq:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = '{"content": "Test", "phone_number": "+91..."}'
                mock_response.headers = {}
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 20
                mock_response.usage.total_tokens = 30
                mock_client.chat.completions.create.return_value = mock_response
                MockGroq.return_value = mock_client
                
                result = await generate_reminder_draft(messages)
                
                assert result is not None
                assert 'content' in result


class TestExtractJSON:
    """Test extract JSON from text."""
    
    def test_extract_json_from_markdown_code_block(self):
        """Test extracting JSON from markdown code block."""
        from munshi.llm.json_utils import extract_json_from_text
        
        text = '```json\n{"result": "success"}\n```'
        result = extract_json_from_text(text)
        
        assert result == '{"result": "success"}'
    
    def test_extract_json_without_markdown(self):
        """Test extracting JSON without markdown."""
        from munshi.llm.json_utils import extract_json_from_text
        
        text = 'Here is the result: {"result": "success"}'
        result = extract_json_from_text(text)
        
        assert result == '{"result": "success"}'
    
    def test_extract_json_none(self):
        """Test extracting JSON from text with no JSON."""
        from munshi.llm.json_utils import extract_json_from_text
        
        text = 'No JSON here'
        result = extract_json_from_text(text)
        
        assert result is None


class TestParseJSONResponse:
    """Test parse JSON response."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON."""
        from munshi.llm.json_utils import parse_json_response
        
        text = '{"result": "success", "value": 42}'
        result = parse_json_response(text)
        
        assert result is not None
        assert result['result'] == 'success'
        assert result['value'] == 42
    
    def test_parse_json_with_markdown(self):
        """Test parsing JSON with markdown code block."""
        from munshi.llm.json_utils import parse_json_response
        
        text = '```json\n{"result": "success"}\n```'
        result = parse_json_response(text)
        
        assert result is not None
        assert result['result'] == 'success'
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        from munshi.llm.json_utils import parse_json_response
        
        text = 'Not valid JSON'
        result = parse_json_response(text)
        
        assert result is None
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        from munshi.llm.json_utils import parse_json_response
        
        result = parse_json_response('')
        
        assert result is None


class TestValidateJSONSchema:
    """Test JSON schema validation."""
    
    class TestSchema(BaseModel):
        result: str
        value: int
    
    def test_validate_valid_schema(self):
        """Test validating valid schema."""
        from munshi.llm.json_utils import validate_json_schema
        
        data = {'result': 'success', 'value': 42}
        result = validate_json_schema(data, self.TestSchema)
        
        assert result is not None
        assert result.result == 'success'
        assert result.value == 42
    
    def test_validate_invalid_schema(self):
        """Test validating invalid schema."""
        from munshi.llm.json_utils import validate_json_schema
        
        data = {'result': 'success'}  # Missing 'value'
        result = validate_json_schema(data, self.TestSchema)
        
        assert result is None
    
    def test_validate_wrong_type(self):
        """Test validating wrong type."""
        from munshi.llm.json_utils import validate_json_schema
        
        data = {'result': 'success', 'value': 'not a number'}
        result = validate_json_schema(data, self.TestSchema)
        
        assert result is None


class TestSafeDictGet:
    """Test safe dictionary get."""
    
    def test_safe_get_existing_key(self):
        """Test getting existing key."""
        from munshi.llm.json_utils import safe_dict_get
        
        data = {'user': {'name': 'John'}}
        result = safe_dict_get(data, 'user.name')
        
        assert result == 'John'
    
    def test_safe_get_nested_missing(self):
        """Test getting nested missing key."""
        from munshi.llm.json_utils import safe_dict_get
        
        data = {'user': {'name': 'John'}}
        result = safe_dict_get(data, 'user.email')
        
        assert result is None
    
    def test_safe_get_top_level(self):
        """Test getting top level key."""
        from munshi.llm.json_utils import safe_dict_get
        
        data = {'result': 'success'}
        result = safe_dict_get(data, 'result')
        
        assert result == 'success'


class TestTruncateResponse:
    """Test response truncation."""
    
    def test_truncate_below_limit(self):
        """Test truncation below limit."""
        from munshi.llm.json_utils import truncate_response
        
        text = 'Short text'
        result = truncate_response(text, max_length=100)
        
        assert result == 'Short text'
    
    def test_truncate_above_limit(self):
        """Test truncation above limit."""
        from munshi.llm.json_utils import truncate_response
        
        text = 'This is a very long text that should be truncated'
        result = truncate_response(text, max_length=20)
        
        assert len(result) <= 20
        assert result.endswith('...')


class TestFormatJSONForLLM:
    """Test JSON formatting for LLM."""
    
    class TestSchema(BaseModel):
        result: str
    
    def test_format_json_for_llm(self):
        """Test formatting JSON for LLM."""
        from munshi.llm.json_utils import format_json_for_llm
        
        result = format_json_for_llm(self.TestSchema)
        
        assert result['type'] == 'json_schema'
        assert result['json_schema']['name'] == 'TestSchema'
        assert result['json_schema']['strict'] is False
    
    def test_format_json_for_llm_strict(self):
        """Test formatting JSON for LLM with strict mode."""
        from munshi.llm.json_utils import format_json_for_llm
        
        result = format_json_for_llm(self.TestSchema, strict=True)
        
        assert result['json_schema']['strict'] is True
    
    def test_format_json_mode(self):
        """Test formatting simple JSON mode."""
        from munshi.llm.json_utils import format_json_mode_for_llm
        
        result = format_json_mode_for_llm()
        
        assert result['type'] == 'json_object'
