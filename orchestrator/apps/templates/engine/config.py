"""Engine configuration."""

from typing import List


# Template engine configuration
ENGINE_CONFIG = {
    # Cache settings
    'CACHE_TIMEOUT': 3600,  # 1 hour
    'CACHE_PREFIX': 'cc1c:template:',

    # Security settings
    'MAX_TEMPLATE_SIZE': 1024 * 1024,  # 1 MB
    'MAX_CONTEXT_SIZE': 1024 * 1024,   # 1 MB

    # Rendering settings
    'TRIM_BLOCKS': True,
    'LSTRIP_BLOCKS': True,
    'AUTOESCAPE': False,  # We're rendering JSON, not HTML
}

# Dangerous patterns for validator
DANGEROUS_PATTERNS: List[str] = [
    r'__.*__',        # Python magic methods
    r'_.*',           # Private attributes
    r'import\s+',     # Import statements
    r'exec\s*\(',     # Exec function
    r'eval\s*\(',     # Eval function
    r'open\s*\(',     # File operations
    r'compile\s*\(',  # Code compilation
]
