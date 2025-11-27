#!/usr/bin/env python
"""Создание суперпользователя для Django Admin."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'admin'
email = 'admin@example.com'
password = 'admin123'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print("✅ Суперпользователь создан!")
    print(f"   Логин: {username}")
    print(f"   Пароль: {password}")
else:
    print(f"ℹ️  Суперпользователь '{username}' уже существует")
    print(f"   Логин: {username}")
    print(f"   Пароль: {password}")
