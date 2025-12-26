# Artifact Storage V2 Roadmap (MinIO + Postgres)

Цель: единое хранилище артефактов 1С с версионированием и алиасами, основанное на MinIO (blob) + Postgres (metadata).
Порядок работ: **сначала backend, затем frontend**.

## Принципы
- **Immutable версии**: загрузка = новая версия, без перезаписи.
- **Единый API** для всех типов артефактов (расширения, конфигурации, dt/epf/erf).
- **Alias-first**: stable/approved/latest для безопасного выбора в UI.
- **Без миграции legacy extension-файлов** (оставить как есть).

---

## Этап 1 — Backend: модель и хранилище

### 1.1 Модели и миграции (Postgres)
- `Artifact`:
  - `id`, `name`, `kind`, `is_versioned`, `tags[]`, `created_by`, `created_at`
- `ArtifactVersion`:
  - `id`, `artifact_id`, `version`, `storage_key`, `size`, `checksum`, `metadata JSONB`, `created_at`, `created_by`
- `ArtifactAlias`:
  - `artifact_id`, `alias`, `version_id`
- `ArtifactUsage`:
  - `artifact_id`, `version_id`, `operation_id`, `database_id`, `used_at`

**Definition of Done**
- Миграции применяются без ошибок.
- Базовые CRUD модели доступны через Django shell.

### 1.2 MinIO интеграция
- Базовый storage client (S3 compatible).
- Стандарт ключей: `artifacts/{artifact_id}/{version}/{filename}`.
- Переиспользуем общие утилиты (checksum, size, mime).

**Definition of Done**
- Загрузка/скачивание объекта через storage client.
- Сохранение storage_key + checksum в БД.

### 1.3 API v2 (artifacts)
Endpoints (черновой набор):
- `POST /api/v2/artifacts` — создать сущность
- `GET /api/v2/artifacts` — поиск/листинг (filter: kind, name, tag)
- `POST /api/v2/artifacts/{id}/versions` — загрузить новую версию (multipart)
- `GET /api/v2/artifacts/{id}/versions` — список версий
- `POST /api/v2/artifacts/{id}/aliases` — создать/обновить alias (stable/latest/approved)
- `GET /api/v2/artifacts/{id}/aliases` — список alias
- `GET /api/v2/artifacts/{id}/versions/{version}/download` — скачать

**Definition of Done**
- OpenAPI контракт готов и синхронизирован.
- Основные сценарии покрыты (create, upload version, list versions, alias).

### 1.4 Интеграция операций
- Новые поля в payload: `artifact_id`, `artifact_version`, `artifact_alias`.
- Резолв alias → version → storage_key.
- Привязка к batch operation: запись `ArtifactUsage`.

**Definition of Done**
- Операция install_extension принимает artifact_id/version/alias.
- Audit trail сохраняется.

---

## Этап 2 — Frontend: UI v2

### 2.1 Каталог артефактов
- Новый экран “Artifacts” (фильтры по type, name, tags).
- Просмотр списка версий и alias.

**Definition of Done**
- Базовый просмотр и поиск артефактов работает.

### 2.2 Wizard: Install Extension (v2)
- Выбор Artifact + Version/Alias.
- Preview (size, checksum, created_by, created_at).
- Удалить legacy upload из wizard для install_extension.

**Definition of Done**
- Wizard валиден без upload, только через artifact selection.
- Review отображает artifact + version/alias.

### 2.3 Глобальная интеграция
- Обновить API клиент, типы, маппинг.
- Удалить старые поля `extension_filename` в UI (кроме legacy-фоллбэка при необходимости).

**Definition of Done**
- UI полностью использует v2 storage для install_extension.

---

## Вопросы / решения
- Границы mini-git: только шаблоны или также исходники конфигураций/расширений? всё
- Политики хранения: сколько версий хранить для каждого kind? три последние
- Нужна ли модерация/approval перед alias=stable/approved? да, через UI
- Как обрабатывать удаление артефактов/версий? мягкое удаление с возможностью восстановления.
