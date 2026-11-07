"""
Munshi - Band command parser

This module parses inbound Band messages using regex (not LLM).
Handles:
- Draft messages from Collector agent
- Risk alerts from Risk agent
- Handoff messages between agents
- Owner approval commands
"""

import re
from typing import Dict, Any, Optional, Tuple, List


# Draft pattern: [DRAFT A-231] To Priya, WhatsApp, today 10:30. <message>. Why: <evidence>.
DRAFT_PATTERN = re.compile(
    r"\[DRAFT\s+(\w+-\d+)\]\s+To\s+([^,]+),\s+([^,]+),\s+today\s+([^,]+)\.\s+(.+?)\s+Why:\s+(.+?)(?:\s+Reply:\s+(.+))?$",
    re.DOTALL,
)

# Risk pattern: [RISK] Reddy Traders: Watch → High. Signals: ... Suggest: ...
RISK_PATTERN = re.compile(
    r"\[RISK\]\s+([^:]+):\s+([^→]+)→\s+([^\.]+)\.\s+Signals:\s+(.+?)\.\s+Suggest:\s+(.+?)(?:\s+@owner)?$",
    re.DOTALL,
)

# Handoff pattern: @Risk reply from Rahul mentions cash-flow trouble on INV-1060, please assess
HANDOFF_PATTERN = re.compile(
    r"@Risk\s+(.+?)\s+on\s+(INV-\d+),\s+please\s+assess",
    re.DOTALL,
)

# Collector handoff pattern: @Collector please follow up on INV-1060 for customer
COLLECTOR_HANDOFF_PATTERN = re.compile(
    r"@Collector\s+(.+?)\s+on\s+(INV-\d+)",
    re.DOTALL,
)


def parse_draft_message(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse draft message from Band.
    
    Args:
        text: Raw message text
    
    Returns:
        Parsed data or None if not a draft
    """
    match = DRAFT_PATTERN.match(text.strip())
    if not match:
        return None
    
    return {
        "draft_id": match.group(1),
        "recipient": match.group(2).strip(),
        "channel": match.group(3).strip(),
        "time": match.group(4).strip(),
        "body": match.group(5).strip(),
        "evidence": match.group(6).strip() if match.group(6) else "",
        "actions": match.group(7) if match.group(7) else "",  # approve/edit/reject commands
    }


def parse_risk_message(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse risk message from Band.
    
    Args:
        text: Raw message text
    
    Returns:
        Parsed data or None if not a risk message
    """
    match = RISK_PATTERN.match(text.strip())
    if not match:
        return None
    
    signals_text = match.group(4).strip()
    signals = [s.strip() for s in re.split(r"[,;]", signals_text) if s.strip()]
    
    return {
        "customer": match.group(1).strip(),
        "from_level": match.group(2).strip(),
        "to_level": match.group(3).strip(),
        "signals": signals,
        "suggestion": match.group(5).strip(),
    }


def parse_handoff_message(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse handoff message (Collector → Risk).
    
    Args:
        text: Raw message text
    
    Returns:
        Parsed data or None if not a handoff
    """
    match = HANDOFF_PATTERN.search(text)
    if not match:
        return None
    
    return {
        "description": match.group(1).strip(),
        "invoice_id": match.group(2).strip(),
    }


def parse_collector_handoff(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse Collector handoff message.
    
    Args:
        text: Raw message text
    
    Returns:
        Parsed data or None if not a handoff
    """
    match = COLLECTOR_HANDOFF_PATTERN.search(text)
    if not match:
        return None
    
    return {
        "description": match.group(1).strip(),
        "invoice_id": match.group(2).strip(),
    }


def parse_owner_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse owner command (approve A-231, edit A-231: text, reject A-231).
    
    Args:
        text: Command text
    
    Returns:
        Parsed command data or None
    """
    # Pattern: approve A-231 / edit A-231: <text> / reject A-231
    approve_pattern = re.compile(r"approve\s+(\w+-\d+)")
    edit_pattern = re.compile(r"edit\s+(\w+-\d+):\s*(.+)")
    reject_pattern = re.compile(r"reject\s+(\w+-\d+)")
    
    if match := approve_pattern.search(text):
        return {"action": "approve", "draft_id": match.group(1)}
    if match := edit_pattern.search(text):
        return {"action": "edit", "draft_id": match.group(1), "text": match.group(2)}
    if match := reject_pattern.search(text):
        return {"action": "reject", "draft_id": match.group(1)}
    
    return None


def parse_band_message(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Parse any Band message.
    
    Args:
        text: Raw message text
    
    Returns:
        (message_type, parsed_data)
        message_type: "draft", "risk", "handoff", "collector_handoff", "command", "question", "unknown"
    """
    if draft := parse_draft_message(text):
        return "draft", draft
    if risk := parse_risk_message(text):
        return "risk", risk
    if handoff := parse_handoff_message(text):
        return "handoff", handoff
    if coll_handoff := parse_collector_handoff(text):
        return "collector_handoff", coll_handoff
    if command := parse_owner_command(text):
        return "command", command
    
    # Check if it's a plain question (no prefix)
    if text.strip() and not text.startswith("[") and not text.startswith("@"):
        return "question", {"text": text}
    
    return "unknown", None


def format_draft_message(draft_data: Dict[str, Any]) -> str:
    """
    Format draft data for Band post.
    
    Args:
        draft_data: Draft data from backend
    
    Returns:
        Formatted message string
    """
    return (
        f"[DRAFT {draft_data.get('id', 'unknown')}] "
        f"To {draft_data.get('recipient', 'unknown')} ({draft_data.get('customer', 'unknown')}), "
        f"{draft_data.get('channel', 'unknown')}, today {draft_data.get('time', 'unknown')}. "
        f"{draft_data.get('body', '')[:200]}... Why: {draft_data.get('evidence', '')[:100]}..."
    )


def format_risk_message(alert_data: Dict[str, Any]) -> str:
    """
    Format risk alert for Band post.
    
    Args:
        alert_data: Alert data
    
    Returns:
        Formatted message string
    """
    signals = alert_data.get("signals", [])
    signals_str = "; ".join(signals) if isinstance(signals, list) else str(signals)
    
    return (
        f"[RISK] {alert_data.get('customer', 'unknown')}: "
        f"{alert_data.get('from_level', 'unknown')} → {alert_data.get('to_level', 'unknown')}. "
        f"Signals: {signals_str}. "
        f"Suggest: {alert_data.get('suggestion', '')}"
    )


def extract_draft_id(text: str) -> Optional[str]:
    """
    Extract draft ID from message.
    
    Args:
        text: Message text
    
    Returns:
        Draft ID or None
    """
    match = re.search(r"\[DRAFT\s+(\w+-\d+)\]", text)
    if match:
        return match.group(1)
    return None


def extract_risk_customer(text: str) -> Optional[str]:
    """
    Extract customer from risk message.
    
    Args:
        text: Message text
    
    Returns:
        Customer name or None
    """
    match = re.search(r"\[RISK\]\s+([^:]+):", text)
    if match:
        return match.group(1).strip()
    return None
