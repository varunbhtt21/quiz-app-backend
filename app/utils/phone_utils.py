"""
📱 Phone Number Utilities
Standardized mobile number handling for Indian phone numbers

Features:
- Normalizes various mobile number formats to 10-digit format
- Validates Indian mobile number patterns
- Handles +91, 91, and plain 10-digit formats
- Architecture-consistent error handling
"""

import re
from typing import Tuple


class MobileValidationError(ValueError):
    """Custom exception for mobile number validation errors."""
    pass


def normalize_indian_mobile(mobile_input: str) -> str:
    """
    Normalize Indian mobile number to 10-digit format.
    
    Handles various input formats:
    - 7906986914 → 7906986914
    - 917906986914 → 7906986914
    - +917906986914 → 7906986914
    - +91 7906986914 → 7906986914 (with spaces)
    - 91-7906986914 → 7906986914 (with dashes)
    
    Args:
        mobile_input (str): Raw mobile number input
        
    Returns:
        str: Normalized 10-digit mobile number
        
    Raises:
        MobileValidationError: If mobile number cannot be normalized or is invalid
    """
    if not mobile_input or not isinstance(mobile_input, str):
        raise MobileValidationError("Mobile number cannot be empty")
    
    # Remove all non-digit characters
    digits_only = re.sub(r'[^0-9]', '', mobile_input.strip())
    
    if not digits_only:
        raise MobileValidationError(f"No digits found in mobile number '{mobile_input}'")
    
    # Handle different formats
    if len(digits_only) == 10:
        # Already 10 digits - validate and return
        normalized = digits_only
    elif len(digits_only) == 11 and digits_only.startswith('91'):
        # Remove '91' prefix
        normalized = digits_only[2:]
    elif len(digits_only) == 12 and digits_only.startswith('91'):
        # Remove '91' prefix
        normalized = digits_only[2:]
    elif len(digits_only) > 12 and digits_only.startswith('91'):
        # Remove '91' prefix from longer numbers
        normalized = digits_only[2:]
    else:
        raise MobileValidationError(
            f"Invalid mobile number format '{mobile_input}' - "
            f"expected 10 digits or 11/12 digits with 91 prefix"
        )
    
    # Final validation
    if len(normalized) != 10:
        raise MobileValidationError(
            f"Normalized mobile number '{normalized}' is not 10 digits "
            f"(original: '{mobile_input}')"
        )
    
    # Validate Indian mobile number pattern
    if not _is_valid_indian_mobile(normalized):
        raise MobileValidationError(
            f"Invalid Indian mobile number '{normalized}' - "
            f"must start with 6, 7, 8, or 9"
        )
    
    return normalized


def _is_valid_indian_mobile(mobile: str) -> bool:
    """
    Validate if 10-digit number follows Indian mobile number patterns.
    
    Indian mobile numbers:
    - Must be 10 digits
    - Must start with 6, 7, 8, or 9
    - Cannot start with 0 or 1
    
    Args:
        mobile (str): 10-digit mobile number
        
    Returns:
        bool: True if valid Indian mobile number
    """
    if len(mobile) != 10:
        return False
    
    if not mobile.isdigit():
        return False
    
    # Indian mobile numbers start with 6, 7, 8, or 9
    valid_prefixes = ['6', '7', '8', '9']
    return mobile[0] in valid_prefixes


def validate_and_normalize_mobile(mobile_input: str, row_context: str = "") -> Tuple[str, str]:
    """
    Validate and normalize mobile number with detailed error context.
    
    Args:
        mobile_input (str): Raw mobile number input
        row_context (str): Context for error reporting (e.g., "Row 5")
        
    Returns:
        Tuple[str, str]: (normalized_mobile, success_message)
        
    Raises:
        MobileValidationError: With detailed error message including context
    """
    try:
        normalized = normalize_indian_mobile(mobile_input)
        context_prefix = f"{row_context}: " if row_context else ""
        return normalized, f"{context_prefix}Mobile '{mobile_input}' normalized to '{normalized}'"
    
    except MobileValidationError as e:
        context_prefix = f"{row_context}: " if row_context else ""
        raise MobileValidationError(f"{context_prefix}{str(e)}")


def format_mobile_for_display(mobile: str, include_country_code: bool = False) -> str:
    """
    Format mobile number for display purposes.
    
    Args:
        mobile (str): 10-digit mobile number
        include_country_code (bool): Whether to include +91 prefix
        
    Returns:
        str: Formatted mobile number
    """
    if not mobile or len(mobile) != 10:
        return mobile
    
    # Format as XXX-XXX-XXXX
    formatted = f"{mobile[:3]}-{mobile[3:6]}-{mobile[6:]}"
    
    if include_country_code:
        return f"+91 {formatted}"
    
    return formatted


# Example usage and test cases (for development reference)
if __name__ == "__main__":
    test_cases = [
        "7906986914",           # Plain 10 digits
        "917906986914",         # With 91 prefix
        "+917906986914",        # With +91 prefix
        "+91 7906986914",       # With spaces
        "91-7906986914",        # With dashes
        "+91-790-698-6914",     # Complex formatting
        "079069869142",         # Invalid (starts with 0)
        "1234567890",           # Invalid (starts with 1)
        "79069869",             # Too short
        "79069869145",          # Too long without prefix
    ]
    
    print("🧪 Testing Mobile Number Normalization:")
    print("=" * 50)
    
    for test_input in test_cases:
        try:
            result = normalize_indian_mobile(test_input)
            print(f"✅ '{test_input}' → '{result}'")
        except MobileValidationError as e:
            print(f"❌ '{test_input}' → ERROR: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Phone utilities module ready!") 