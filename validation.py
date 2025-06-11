"""
Input validation utilities for the Elk River Guns Inventory Tracker

This module provides comprehensive validation for user inputs, firearm data,
and external data sources to prevent security issues and data corruption.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    cleaned_value: Any = None
    error_message: str = ""


class InputValidator:
    """Comprehensive input validation for firearm data and user inputs"""
    
    # Firearm validation patterns
    MANUFACTURER_PATTERN = re.compile(r'^[A-Za-z0-9\s&\-\.]{1,50}$')
    MODEL_PATTERN = re.compile(r'^[A-Za-z0-9\s\-\./]{1,50}$')
    CALIBER_PATTERN = re.compile(r'^[A-Za-z0-9\s\-\.×X/]{1,30}$')
    SECTION_PATTERN = re.compile(r'^[A-Za-z0-9\s]{1,50}$')
    
    # Price validation ranges
    MIN_PRICE = 10.0
    MAX_PRICE = 50000.0
    
    # String length limits
    MAX_DESCRIPTION_LENGTH = 500
    MAX_URL_LENGTH = 2048
    
    # Allowed URL schemes and domains
    ALLOWED_URL_SCHEMES = ['http', 'https']
    ALLOWED_DOMAINS = [
        'elkriverguns.com',
        'www.elkriverguns.com',
        'armslist.com',
        'www.armslist.com'
    ]
    
    @classmethod
    def validate_manufacturer(cls, manufacturer: str) -> ValidationResult:
        """Validate firearm manufacturer name"""
        if not manufacturer:
            return ValidationResult(False, None, "Manufacturer is required")
        
        if not isinstance(manufacturer, str):
            return ValidationResult(False, None, "Manufacturer must be a string")
        
        # Clean and normalize
        cleaned = manufacturer.strip().upper()
        
        if not cleaned:
            return ValidationResult(False, None, "Manufacturer cannot be empty")
        
        if len(cleaned) > 50:
            return ValidationResult(False, None, "Manufacturer name too long (max 50 characters)")
        
        if not cls.MANUFACTURER_PATTERN.match(cleaned):
            return ValidationResult(False, None, "Manufacturer contains invalid characters")
        
        # Check for known problematic patterns
        sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', '--', ';']
        for pattern in sql_patterns:
            if pattern in cleaned:
                return ValidationResult(False, None, "Manufacturer contains invalid content")
        
        return ValidationResult(True, cleaned, "")
    
    @classmethod
    def validate_model(cls, model: str) -> ValidationResult:
        """Validate firearm model name"""
        if not model:
            return ValidationResult(False, None, "Model is required")
        
        if not isinstance(model, str):
            return ValidationResult(False, None, "Model must be a string")
        
        # Clean and normalize
        cleaned = model.strip().upper()
        
        if not cleaned:
            return ValidationResult(False, None, "Model cannot be empty")
        
        if len(cleaned) > 50:
            return ValidationResult(False, None, "Model name too long (max 50 characters)")
        
        if not cls.MODEL_PATTERN.match(cleaned):
            return ValidationResult(False, None, "Model contains invalid characters")
        
        # Check for known problematic patterns
        sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', '--', ';']
        for pattern in sql_patterns:
            if pattern in cleaned:
                return ValidationResult(False, None, "Model contains invalid content")
        
        return ValidationResult(True, cleaned, "")
    
    @classmethod
    def validate_caliber(cls, caliber: str) -> ValidationResult:
        """Validate firearm caliber"""
        if not caliber:
            return ValidationResult(False, None, "Caliber is required")
        
        if not isinstance(caliber, str):
            return ValidationResult(False, None, "Caliber must be a string")
        
        # Clean and normalize
        cleaned = caliber.strip().upper()
        
        if not cleaned:
            return ValidationResult(False, None, "Caliber cannot be empty")
        
        if len(cleaned) > 30:
            return ValidationResult(False, None, "Caliber name too long (max 30 characters)")
        
        if not cls.CALIBER_PATTERN.match(cleaned):
            return ValidationResult(False, None, "Caliber contains invalid characters")
        
        # Check for known problematic patterns
        sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', '--', ';']
        for pattern in sql_patterns:
            if pattern in cleaned:
                return ValidationResult(False, None, "Caliber contains invalid content")
        
        return ValidationResult(True, cleaned, "")
    
    @classmethod
    def validate_price(cls, price: Union[str, int, float]) -> ValidationResult:
        """Validate firearm price"""
        if price is None:
            return ValidationResult(False, None, "Price is required")
        
        # Convert string to float if needed
        if isinstance(price, str):
            try:
                # Remove currency symbols and commas
                cleaned_str = re.sub(r'[,$]', '', price.strip())
                price = float(cleaned_str)
            except (ValueError, TypeError):
                return ValidationResult(False, None, "Price must be a valid number")
        
        if not isinstance(price, (int, float)):
            return ValidationResult(False, None, "Price must be a number")
        
        if price < cls.MIN_PRICE:
            return ValidationResult(False, None, f"Price too low (minimum ${cls.MIN_PRICE})")
        
        if price > cls.MAX_PRICE:
            return ValidationResult(False, None, f"Price too high (maximum ${cls.MAX_PRICE})")
        
        # Round to 2 decimal places
        cleaned_price = round(float(price), 2)
        
        return ValidationResult(True, cleaned_price, "")
    
    @classmethod
    def validate_description(cls, description: str) -> ValidationResult:
        """Validate firearm description"""
        if description is None:
            description = ""
        
        if not isinstance(description, str):
            return ValidationResult(False, None, "Description must be a string")
        
        # Clean description
        cleaned = description.strip()
        
        if len(cleaned) > cls.MAX_DESCRIPTION_LENGTH:
            return ValidationResult(False, None, f"Description too long (max {cls.MAX_DESCRIPTION_LENGTH} characters)")
        
        # Check for potential XSS patterns
        xss_patterns = ['<script', '<iframe', '<object', '<embed', 'javascript:', 'onload=', 'onerror=']
        for pattern in xss_patterns:
            if pattern.lower() in cleaned.lower():
                return ValidationResult(False, None, "Description contains invalid content")
        
        # Check for SQL injection patterns
        sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', '--', ';']
        for pattern in sql_patterns:
            if pattern in cleaned.upper():
                return ValidationResult(False, None, "Description contains invalid content")
        
        return ValidationResult(True, cleaned, "")
    
    @classmethod
    def validate_condition(cls, condition: str) -> ValidationResult:
        """Validate firearm condition"""
        if not condition:
            return ValidationResult(False, None, "Condition is required")
        
        if not isinstance(condition, str):
            return ValidationResult(False, None, "Condition must be a string")
        
        cleaned = condition.strip().lower()
        
        valid_conditions = ['new', 'used']
        if cleaned not in valid_conditions:
            return ValidationResult(False, None, f"Condition must be one of: {', '.join(valid_conditions)}")
        
        return ValidationResult(True, cleaned, "")
    
    @classmethod
    def validate_section(cls, section: str) -> ValidationResult:
        """Validate firearm section/category"""
        if not section:
            return ValidationResult(False, None, "Section is required")
        
        if not isinstance(section, str):
            return ValidationResult(False, None, "Section must be a string")
        
        cleaned = section.strip()
        
        if len(cleaned) > 50:
            return ValidationResult(False, None, "Section name too long (max 50 characters)")
        
        if not cls.SECTION_PATTERN.match(cleaned):
            return ValidationResult(False, None, "Section contains invalid characters")
        
        return ValidationResult(True, cleaned, "")
    
    @classmethod
    def validate_url(cls, url: str) -> ValidationResult:
        """Validate URL for scraping"""
        if not url:
            return ValidationResult(False, None, "URL is required")
        
        if not isinstance(url, str):
            return ValidationResult(False, None, "URL must be a string")
        
        if len(url) > cls.MAX_URL_LENGTH:
            return ValidationResult(False, None, f"URL too long (max {cls.MAX_URL_LENGTH} characters)")
        
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return ValidationResult(False, None, "Invalid URL format")
        
        if parsed.scheme not in cls.ALLOWED_URL_SCHEMES:
            return ValidationResult(False, None, f"URL scheme must be one of: {', '.join(cls.ALLOWED_URL_SCHEMES)}")
        
        if parsed.netloc.lower() not in cls.ALLOWED_DOMAINS:
            return ValidationResult(False, None, f"URL domain must be one of: {', '.join(cls.ALLOWED_DOMAINS)}")
        
        return ValidationResult(True, url, "")
    
    @classmethod
    def validate_firearm_listing(cls, listing_data: Dict[str, Any]) -> ValidationResult:
        """Validate complete firearm listing data"""
        errors = []
        cleaned_data = {}
        
        # Validate manufacturer
        manufacturer_result = cls.validate_manufacturer(listing_data.get('manufacturer', ''))
        if not manufacturer_result.is_valid:
            errors.append(f"Manufacturer: {manufacturer_result.error_message}")
        else:
            cleaned_data['manufacturer'] = manufacturer_result.cleaned_value
        
        # Validate model
        model_result = cls.validate_model(listing_data.get('model', ''))
        if not model_result.is_valid:
            errors.append(f"Model: {model_result.error_message}")
        else:
            cleaned_data['model'] = model_result.cleaned_value
        
        # Validate caliber
        caliber_result = cls.validate_caliber(listing_data.get('caliber', ''))
        if not caliber_result.is_valid:
            errors.append(f"Caliber: {caliber_result.error_message}")
        else:
            cleaned_data['caliber'] = caliber_result.cleaned_value
        
        # Validate price
        price_result = cls.validate_price(listing_data.get('price'))
        if not price_result.is_valid:
            errors.append(f"Price: {price_result.error_message}")
        else:
            cleaned_data['price'] = price_result.cleaned_value
        
        # Validate condition
        condition_result = cls.validate_condition(listing_data.get('condition', 'used'))
        if not condition_result.is_valid:
            errors.append(f"Condition: {condition_result.error_message}")
        else:
            cleaned_data['condition'] = condition_result.cleaned_value
        
        # Validate section
        section_result = cls.validate_section(listing_data.get('section', ''))
        if not section_result.is_valid:
            errors.append(f"Section: {section_result.error_message}")
        else:
            cleaned_data['section'] = section_result.cleaned_value
        
        # Validate description (optional)
        description_result = cls.validate_description(listing_data.get('description', ''))
        if not description_result.is_valid:
            errors.append(f"Description: {description_result.error_message}")
        else:
            cleaned_data['description'] = description_result.cleaned_value
        
        if errors:
            return ValidationResult(False, None, "; ".join(errors))
        
        return ValidationResult(True, cleaned_data, "")
    
    @classmethod
    def sanitize_for_display(cls, text: str) -> str:
        """Sanitize text for safe display in web UI"""
        if not isinstance(text, str):
            return str(text)
        
        # Basic HTML entity encoding for safety
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        
        return text.strip()


def validate_search_params(manufacturer: str, model: str, caliber: str) -> ValidationResult:
    """Validate parameters for marketplace search"""
    validator = InputValidator()
    
    # Validate each parameter
    manufacturer_result = validator.validate_manufacturer(manufacturer)
    if not manufacturer_result.is_valid:
        return ValidationResult(False, None, f"Manufacturer: {manufacturer_result.error_message}")
    
    model_result = validator.validate_model(model)
    if not model_result.is_valid:
        return ValidationResult(False, None, f"Model: {model_result.error_message}")
    
    caliber_result = validator.validate_caliber(caliber)
    if not caliber_result.is_valid:
        return ValidationResult(False, None, f"Caliber: {caliber_result.error_message}")
    
    cleaned_params = {
        'manufacturer': manufacturer_result.cleaned_value,
        'model': model_result.cleaned_value,
        'caliber': caliber_result.cleaned_value
    }
    
    return ValidationResult(True, cleaned_params, "")


def validate_scraping_url(url: str) -> ValidationResult:
    """Validate URL for web scraping"""
    return InputValidator.validate_url(url)