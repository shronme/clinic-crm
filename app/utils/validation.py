from typing import Dict, Any, List
import re
from pydantic import ValidationError

def validate_hex_color(color: str) -> bool:
    """Validate hex color format (#RRGGBB or #RGB)."""
    if not color:
        return True  # Allow empty/null
    
    hex_pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    return bool(re.match(hex_pattern, color))

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format (international or local)."""
    if not phone:
        return True  # Allow empty/null
    
    # Basic phone validation - accepts various formats
    phone_pattern = r'^[\+]?[1-9][\d\-\s\(\)\.]{7,15}$'
    return bool(re.match(phone_pattern, phone.replace(' ', '')))

def validate_email_format(email: str) -> bool:
    """Validate email format."""
    if not email:
        return True  # Allow empty/null
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

def validate_url_format(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return True  # Allow empty/null
    
    url_pattern = r'^https?:\/\/(?:[-\w.])+(?:\:[0-9]+)?(?:\/(?:[\w\/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
    return bool(re.match(url_pattern, url))

def validate_business_branding(branding: Dict[str, Any]) -> List[str]:
    """Validate business branding configuration."""
    errors = []
    
    if not branding:
        return errors
    
    # Validate colors
    if 'primary_color' in branding and not validate_hex_color(branding['primary_color']):
        errors.append("primary_color must be a valid hex color (#RRGGBB or #RGB)")
    
    if 'secondary_color' in branding and not validate_hex_color(branding['secondary_color']):
        errors.append("secondary_color must be a valid hex color (#RRGGBB or #RGB)")
    
    # Validate logo position
    valid_positions = ['left', 'center', 'right']
    if 'logo_position' in branding and branding['logo_position'] not in valid_positions:
        errors.append(f"logo_position must be one of: {', '.join(valid_positions)}")
    
    return errors

def validate_business_policy(policy: Dict[str, Any]) -> List[str]:
    """Validate business policy configuration."""
    errors = []
    
    if not policy:
        return errors
    
    # Validate time constraints
    if 'min_lead_time_hours' in policy:
        if not isinstance(policy['min_lead_time_hours'], int) or policy['min_lead_time_hours'] < 0:
            errors.append("min_lead_time_hours must be a non-negative integer")
    
    if 'max_lead_time_days' in policy:
        if not isinstance(policy['max_lead_time_days'], int) or policy['max_lead_time_days'] < 1:
            errors.append("max_lead_time_days must be a positive integer")
    
    if 'cancellation_window_hours' in policy:
        if not isinstance(policy['cancellation_window_hours'], int) or policy['cancellation_window_hours'] < 0:
            errors.append("cancellation_window_hours must be a non-negative integer")
    
    # Validate fees
    if 'no_show_fee' in policy and policy['no_show_fee'] is not None:
        if not isinstance(policy['no_show_fee'], (int, float)) or policy['no_show_fee'] < 0:
            errors.append("no_show_fee must be a non-negative number")
    
    # Validate grace period
    if 'late_arrival_grace_minutes' in policy:
        if not isinstance(policy['late_arrival_grace_minutes'], int) or policy['late_arrival_grace_minutes'] < 0:
            errors.append("late_arrival_grace_minutes must be a non-negative integer")
    
    return errors

def validate_business_data(business_data: Dict[str, Any]) -> List[str]:
    """Comprehensive business data validation."""
    errors = []
    
    # Validate basic contact information
    if 'phone' in business_data and not validate_phone_number(business_data['phone']):
        errors.append("Invalid phone number format")
    
    if 'email' in business_data and not validate_email_format(business_data['email']):
        errors.append("Invalid email format")
    
    if 'website' in business_data and not validate_url_format(business_data['website']):
        errors.append("Invalid website URL format")
    
    if 'logo_url' in business_data and not validate_url_format(business_data['logo_url']):
        errors.append("Invalid logo URL format")
    
    # Validate branding
    if 'branding' in business_data:
        branding_errors = validate_business_branding(business_data['branding'])
        errors.extend(branding_errors)
    
    # Validate policy
    if 'policy' in business_data:
        policy_errors = validate_business_policy(business_data['policy'])
        errors.extend(policy_errors)
    
    return errors

class BusinessValidationError(Exception):
    """Custom exception for business validation errors."""
    
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Business validation failed: {'; '.join(errors)}")

def validate_and_raise(business_data: Dict[str, Any]) -> None:
    """Validate business data and raise exception if errors found."""
    errors = validate_business_data(business_data)
    if errors:
        raise BusinessValidationError(errors)