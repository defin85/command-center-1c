# TODO: Artifacts — Permanent Delete (Purge) + TTL 30 days

См. архитектурное решение: `docs/roadmaps/ADR_ARTIFACTS_PURGE_TTL_30D.md`.

Контекст:
- Сейчас `DELETE /api/v2/artifacts/{id}/` делает только soft-delete (`is_deleted=true`).
- В UI прямо указано: “Versions and aliases remain stored.”
- Требуется “удалить навсегда” (DB + MinIO), авто‑пурж через 30 дней, и блокировка при активном использовании.

Ограничения/принципы:
- **Contract-first**: сначала `contracts/orchestrator/openapi.yaml`, затем генерация клиентов.
- Frontend ходит только через API Gateway (`/api/v2/*`).
- Celery отсутствует, **Go Worker — единственный execution engine**.
- Purge должен быть **асинхронным** (job), без долгих HTTP транзакций.
- **Blocking**: если артефакт используется в активных operations/workflows — запретить purge и показать причину.

Затронутые места (ориентировочно):
- Contracts:
  - `contracts/orchestrator/openapi.yaml` (+ regeneration)
- Backend (Orchestrator):
  - `orchestrator/apps/api_v2/views/artifacts.py`
  - `orchestrator/apps/api_v2/urls.py`
  - `orchestrator/apps/artifacts/models.py` (+ migrations)
  - `orchestrator/apps/artifacts/storage.py` (delete by prefix/batch)
  - `orchestrator/apps/operations/models/admin_action_audit_log.py` (аудит)
  - `orchestrator/apps/templates/workflow/models.py` (blockers по status)
- Frontend:
  - `frontend/src/pages/Artifacts/ArtifactsPage.tsx`
  - `frontend/src/api/generated/v2/v2.ts` (после генерации)
- Go Worker:
  - purge runner + TTL scheduler (точные пути зависят от структуры `go-services/worker`)

---

## P0 — Manual purge (MVP) + блокировки

### Контракты (OpenAPI contract-first)

- [x] Обновить `contracts/orchestrator/openapi.yaml`:
  - [x] `POST /api/v2/artifacts/{artifact_id}/purge/`
    - body: `reason`, `dry_run` (default `false`)
    - response (dry-run): `plan + blockers`
    - response (start): `job_id`
  - [x] `GET /api/v2/artifacts/purge-jobs/{job_id}/` (status/progress/error)
  - [x] Добавить error codes:
    - [x] `ARTIFACT_IN_USE` (409)
    - [x] `PURGE_NOT_ALLOWED` (400/403) — например, если `is_deleted=false`
    - [x] `PURGE_ALREADY_RUNNING` (409)
  - [x] Расширить модель `Artifact` в ответах:
    - [x] `is_deleted`, `deleted_at`
    - [x] `purge_state`, `purge_after` (для TTL и UI)

- [x] `./contracts/scripts/validate-specs.sh`
- [x] `./contracts/scripts/generate-all.sh`

### Backend: модели/миграции

- [x] Добавить поля в `Artifact`:
  - [x] `purge_state` (`none|scheduled|running|failed`)
  - [x] `purge_after` (datetime, nullable)
  - [ ] (опц.) `purge_last_error` (text) для UI/диагностики
- [x] Создать модель `ArtifactPurgeJob`:
  - [x] `artifact_id`, `mode` (`manual|ttl`), `status`, прогресс, ошибки
  - [x] `requested_by`, `reason`, timestamps
  - [x] идемпотентность/уникальность на активный job для артефакта
- [x] Миграции + индексы:
  - [x] `(is_deleted, purge_after)`
  - [x] `(purge_state, purge_after)`

### Backend: preflight plan + blockers

- [x] Реализовать “план удаления”:
  - [x] количество версий/алиасов/байт/MinIO objects
  - [x] список ключей (лимит ключей в ответе, без пагинации)
- [x] Реализовать blockers:
  - [x] по операциям `BatchOperation` (активные статусы)
  - [x] по workflow `WorkflowExecution` (активные статусы)
- [x] Ввести/расширить учёт ссылок на артефакты:
  - [x] извлечение `artifact://artifacts/<uuid>/...` из payload/контекста
  - [x] запись `ArtifactUsage` при создании/запуске операции и workflow
  - [x] (fallback) скан активных `BatchOperation.payload/config` и `WorkflowExecution.input_context` по строке `artifact://artifacts/<uuid>/`

### Backend: purge endpoints

- [x] `POST /api/v2/artifacts/{artifact_id}/purge/`:
  - [x] проверка прав (отдельное permission `artifacts.purge_artifact` + `manage_artifact`)
  - [x] `dry_run=true` → вернуть plan+blockers
  - [x] `dry_run=false`:
    - [x] запрет, если `is_deleted=false`
    - [x] запрет, если есть blockers
    - [x] lock артефакта (`purge_state=running`) + создать job
    - [x] enqueue задачи в Worker (создание job, worker подхватывает через internal claim)
    - [x] вернуть `job_id`
- [x] `GET /api/v2/artifacts/purge-jobs/{job_id}/`:
  - [x] статус + прогресс + сообщение об ошибке

### Worker: purge runner

- [x] Получить job → список `ArtifactVersion.storage_key`.
- [x] Удалять объекты батчами (bulk delete).
- [x] “страховка”: удалить по prefix `artifacts/<artifact_id>/`.
- [x] Прогресс: обновлять job (deleted_objects/bytes).
- [x] Finalize: Orchestrator internal complete endpoint (удаление DB + финальный статус job).

### UI: permanent delete flow

- [x] Вкладка “Deleted”:
  - [x] кнопка “Delete permanently”
  - [x] показ `purge_after` (“Auto purge in N days”)
- [x] Модалка подтверждения:
  - [x] preflight (`dry_run`) → summary + blockers
  - [x] поле `reason` (обязательное)
  - [x] подтверждение вводом имени артефакта
- [x] Прогресс:
  - [x] polling `purge-jobs/{job_id}`
  - [x] показать error/успех, обновить список

### Тесты / DoD

- [x] Unit tests на extractor ссылок `artifact://...`.
- [x] API tests:
  - [x] purge запрещён если `is_deleted=false`
  - [x] purge запрещён при blockers
  - [x] purge создаёт job и уходит в worker (mock)
- [ ] E2E (минимум):
  - [ ] UI: deleted tab → purge → прогресс → исчезновение из списка

---

## P1 — TTL auto-purge (30 days)

- [x] При soft-delete выставлять `purge_after = deleted_at + 30d`, `purge_state=scheduled`.
- [x] При restore сбрасывать `purge_after/purge_state`.
- [x] Worker scheduler:
  - [x] периодический скан кандидатов (через internal claim endpoint по cron)
  - [x] запуск purge jobs с `mode=ttl`, `reason=ttl_auto_purge`
  - [x] ограничение параллелизма (чтобы не перегрузить MinIO)
- [x] retry/backoff при ошибках
- [x] UI:
  - [x] “Auto purge blocked” с причинами (активные операции/workflows)

---

## P2 — Hardening / Ops

- [x] Метрики:
  - [x] jobs created/succeeded/failed
  - [x] bytes deleted, objects deleted, duration
- [x] Audit:
  - [x] `AdminActionAuditLog` для manual purge и TTL purge (разные action id)
- [ ] Конфигурация MinIO:
  - [ ] зафиксировать “bucket versioning OFF” для artifacts (или реализовать delete всех версий)
- [ ] Инструменты:
  - [ ] админская ручка “purge now” для просроченных
  - [ ] защита от случайного удаления системных артефактов (доп. подтверждение/теги риска)
