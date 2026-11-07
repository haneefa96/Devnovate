"""
Munshi - Groq client wrapper

This module wraps the Groq SDK client.
IMPORTANT: Only this file may call Groq API.
"""

import logging
import asyncio
import time
import re
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from pydantic import BaseModel

from munshi.config import settings

try:
    from groq import Groq
except ImportError:
    Groq = None

logger = logging.getLogger(__name__)


# Model capabilities based on Groq documentation
# openai/gpt-oss-120b: Supports strict structured outputs, 65K output tokens, 250K TPM rate limit
# qwen/qwen3-32b: Supports structured outputs (strict: false), limited output tokens
# qwen/qwen3.8-27b: Better structured output support than qwen3-32b
SUPPORTED_MODELS = {
    "openai/gpt-oss-120b": {
        "name": "GPT-OSS 120B",
        "supports_strict_output": True,
        "supports_json_schema": True,
        "max_output_tokens": 65536,
        "rate_limit_rpm": 30,
        "rate_limit_tpm": 8000,
        "context_window": 131072,
    },
    "openai/gpt-oss-20b": {
        "name": "GPT-OSS 20B",
        "supports_strict_output": True,
        "supports_json_schema": True,
        "max_output_tokens": 65536,
        "rate_limit_rpm": 30,
        "rate_limit_tpm": 8000,
        "context_window": 131072,
    },
    "qwen/qwen3.8-27b": {
        "name": "Qwen 3.8 27B",
        "supports_strict_output": True,
        "supports_json_schema": True,
        "max_output_tokens": 16384,
        "rate_limit_rpm": 30,
        "rate_limit_tpm": 8000,
        "context_window": 131072,
    },
    "qwen/qwen3-32b": {
        "name": "Qwen3 32B",
        "supports_strict_output": False,
        "supports_json_schema": False,
        "max_output_tokens": 32768,
        "rate_limit_rpm": 30,
        "rate_limit_tpm": 8000,
        "context_window": 32768,
    },
    "llama-3.3-70b-versatile": {
        "name": "Llama 3.3 70B",
        "supports_strict_output": False,
        "supports_json_schema": False,
        "max_output_tokens": 32768,
        "rate_limit_rpm": 30,
        "rate_limit_tpm": 8000,
        "context_window": 131072,
    },
}


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class GroqRequestError(RuntimeError):
    """Sanitized provider error that never includes request credentials or body."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _sanitize_groq_error(error: Exception) -> GroqRequestError:
    status_code = getattr(error, "status_code", None)
    safe_detail = str(error).casefold()
    if status_code == 401:
        return GroqRequestError("INVALID_CREDENTIALS", "Groq rejected the configured credentials.")
    if status_code == 404 or (
        "model" in safe_detail
        and any(term in safe_detail for term in ("not found", "unavailable", "does not exist"))
    ):
        return GroqRequestError("MODEL_UNAVAILABLE", "The configured Groq model or endpoint is unavailable.")
    if status_code == 429:
        return GroqRequestError("RATE_LIMITED", "Groq rate limit was reached after retries.")
    if status_code in (400, 403):
        return GroqRequestError("INVALID_REQUEST", "Groq rejected the request or model configuration.")
    if status_code and status_code >= 500:
        return GroqRequestError("PROVIDER_UNAVAILABLE", "Groq is temporarily unavailable.")
    return GroqRequestError("PROVIDER_ERROR", "Groq request failed after retries.")


class GroqClient:
    """
    Wrapper around Groq SDK client.
    
    This class handles:
    - Client initialization
    - Model configuration
    - Retry logic with exponential backoff
    - Rate limit handling
    - Structured output support
    - Error handling and fallback
    
    Never call Groq API outside this file.
    """
    
    _instance: Optional["GroqClient"] = None
    
    def __new__(cls, *args: Any, **kwargs: Any):
        """Singleton pattern for client."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, client_factory: Optional[Callable[..., Any]] = None):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self._client = None
        self._is_available = False
        
        # Model configuration
        self._agent_model = settings.GROQ_AGENT_MODEL
        self._customer_model = settings.GROQ_CUSTOMER_MODEL
        self._api_key = settings.GROQ_API_KEY
        self._base_url = settings.GROQ_BASE_URL
        self._client_factory = client_factory if client_factory is not None else Groq
        
        # Rate limit tracking
        self._rate_limit_remaining = 1000
        self._rate_limit_reset_time = 0
        
        # Initialize client
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize Groq client."""
        if not self._api_key:
            logger.warning(
                "GROQ_API_KEY not set - using fallback mode. "
                "Set GROQ_API_KEY for production."
            )
            return
        if self._client_factory is None:
            logger.warning("groq SDK is unavailable; using deterministic fallback mode")
            return
        
        try:
            self._client = self._client_factory(
                api_key=self._api_key,
                base_url=self._base_url,
            )
            self._is_available = True
            logger.info("Groq client initialized successfully")
        except ImportError:
            logger.warning("groq SDK is unavailable; using deterministic fallback mode")
        except Exception as error:
            logger.error("Groq client initialization failed (%s)", type(error).__name__)
    
    @property
    def client(self):
        """Get Groq client instance. Raises if not available."""
        if not self._is_available:
            raise RuntimeError(
                "Groq client not initialized. "
                "Set GROQ_API_KEY environment variable."
            )
        return self._client
    
    @property
    def agent_model(self) -> str:
        """Get agent model ID."""
        return self._agent_model
    
    @property
    def customer_model(self) -> str:
        """Get customer model ID."""
        return self._customer_model
    
    def get_model_capabilities(self, model_id: str) -> Dict[str, Any]:
        """
        Get capabilities for a model.
        
        Args:
            model_id: Model identifier
        
        Returns:
            Dict with model capabilities
        """
        return SUPPORTED_MODELS.get(model_id, {
            "name": model_id,
            "supports_strict_output": False,
            "supports_json_schema": False,
            "max_output_tokens": 32768,
            "rate_limit_rpm": 30,
            "rate_limit_tpm": 8000,
            "context_window": 131072,
        })
    
    def _should_use_structured_output(self, model_id: str) -> bool:
        """Check if model supports structured outputs."""
        caps = self.get_model_capabilities(model_id)
        return caps.get("supports_json_schema", False)
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows new request."""
        if time.time() > self._rate_limit_reset_time:
            self._rate_limit_remaining = 1000
            return True
        if self._rate_limit_remaining > 0:
            self._rate_limit_remaining -= 1
            return True
        return False
    
    async def _wait_for_rate_limit(self) -> None:
        """Wait until rate limit resets."""
        if self._rate_limit_remaining <= 0:
            wait_time = max(1, self._rate_limit_reset_time - time.time() + 1)
            logger.warning(f"Waiting {wait_time}s for rate limit reset")
            await asyncio.sleep(wait_time)
            self._rate_limit_remaining = 1000
            self._rate_limit_reset_time = time.time() + 60
    
    def _extract_json_from_response(self, text: str) -> Optional[str]:
        """
        Extract JSON from LLM response.
        
        Handles cases where LLM returns JSON in code blocks or with extra text.
        
        Args:
            text: Response text
        
        Returns:
            JSON string or None
        """
        # Try to find JSON in markdown code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        
        # Try to find JSON without code blocks
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            return match.group(1)
        
        return None
    
    def _parse_rate_limit_headers(self, headers: Optional[Dict[str, str]]) -> None:
        """
        Parse rate limit headers from response.
        
        Args:
            headers: Response headers
        """
        if not headers:
            return
        
        # Parse retry-after
        retry_after = headers.get("retry-after")
        if retry_after:
            # Try to parse as seconds
            try:
                wait_time = float(retry_after)
                self._rate_limit_reset_time = time.time() + wait_time
            except ValueError:
                pass
        
        # Parse x-ratelimit-remaining-requests
        remaining = headers.get("x-ratelimit-remaining-requests")
        if remaining:
            try:
                self._rate_limit_remaining = int(remaining)
            except ValueError:
                pass
        
        # Parse x-ratelimit-reset-requests
        reset = headers.get("x-ratelimit-reset-requests")
        if reset:
            # Parse duration string like "2m30s"
            match = re.match(r'(\d+)m(\d+)s', reset)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                self._rate_limit_reset_time = time.time() + minutes * 60 + seconds
    
    async def create_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[type[BaseModel]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Create chat completion with retry logic.
        
        Args:
            model: Model ID (gpt-oss-120b or qwen3-32b)
            messages: Message history
            temperature: Sampling temperature
            response_format: Pydantic model for structured output
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries
        
        Returns:
            Parsed response dict with 'content', 'raw', and optionally 'parsed' fields
        
        Raises:
            GroqError: If all retries fail
        """
        if not self._is_available:
            logger.warning("Groq not available - using fallback mode")
            return {
                "content": "Groq LLM unavailable - using fallback response",
                "raw": None,
                "model": model,
                "fallback": True,
            }
        
        # Check model capabilities
        model_caps = self.get_model_capabilities(model)
        
        for attempt in range(max_retries):
            try:
                # Check rate limit
                if not self._check_rate_limit():
                    await self._wait_for_rate_limit()
                
                # Build request
                request = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                # Add structured output if supported
                if response_format and model_caps.get("supports_json_schema", False):
                    schema = response_format.model_json_schema()
                    request["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": response_format.__name__,
                            "strict": model_caps.get("supports_strict_output", False),
                            "schema": schema,
                        },
                    }
                    logger.debug(f"Using structured output with {model}")
                else:
                    # Fallback to JSON mode
                    request["response_format"] = {"type": "json_object"}
                
                # Make request
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    **request
                )
                
                # Parse rate limit headers
                self._parse_rate_limit_headers(dict(response.headers) if hasattr(response, 'headers') else {})
                
                # Extract content
                content = response.choices[0].message.content or ""
                
                # Try to parse as JSON
                parsed = None
                if response_format:
                    try:
                        # Clean JSON if needed
                        json_str = self._extract_json_from_response(content)
                        if json_str:
                            parsed = response_format.model_validate_json(json_str)
                        else:
                            parsed = response_format.model_validate_json(content)
                    except Exception as e:
                        logger.warning(
                            "Failed to parse Groq response as %s (%s)",
                            response_format.__name__,
                            type(e).__name__,
                        )
                
                return {
                    "content": content,
                    "raw": content,
                    "parsed": parsed,
                    "model": model,
                    "fallback": False,
                    "usage": {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if hasattr(response, "usage") else 0,
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if hasattr(response, "usage") else 0,
                        "total_tokens": getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") else 0,
                    },
                }
                
            except Exception as error:
                status_code = getattr(error, "status_code", None)
                logger.warning(
                    "Groq API request failed (attempt %s/%s, status=%s, type=%s)",
                    attempt + 1,
                    max_retries,
                    status_code or "unknown",
                    type(error).__name__,
                )
                
                # Handle rate limit specifically
                if status_code == 429 or "429" in str(error) or "rate limit" in str(error).lower():
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                
                # Handle unsupported model features
                if "structured" in str(error).lower() or "json_schema" in str(error).lower():
                    # Try fallback without structured output
                    if response_format and attempt < max_retries - 1:
                        logger.warning("Model doesn't support structured outputs, trying fallback")
                        result = await self.create_chat_completion(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            response_format=None,
                            max_retries=1,
                        )
                        return result
                    raise _sanitize_groq_error(error) from None

                if status_code in (400, 401, 403, 404):
                    raise _sanitize_groq_error(error) from None
                
                if attempt == max_retries - 1:
                    raise _sanitize_groq_error(error) from None
        
        return {
            "content": "Groq LLM unavailable after retries",
            "raw": None,
            "fallback": True,
        }
    
    async def call_agent_model(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[BaseModel] = None,
    ) -> Dict[str, Any]:
        """Call Groq with agent model."""
        return await self.create_chat_completion(
            model=self._agent_model,
            messages=messages,
            response_format=response_format,
        )
    
    async def call_customer_model(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Call Groq with customer model."""
        return await self.create_chat_completion(
            model=self._customer_model,
            messages=messages,
        )
    
    async def close(self) -> None:
        """Close Groq client."""
        if self._client:
            try:
                await asyncio.to_thread(self._client.close)
            except Exception as error:
                logger.warning("Groq client close failed (%s)", type(error).__name__)


def get_groq_client(
    client_factory: Optional[Callable[..., Any]] = None,
) -> GroqClient:
    """Get or create Groq client singleton."""
    return GroqClient(client_factory=client_factory)


def is_groq_available() -> bool:
    """Check if Groq service is available."""
    client = get_groq_client()
    return client._is_available


async def generate_reminder_draft(
    messages: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Generate reminder draft using Groq.
    
    Args:
        messages: Prompt messages
    
    Returns:
        Draft with phone_number, channel, message, and why fields
    """
    client = get_groq_client()
    return await client.call_agent_model(messages)


async def generate_evidence_based_message(
    customer_context: str,
    evidence: str,
    instruction: str,
) -> Dict[str, Any]:
    """
    Generate evidence-based customer message.
    
    Args:
        customer_context: Customer background
        evidence: Evidence from SQLite/Hindsight
        instruction: Action instruction
    
    Returns:
        Message with content and supporting evidence
    """
    messages = [
        {"role": "system", "content": "You are Munshi, helping generate customer communications."},
        {"role": "user", "content": f"""
Customer context: {customer_context}

Evidence:
{evidence}

Instruction: {instruction}

Generate a customer message that is evidence-based and follows our guidelines.
Output as JSON with: content, evidence_citations[]
"""}
    ]
    
    client = get_groq_client()
    return await client.call_agent_model(messages)


async def generate_risk_explanation(
    customer_id: str,
    risk_level: str,
    signals: List[str],
    suggestion: str,
) -> Dict[str, Any]:
    """
    Generate risk explanation for owner review.
    
    Args:
        customer_id: Customer identifier
        risk_level: Risk level (NORMAL/WATCH/HIGH)
        signals: Risk signals
        suggestion: Suggested action
    
    Returns:
        Explanation with rationale
    """
    messages = [
        {"role": "system", "content": "You are Munshi, explaining customer risk to the owner."},
        {"role": "user", "content": f"""
Customer {customer_id} risk assessment:
- Level: {risk_level}
- Signals: {", ".join(signals)}
- Suggestion: {suggestion}

Generate an explanation of why this risk was assigned and what the owner should consider.
Output as JSON with: explanation, key_factors[], action_items[]
"""}
    ]
    
    client = get_groq_client()
    return await client.call_agent_model(messages)


async def generate_agent_summary(
    task: str,
    context: str,
    findings: str,
) -> Dict[str, Any]:
    """
    Generate agent summary for owner review.
    
    Args:
        task: Task description
        context: Context information
        findings: Agent findings
    
    Returns:
        Summary with key points
    """
    messages = [
        {"role": "system", "content": "You are Munshi, summarizing agent work for the owner."},
        {"role": "user", "content": f"""
Task: {task}

Context:
{context}

Findings:
{findings}

Generate a concise summary of what was done and what the owner should know.
Output as JSON with: summary, key_points[], next_steps[]
"""}
    ]
    
    client = get_groq_client()
    return await client.call_agent_model(messages)


# Module-level client instance
groq_client = get_groq_client()
