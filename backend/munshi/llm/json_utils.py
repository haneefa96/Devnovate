"""
Munshi - JSON utilities

This module handles JSON schema validation and function calling wrappers.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Type, List
from datetime import datetime

from pydantic import BaseModel, ValidationError, Field

logger = logging.getLogger(__name__)


def validate_json_schema(data: Dict[str, Any], schema: Type[BaseModel]) -> Optional[BaseModel]:
    """
    Validate JSON against Pydantic schema.
    
    Args:
        data: Raw dictionary
        schema: Pydantic model class
    
    Returns:
        Validated model instance or None if invalid
    """
    try:
        return schema(**data)
    except ValidationError as e:
        logger.warning(f"Schema validation error: {e}")
        return None


def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from text response.
    
    Handles cases where LLM returns JSON in code blocks or with extra text.
    
    Args:
        text: Response text
    
    Returns:
        Parsed JSON or None
    """
    if not text:
        return None
    
    try:
        # Try to find JSON in markdown code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
        
        # Try to find JSON without code blocks (simple case)
        if text.strip().startswith("{"):
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                text = match.group(1)
        
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"JSON parse error: {e}")
        return None


def format_json_for_llm(schema: Type[BaseModel], strict: bool = False) -> Dict[str, Any]:
    """
    Format Pydantic schema for LLM JSON mode.
    
    Args:
        schema: Pydantic model class
        strict: Whether to require strict schema adherence
    
    Returns:
        Response format dict for Groq API
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "strict": strict,
            "schema": schema.model_json_schema(),
        },
    }


def format_json_mode_for_llm() -> Dict[str, Any]:
    """
    Get simple JSON mode for models that don't support structured outputs.
    
    Returns:
        Response format dict for Groq API
    """
    return {
        "type": "json_object",
    }


def validate_enum(value: str, enum_class) -> bool:
    """
    Validate value against enum.
    
    Args:
        value: Value to validate
        enum_class: Enum class
    
    Returns:
        True if valid
    """
    try:
        enum_class(value)
        return True
    except ValueError:
        return False


def safe_dict_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.
    
    Args:
        data: Dictionary
        key: Key (supports dot notation like "user.name")
        default: Default value if not found
    
    Returns:
        Value or default
    """
    if not data or not isinstance(data, dict):
        return default
    
    keys = key.split(".")
    value = data
    
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, default)
        else:
            return default
    
    return value if value is not None else default


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON from text response.
    
    Handles cases where LLM returns JSON in code blocks or with extra text.
    
    Args:
        text: Response text
    
    Returns:
        JSON string or None
    """
    if not text:
        return None
    
    # Try to find JSON in markdown code blocks
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    
    # Try to find JSON without code blocks
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        return match.group(1)
    
    return None


def parse_response_with_schema(
    response_text: str,
    schema: Type[BaseModel],
    strict: bool = True,
) -> Optional[BaseModel]:
    """
    Parse LLM response and validate against schema.
    
    Args:
        response_text: Raw response text
        schema: Pydantic model class
        strict: Whether to use strict parsing
    
    Returns:
        Validated model instance or None
    """
    # Extract JSON from text
    json_str = extract_json_from_text(response_text)
    if not json_str:
        json_str = response_text
    
    try:
        # Try parsing as JSON
        data = json.loads(json_str)
        
        # Validate against schema
        return schema(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        if strict:
            logger.warning(f"Failed to parse response: {e}")
        return None


def validate_response_keys(
    response: Dict[str, Any],
    required_keys: List[str],
    optional_keys: List[str] = None,
) -> bool:
    """
    Validate response has required keys.
    
    Args:
        response: Response dict
        required_keys: Keys that must be present
        optional_keys: Keys that may be present
    
    Returns:
        True if valid
    """
    if not response:
        return False
    
    for key in required_keys:
        if key not in response:
            logger.warning(f"Missing required key: {key}")
            return False
    
    if optional_keys:
        for key in response:
            if key not in required_keys and key not in optional_keys:
                logger.warning(f"Unexpected key in response: {key}")
    
    return True


def get_fallback_response(
    schema: Type[BaseModel],
    reason: str = "Groq unavailable",
) -> Dict[str, Any]:
    """
    Get fallback response when LLM is unavailable.
    
    Args:
        schema: Expected response schema
        reason: Reason for fallback
    
    Returns:
        Fallback response dict
    """
    return {
        "content": f"Fallback: {reason}",
        "raw": None,
        "parsed": None,
        "fallback": True,
        "fallback_reason": reason,
    }


def truncate_response(
    response: str,
    max_length: int = 8000,
    suffix: str = "...",
) -> str:
    """
    Truncate response to max length.
    
    Args:
        response: Response text
        max_length: Maximum length
        suffix: Suffix to append if truncated
    
    Returns:
        Truncated response
    """
    if len(response) <= max_length:
        return response
    return response[:max_length - len(suffix)] + suffix
