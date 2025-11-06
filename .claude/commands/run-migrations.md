---
description: Run database migrations for Django Orchestrator
---

Применить миграции Django для Orchestrator.

## Usage

```bash
cd orchestrator
source venv/Scripts/activate  # Windows GitBash
# или: source venv/bin/activate  # Linux/Mac
python manage.py migrate
```

## Common Operations

**Проверить статус миграций:**
```bash
python manage.py showmigrations
```

**Создать новые миграции:**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Откатить миграции:**
```bash
python manage.py migrate <app_name> <migration_name>
```

**Создать суперпользователя:**
```bash
python manage.py createsuperuser
```

## When to Use

- После `git pull` (новые миграции от других)
- После изменения Django models
- При setup нового окружения
- При ошибках "no such table"

## Common Issues

**Database connection error:**
```bash
# Проверить что PostgreSQL запущен
docker ps | grep postgres

# Проверить .env.local
cat .env.local | grep DB_HOST
# Должно быть: DB_HOST=localhost (НЕ postgres!)
```

**Migration conflicts:**
```bash
# Удалить конфликтующие миграции и пересоздать
rm orchestrator/apps/<app>/migrations/0XXX_*.py
python manage.py makemigrations
```

**"No changes detected":**
```bash
# Проверить dry-run
python manage.py makemigrations --dry-run

# Force recreation
python manage.py makemigrations --noinput
```

Детальный troubleshooting: skill `cc1c-devops`

## Verification

```bash
# Проверить что все миграции applied
python manage.py showmigrations --list | grep "\[X\]"

# Проверить план миграций
python manage.py migrate --plan

# Access admin panel
# http://localhost:8000/admin (если DEBUG=true)
```

## Related

- `/dev-start` - запустить все (автоматически применяет миграции)
- Skill: `cc1c-devops`
