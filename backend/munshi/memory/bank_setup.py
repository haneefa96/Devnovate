"""
Munshi - Bank configuration

This module configures Hindsight banks for production/demo and evaluation.
"""

from typing import Dict, Any, List


def get_bank_name(business_slug: str, is_demo: bool = False, run_id: str = None, seed: int = None) -> str:
    """
    Generate bank name based on context.
    
    Production/Demo: munshi-<business-slug>
    Evaluation: eval-<run-id>-C-s<seed>
    
    Args:
        business_slug: Business identifier (lowercase, hyphenated)
        is_demo: Use demo prefix
        run_id: Evaluation run identifier
        seed: Evaluation seed
    
    Returns:
        Bank name string
    """
    if run_id and seed is not None:
        return f"eval-{run_id}-C-s{seed}"
    if is_demo:
        return f"munshi-{business_slug}"
    return f"munshi-{business_slug}"


def get_bank_directives() -> List[str]:
    """
    Get bank directives (global, untagged).
    
    These are the 6 directives from the PDF section 7:
    1. Never threaten legal action or use coercive language
    2. Never recommend contacting outside 09:00-19:00 IST
    3. Never reveal one customer's information to another
    4. Never state invoice validity or payment receipt
    5. Cite evidence behind every recommendation
    6. Mention MSME rules only if business registered
    """
    return [
        "Never threaten legal action or use coercive language. Escalation needs owner approval.",
        "Never recommend contacting a customer outside 09:00-19:00 IST.",
        "Never reveal one customer's information to another.",
        "Never state that an invoice is valid or that a payment was received; those come from the ledger.",
        "Cite the evidence behind every recommendation. If there is none, say so.",
        "Mention MSME payment-term rules only when the owner has marked the business as a registered micro or small enterprise.",
    ]


def get_retain_mission() -> str:
    """
    Get retain mission string.
    
    This mission guides what memories should be retained:
    - Payment run days per customer
    - Who approves and releases payments
    - Required invoice details and documents
    - Reasons invoices were held or disputed
    - Promises to pay and whether they were kept
    - Contact changes
    - Signs of financial stress
    - Ignore greetings and small talk
    """
    return (
        "Extract facts that affect when and how this supplier gets paid: "
        "each customer's payment-run days, who approves and releases payments, "
        "required invoice details and documents, reasons invoices were held or disputed, "
        "promises to pay and whether they were kept, contact changes, and signs of financial stress. "
        "Ignore greetings and small talk."
    )


def get_observations_mission() -> str:
    """
    Get observations mission string.
    
    This mission guides what patterns should be observed:
    - Payment timing patterns
    - Which follow-ups work or fail
    - Document requirements
    - Changes in behaviour
    - When newer evidence contradicts an older pattern
    """
    return (
        "Consolidate durable patterns per customer: "
        "payment timing, which follow-ups work or fail, document requirements, "
        "and changes in behaviour. Note when newer evidence contradicts an older pattern."
    )


def get_reflect_mission(business_name: str) -> str:
    """
    Get reflect mission string.
    
    Args:
        business_name: Name of the business
    
    Returns:
        Mission string for reflection
    """
    return (
        f"You are Munshi, the accounts clerk for {business_name}. "
        "Help the owner get paid on time without harming customer relationships. "
        "Base every recommendation on evidence and say when evidence is thin or stale."
    )


def get_disposition() -> Dict[str, int]:
    """
    Get disposition traits for the Hindsight agent.
    
    Traits:
    - skepticism: 4 (demand evidence before accepting claims)
    - literalism: 3 (interpret literally, no creative leaps)
    - empathy: 3 (understand customer constraints)
    """
    return {
        "skepticism": 4,
        "literalism": 3,
        "empathy": 3,
    }


def get_bank_config(bank_name: str, business_name: str = "Demo Business") -> Dict[str, Any]:
    """
    Get complete bank configuration.
    
    Args:
        bank_name: Bank name for context
        business_name: Business name for reflect mission
    
    Returns:
        Configuration dict with directives, missions, and disposition
    """
    return {
        "directives": get_bank_directives(),
        "retained_mission": get_retain_mission(),
        "observations_mission": get_observations_mission(),
        "reflect_mission": get_reflect_mission(business_name),
        "disposition": get_disposition(),
    }


def validate_bank_name(bank_name: str) -> bool:
    """
    Validate bank name format.
    
    Valid formats:
    - munshi-<business-slug> (production/demo)
    - eval-<run-id>-C-s<seed> (evaluation)
    
    Args:
        bank_name: Bank name to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not bank_name:
        return False
    
    # Production/Demo format
    if bank_name.startswith("munshi-"):
        suffix = bank_name[7:]
        if suffix and all(c.isalnum() or c == '-' for c in suffix):
            return True
    
    # Evaluation format: eval-<run-id>-C-s<seed>
    # run-id may itself contain hyphens, so find the last -C-s<digits> suffix
    if bank_name.startswith("eval-"):
        import re
        if re.search(r"-C-s\d+$", bank_name):
            return True
    
    return False
