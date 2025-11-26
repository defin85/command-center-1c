# orchestrator/conftest.py
"""
Root conftest for pytest - initializes Django before anything else.
"""

import os
import sys
import django

# Setup Django before any imports
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

django.setup()
