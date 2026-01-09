# Roadmap: Переход на Django 6.0 и async-first

> **Статус:** DRAFT
> **Версия:** 1.0
> **Создан:** 2025-12-30
> **Обновлён:** 2025-12-30
> **Автор:** Codex

---

## Цель

Перейти на Django 6.0 (Python 3.13) и убрать смешивание sync/async в API,
особенно для SSE/long-lived запросов. Итог — устойчивые асинхронные стримы
и понятные границы синхронного кода.

## Контекст и ограничения

- Продакшена нет, только dev (можно менять Python и зависимости).
- Orchestrator уже работает через ASGI (Daphne).
- Есть проблемы со смешиванием sync/async и SSE.
- 1C операции критичны по времени (транзакции < 15 сек).

## Область работ

**Включено:**
- `orchestrator/` (Django, DRF, Channels, SSE, Redis).
- Зависимости Python и их совместимость с Django 6.0.

**Исключено:**
- Go-сервисы и фронтенд (кроме контрактов/генерации при необходимости).

---

## Фаза 0: Аудит и подготовка (1-2 дня)

**Цель:** зафиксировать текущее состояние и точки смешивания sync/async.

**Subtasks:**
- [x] Инвентаризация async-to-sync точек:
  - `orchestrator/apps/api_v2/views/databases.py`
  - `orchestrator/apps/api_v2/views/operations.py`
  - `orchestrator/apps/api_v2/views/system.py`
  - `orchestrator/apps/monitoring/services.py`
  - `orchestrator/apps/operations/consumers.py`
  - `orchestrator/apps/operations/signals.py`
- [x] Инвентаризация sync-only библиотек (DB/ORM, cache, сторонние клиенты).
- [x] Карта SSE и WebSocket потоков (endpoints + точка входа).

**Артефакты:**
- Список sync/async boundary.
- Список библиотек и их совместимость с Django 6.0.
- Отчёт Phase 0: `docs/roadmaps/ROADMAP_DJANGO_6_ASYNC_PHASE0.md`

---

## Фаза 1: Python 3.12 + зависимости (1-2 дня)

**Цель:** поднять базу под Django 6.0.

**Subtasks:**
- [x] Обновить Python до 3.13 в dev.
- [x] Пересоздать `orchestrator/venv`.
- [x] Обновить зависимости в `orchestrator/requirements.txt`:
  - Django 6.0
  - DRF, drf-spectacular, django-filter
  - channels, daphne, redis, aiohttp и др.
- [x] Проверить совместимость пакетами и исправить конфликты.

**Артефакты:**
- Обновлённый `requirements.txt`.
- Чистый запуск Django + миграции без ошибок.

---

## Фаза 2: Django 6.0 миграция (2-4 дня)

**Цель:** привести код под Django 6.0 и убрать деприкейты.

**Subtasks:**
- [ ] Прогнать `python -Wd` и очистить деприкейты.
- [ ] Обновить настройки/импорты, если изменились контракты.
- [ ] Проверить `DEFAULT_AUTO_FIELD`, middleware, ASGI настройки.
- [ ] Убедиться, что OpenAPI генерация и proxy routes работают.

**Артефакты:**
- Проект собирается и запускается на Django 6.0.
- Нет warnings уровня DeprecationWarning.

---

## Фаза 3: Async-first API (3-6 дней)

**Цель:** убрать sync/async мешанину и сделать SSE стабильным.

**Принципы:**
- SSE/long-lived запросы — только async.
- Sync-only операции (ORM) — строго через `database_sync_to_async`/`sync_to_async`,
  либо вынос в отдельный сервис/операцию.
- DRF остаётся sync для обычных CRUD, async только там, где реально нужен.

**Subtasks:**
- [x] Перевести SSE endpoints на чистый async без `async_to_sync`.
- [x] Выделить единый async слой для Redis/stream I/O (через `redis.asyncio`).
- [x] Устранить async_to_sync в `system.py` (если используется).
- [x] Проверить, что каждый async view не делает sync ORM напрямую.
- [x] Настроить корректные таймауты и отмену (cancel) для SSE.

**Артефакты:**
- Стабильные SSE без fallback/502.
- Понятные границы sync/async в коде.

---

## Фаза 4: Тесты и проверка (2-3 дня)

**Цель:** убедиться, что апгрейд не ломает бизнес-логику.

**Subtasks:**
- [ ] Полный прогон unit/интеграционных тестов.
- [ ] Нагрузочные проверки SSE (много одновременных клиентов).
- [ ] Проверка основных пользовательских сценариев (DB/cluster/ops).

**Артефакты:**
- Зеленые тесты.
- Подтверждённая стабильность SSE.

---

## Фаза 5: Документация и стабилизация (1 день)

**Subtasks:**
- [ ] Обновить документацию по dev-окружению (Python 3.13).
- [ ] Зафиксировать async-гайдлайны для новых endpoints.
- [ ] Обновить quick-start/README (если нужно).

---

## Definition of Done

- Django 6.0 + Python 3.13 в dev.
- SSE работает стабильно без sync wrappers и без 5xx.
- Нет критичных deprecation warnings.
- Тесты проходят (или есть явный список допустимых исключений).
