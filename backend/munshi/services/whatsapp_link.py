"""
Munshi - WhatsApp link generator

This module generates WhatsApp links for message handoff.
"""

from typing import Optional
from urllib.parse import quote
import re


def generate_whatsapp_link(
    phone: str,
    message: str,
) -> str:
    """
    Generate WhatsApp web link for message.
    
    Args:
        phone: Phone number (with country code, no +)
        message: Message text
    
    Returns:
        WhatsApp web link
    """
    phone_digits = re.sub(r"\D", "", phone)
    if not 10 <= len(phone_digits) <= 15:
        raise ValueError("A valid customer phone number is required for WhatsApp handoff")
    encoded_message = quote(message, safe="")
    return f"https://wa.me/{phone_digits}?text={encoded_message}"


def get_whatsapp_link_for_draft(
    phone: Optional[str],
    body: str,
) -> Optional[str]:
    """
    Get WhatsApp link for a draft message.
    
    Args:
        phone: Customer phone number
        body: Message body
    
    Returns:
        WhatsApp link or None
    """
    if not phone:
        return None
    return generate_whatsapp_link(phone, body)
