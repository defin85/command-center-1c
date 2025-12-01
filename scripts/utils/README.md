# Utils Scripts

Утилиты общего назначения.

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `rollback-event-driven.sh` | Откат Event-Driven архитектуры к HTTP Sync |
| `generate_encryption_key.py` | Генерация ключа шифрования для Django |

## rollback-event-driven.sh

Автоматический откат Event-Driven Architecture:

```bash
# Предпросмотр изменений
./scripts/utils/rollback-event-driven.sh --dry-run

# Выполнение отката
./scripts/utils/rollback-event-driven.sh

# Без очистки Redis
./scripts/utils/rollback-event-driven.sh --skip-redis-flush
```

## generate_encryption_key.py

Генерация Fernet ключа:

```bash
python scripts/utils/generate_encryption_key.py
```
