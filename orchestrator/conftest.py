# orchestrator/conftest.py
"""
Root conftest for pytest - initializes Django before anything else.
"""

import os
import django

# These are runnable integration scripts, not pytest tests.
collect_ignore = [
    "test_1c_connection.py",
    "test_cluster_endpoints.py",
    "test_cluster_service.py",
    "test_installation_service_client.py",
    "test_patents.py",
]

# Setup Django before any imports
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

django.setup()
