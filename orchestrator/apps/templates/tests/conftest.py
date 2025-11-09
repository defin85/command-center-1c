"""
Pytest configuration for template engine tests.

These tests do NOT require database access.
"""

import os
import sys
from pathlib import Path

# Настроим окружение Django перед импортом
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('DJANGO_ENV', 'development')

# Минимальные env переменные для Django
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('ALLOWED_HOSTS', 'localhost,127.0.0.1')
os.environ.setdefault('DB_NAME', 'test_db')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('REDIS_HOST', 'localhost')
os.environ.setdefault('REDIS_PORT', '6379')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('DB_ENCRYPTION_KEY', '2KyoQKVSb56ajWuIVq3n11VXLd6YjZ099oABHDXV4V4=')
os.environ.setdefault('FIELD_ENCRYPTION_KEY', '2KyoQKVSb56ajWuIVq3n11VXLd6YjZ099oABHDXV4V4=')

# Импортируем Django после настройки окружения
import django
django.setup()
