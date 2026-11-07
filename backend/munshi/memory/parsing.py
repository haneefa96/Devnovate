"""
Munshi - Memory parsing utilities

This module handles LLM output parsing and JSON validation.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from pydantic import BaseModel, ValidationError, Field

logger = logging.getLogger(__name__)


class Requirement(BaseModel):
    """Requirement from memory reflect."""
    code: str = Field(..., description="Unique requirement code")
    description: str = Field(..., description="Description of the requirement")
    required: bool = Field(default=True, description="Whether this requirement must be met")
    evidence_ids: List[str] = Field(default_factory=list, description="Document IDs referencing this requirement")
    evidence_count: int = Field(default=0, description="Number of evidence documents")


class Conflict(BaseModel):
    """Conflict from memory reflect."""
    code: str = Field(..., description="Unique conflict code")
    description: str = Field(..., description="Description of the conflict")
    evidence_ids: List[str] = Field(default_factory=list, description="Document IDs referencing this conflict")


class Playbook(BaseModel):
    """Playbook derived from reflection."""
    title: str = Field(default="", description="Playbook title")
    steps: List[str] = Field(default_factory=list, description="Step-by-step instructions")
    key_points: List[str] = Field(default_factory=list, description="Key points to remember")
    warnings: List[str] = Field(default_factory=list, description="Warnings or cautions")


class ReflectResponse(BaseModel):
    """Response from memory reflect."""
    requirements: List[Requirement] = Field(default_factory=list, description="List of requirements")
    conflicts: List[Conflict] = Field(default_factory=list, description="List of conflicts")
    playbook: str = Field(default="", description="Playbook text (raw)")
    playbook_obj: Optional[Playbook] = Field(default=None, description="Parsed playbook object")


def parse_reflect_response(raw_response: Dict[str, Any]) -> ReflectResponse:
    """
    Parse raw reflect response into structured format.
    
    Args:
        raw_response: Raw dictionary from Hindsight
    
    Returns:
        Parsed ReflectResponse
    
    Raises:
        ValidationError: If response format is invalid
    """
    try:
        requirements = []
        for req in raw_response.get("requirements", []):
            if isinstance(req, dict):
                requirements.append(Requirement(**req))
            else:
                # Handle string-only requirements
                requirements.append(Requirement(
                    code=f"req_{len(requirements)}",
                    description=str(req),
                ))
        
        conflicts = []
        for conf in raw_response.get("conflicts", []):
            if isinstance(conf, dict):
                conflicts.append(Conflict(**conf))
            else:
                conflicts.append(Conflict(
                    code=f"conf_{len(conflicts)}",
                    description=str(conf),
                ))
        
        return ReflectResponse(
            requirements=requirements,
            conflicts=conflicts,
            playbook=raw_response.get("playbook", ""),
        )
    except ValidationError as e:
        logger.warning(f"Validation error parsing reflect response: {e}")
        # Return empty response with validation error logged
        return ReflectResponse()


def parse_playbook(playbook_text: str) -> Playbook:
    """
    Parse playbook text into structured format.
    
    Args:
        playbook_text: Raw playbook text
    
    Returns:
        Parsed Playbook object
    """
    # Try JSON first
    try:
        playbook_data = json.loads(playbook_text)
        return Playbook(**playbook_data)
    except (json.JSONDecodeError, ValidationError):
        pass
    
    # Parse as plain text
    steps = []
    key_points = []
    warnings = []
    
    current_section = None
    
    for line in playbook_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Detect sections
        if line.lower().startswith('steps:'):
            current_section = 'steps'
            continue
        elif line.lower().startswith('key points:'):
            current_section = 'key_points'
            continue
        elif line.lower().startswith('warnings:') or line.lower().startswith('cautions:'):
            current_section = 'warnings'
            continue
        
        # Parse list items
        if line.startswith('- ') or line.startswith('* '):
            item = line[2:].strip()
            if current_section == 'steps':
                steps.append(item)
            elif current_section == 'key_points':
                key_points.append(item)
            elif current_section == 'warnings':
                warnings.append(item)
        elif current_section == 'steps':
            steps.append(line)
    
    return Playbook(
        title="Payment Collection Playbook",
        steps=steps,
        key_points=key_points,
        warnings=warnings,
    )


def parse_memory_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse memory events into standardized format.
    
    Args:
        events: List of raw events from Hindsight
    
    Returns:
        List of parsed events
    """
    parsed = []
    for event in events:
        parsed.append({
            "id": event.get("document_id") or event.get("id"),
            "timestamp": event.get("timestamp"),
            "content": event.get("content"),
            "kind": event.get("kind")
            or next(
                (
                    tag.removeprefix("kind:")
                    for tag in event.get("tags", [])
                    if tag.startswith("kind:")
                ),
                None,
            ),
            "customer_id": event.get("customer_id")
            or event.get("metadata", {}).get("customer_id"),
            "invoice_id": event.get("invoice_id")
            or event.get("metadata", {}).get("invoice_id"),
            "metadata": event.get("metadata") or {},
            "tags": event.get("tags") or [],
        })
    return parsed


def extract_requirements_from_text(text: str) -> List[Requirement]:
    """
    Extract requirements from unstructured text.
    
    Args:
        text: Raw text containing requirements
    
    Returns:
        List of parsed requirements
    """
    requirements = []
    
    # Look for numbered or bulleted requirements
    lines = text.split('\n')
    current_req = None
    
    for line in lines:
        line = line.strip()
        
        # Match requirement patterns
        if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
            if current_req:
                requirements.append(current_req)
            req_text = line[3:].strip()
            current_req = Requirement(
                code=f"req_{len(requirements) + 1}",
                description=req_text,
            )
        elif line.startswith(('- ', '* ')):
            item = line[2:].strip()
            if current_req:
                current_req.description += " " + item
            else:
                requirements.append(Requirement(
                    code=f"req_{len(requirements) + 1}",
                    description=item,
                ))
    
    if current_req:
        requirements.append(current_req)
    
    return requirements


def validate_timestamp(timestamp: Any) -> Optional[datetime]:
    """
    Validate and convert timestamp to datetime.
    
    Args:
        timestamp: Timestamp in various formats
    
    Returns:
        datetime object or None if invalid
    """
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        # Try other common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                continue
    
    return None
