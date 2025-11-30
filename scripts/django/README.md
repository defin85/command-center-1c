# Django Scripts

Django-специфичные скрипты для работы с Orchestrator.

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `create_migrations.sh` | Создание миграций для databases и operations apps |

## Использование

```bash
# Создание миграций
./scripts/django/create_migrations.sh

# Применение миграций (вручную)
cd orchestrator
python manage.py migrate
```
