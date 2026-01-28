# Change: Рефакторинг orchestrator (Python) исходников до целевого размера (700 строк)

## Why
В orchestrator есть очень крупные view/service/test файлы (1000–5000+ строк). Это затрудняет поддержку и повышает риск ошибок при изменениях. Также это плохо для работы LLM/агентов с контекстом.

## What Changes
Рефакторим Python код orchestrator (включая тесты), чтобы:
- разнести крупные модули по ответственности (views по доменам/эндпоинтам, services по операциям, tests по сценариям);
- привести файлы к целевому размеру ~700 строк;
- не менять поведение API.

Крупнейшие файлы (примерный срез):
- `orchestrator/apps/api_v2/views/rbac.py` (~5275)
- `orchestrator/apps/api_v2/views/operations.py` (~3993)
- `orchestrator/apps/api_v2/views/driver_catalogs.py` (~2733)
- `orchestrator/apps/api_v2/views/workflows.py` (~2337)
- `orchestrator/apps/api_v2/views/databases.py` (~2314)
- `orchestrator/apps/api_v2/views/ui.py` (~2028)

## Non-Goals
- Не меняем API контракты и бизнес-логику.
- Не трогаем архивные тесты и миграции (см. правило исключений).
- Не делаем жёсткий CI gate на размер файлов.

## Impact
- Перестройка структуры модулей `orchestrator/apps/api_v2/views/**` и части сервисов/тестов.
- Правки импортов и `urls.py`/роутинга.

