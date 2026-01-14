# ADR: Artifacts — Permanent Delete (Purge) + TTL 30 days

**Date:** 2026-01-14
**Status:** Accepted

## Context

В UI `/artifacts` сейчас есть только soft-delete: артефакт скрывается из каталога (`is_deleted=true`), но:
- версии/алиасы остаются в Postgres;
- бинарные объекты остаются в MinIO;
- storage не очищается автоматически и растет бесконечно.

Требование:
- “Окончательно” = удалить **все данные артефакта** (DB + MinIO).
- Разрешено удалять системные артефакты (включая `kind=driver_catalog`).
- Если артефакт используется в активных операциях/воркфлоу — **блокировать** purge и дать понятное уведомление (кто/где использует).
- Нужен auto-purge: через **30 дней** после soft-delete автоматически пытаться выполнить purge (TTL).

Ограничения проекта:
- Frontend обращается только в API Gateway (`/api/v2/*`), изменения API — contract-first (`contracts/**`).
- Celery отсутствует, Go Worker — единственный execution engine.
- 1C ограничения не критичны для purge (это не 1C транзакции), но важны: не делать тяжёлых синхронных API вызовов.

## Decision

### 1) Пользовательская семантика

Вводим 4 действия:
1) **Delete (soft)**: как сейчас — `is_deleted=true`, возможно восстановление.
2) **Restore**: как сейчас — вернуть в активный каталог.
3) **Purge (manual)**: “удалить навсегда” — удаляет MinIO + Postgres, только если `is_deleted=true`.
4) **Auto purge (TTL 30d)**: планируем purge через 30 дней после soft-delete, выполняем в фоне при отсутствии блокеров.

TTL в этом ADR = “срок жизни в deleted”: после `deleted_at + 30d` система сама запускает purge.

### 2) Блокировка “in use” (активные зависимости)

Purge запрещён, если артефакт используется в активных сущностях:
- **Operations**: `BatchOperation.status in {pending, queued, processing, retry}`.
- **Workflows**: `WorkflowExecution.status in {pending, running}`.

Для детерминированных блокировок вводим учёт ссылок на артефакты:
- Базовый формат ссылки в payload/UI: `artifact://artifacts/<artifact_id>/<version>/<filename>` (используется фронтендом через `storage_key`).
- При создании/запуске операций и workflow извлекаем ссылки `artifact://...` и пишем `ArtifactUsage` (или расширенный аналог), чтобы preflight мог быстро находить зависимости.

### 3) Архитектура исполнения purge

Purge выполняется **асинхронно** через Go Worker (без долгих HTTP транзакций).

Вводим сущность `ArtifactPurgeJob`:
- создаётся Orchestrator’ом (manual или TTL);
- имеет статус, прогресс (кол-во объектов/байт), ошибки;
- идемпотентна по `(artifact_id, mode, idempotency_key)`.

Процесс:
1) **Preflight**: Orchestrator строит “план удаления” (сколько версий/алиасов/байт/объектов) + проверяет blockers.
2) **Lock**: помечаем артефакт `purge_state=running` (или `purge_pending=true`) и создаём job.
3) **Execute**: Worker удаляет объекты из MinIO батчами.
4) **Finalize**: Orchestrator удаляет записи в Postgres (Artifact + каскад).
5) **Audit/Metrics**: пишем `AdminActionAuditLog` и метрики (успех/ошибка/байты/длительность).

### 4) MinIO семантика “удалить навсегда”

Удаляем:
- все `ArtifactVersion.storage_key`;
- “страховочно” — всё по prefix `artifacts/<artifact_id>/` (для сирот/старых ключей).

Требование для честного “навсегда”:
- bucket versioning для артефактов должен быть **выключен** (у нас уже есть прикладное версионирование через `ArtifactVersion`).
  - Если versioning включён на бакете, обычный delete может оставить старые версии/delete-markers, и место не освободится.
  - В этом случае purge обязан либо удалять версии по versionId, либо система должна запретить/детектировать неверную конфигурацию.

### 5) TTL 30 дней

При soft-delete:
- сохраняем `deleted_at`;
- рассчитываем `purge_after = deleted_at + 30d`;
- переводим `purge_state` в “scheduled”.

При restore:
- сбрасываем `purge_after/purge_state`.

Auto-purge:
- периодический процесс в Worker (например, раз в сутки/час) выбирает кандидатов `is_deleted=true AND purge_after<=now AND purge_state in {scheduled, failed}`.
- для каждого делает preflight и либо запускает purge job, либо оставляет в “blocked” (с причиной).

## Consequences

**Positive:**
- Storage перестаёт расти бесконечно: есть manual purge и auto-purge по TTL.
- Безопасность: purge блокируется при активном использовании, UI показывает кто блокирует.
- Надёжность: асинхронная модель без timeouts, с ретраями и прогрессом.
- Наблюдаемость: audit + метрики на purge.

**Negative / Costs:**
- Нужны новые модели/миграции, job-исполнение, UI для прогресса и подтверждений.
- Нужен учёт ссылок (ArtifactUsage) — иначе блокировки будут неточными или дорогими (скан JSON).
- Удаление системных артефактов может временно “сломать” функциональность (например, схемы драйверов) до реимпорта.
- Требуется зафиксировать конфигурацию MinIO (versioning OFF) или усложнить удаление версий.

## Alternatives Considered

1) **Синхронный hard-delete в API** — отклонено (долго, ошибки/таймауты, частичные удаления).
2) **Удалять только DB, оставить MinIO** — отклонено (не решает рост storage).
3) **Только MinIO lifecycle rules** — отклонено (нет блокировок “in use”, нет синхронизации с Postgres, сложная поддержка и отладка).
4) **Hard-delete без soft-delete** — отклонено (слишком рискованно для операторского UI).

