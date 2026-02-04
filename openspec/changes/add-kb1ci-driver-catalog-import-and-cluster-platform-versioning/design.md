# Design: kb1ci → driver catalogs + platform versioning

## Контекст и исходные точки
- `kb.1ci.com` — XWiki, доступен REST API без ИТС авторизации (XML/JSON по `Accept`).
  - Пример страницы: `GET /rest/wikis/xwiki/spaces/OnecInt/spaces/KB/pages/WebHome` (+ `Accept: application/json`)
  - Дерево: `.../pages/<name>/children`
  - Разметка: `syntax: xwiki/2.1`, контент в поле `content` (wiki markup).
- В проекте уже есть import pipeline для ITS:
  - `orchestrator/apps/api_v2/views/driver_catalogs/write.py` → `import_its_command_schemas`
  - build/validate для `cli` и `ibcmd`.

Цель этого change — добавить отдельный источник KB и связать его с многоверсионностью base catalogs и версией платформы по кластерам.

## Архитектурные драйверы
- Воспроизводимость: один и тот же DocSet + parser version → один и тот же результат.
- Fail-closed: любые несоответствия схемам/типам блокируют публикацию.
- Управляемость: администратор видит полный список разделов и вручную маппит DocSet → driver/schema.
- Многоверсионность: несколько наборов документации/каталогов под версии платформы (8.3.23/8.3.24/…).
- i18n-ready: хранить переводимые поля так, чтобы добавить i18n без миграции идентификаторов и без breaking API по умолчанию.

## Предлагаемая модель данных (высокоуровнево)
### KB snapshots
- `Kb1ciSnapshot`:
  - `id`, `created_at`, `source_root` (например `xwiki:OnecInt.KB.WebHome`), `sync_status`
  - `stats` (кол-во страниц/ошибок), `raw_meta` (опционально)
- `Kb1ciPage` (в составе snapshot или как append-only page versions):
  - `doc_id` (стабильный, например `xwiki:OnecInt.KB.1C_Bus.WebHome`)
  - `parent_doc_id`, `title`, `url`, `syntax`, `language`, `translations[]`
  - `version`, `modified_at`, `content_raw` (xwiki markup)
  - `attachments_meta[]` (без скачивания бинарей на MVP)

### DocSets (выбор разделов)
- `Kb1ciDocSet`:
  - `name`, `root_doc_ids[]` (выбранные корни/поддеревья)
  - `include_mode` (root only / subtree), `filters` (опционально: regex по title/url)
  - `target_driver` (`cli`/`ibcmd`), `target_platform_version` (нормализованная `8.3.23`)
  - `language_policy` (default language + fallback list)
  - `validation_policy` (strict/fail-closed)

### ParseRuns
- `Kb1ciParseRun`:
  - `doc_set_id`, `snapshot_id`, `parser_version`
  - `result_catalog` (JSON base catalog v2) + `validation_report` (issues[])
  - `status`: `success|failed|partial`
  - `save_mode`: dry-run / save draft / publish (depends on workflow)

### Platform versioning
- `ClusterPlatformVersion` (или расширение `Cluster.metadata`):
  - `cluster_id`
  - `effective_platform_version_full` (например `8.3.23.1709`)
  - `effective_platform_version_minor` (`8.3.23`)
  - `status` (`ok|unknown|mixed`)
  - `source` (`auto|manual`), `updated_at`, `notes`

### Active base catalogs per version
- Настройка “active base catalog” как отображение:
  - `(driver, platform_version_minor) -> base_catalog_artifact_alias_or_version`
  - хранится tenant-scoped; для staff mutating — требовать явный tenant context.

## API/UX (набросок)
### KB
- `GET /api/v2/kb1ci/tree/` → полное дерево (или список корней + lazy loading), включая `doc_id`, `title`, `children_count`, `translations`.
- `POST /api/v2/kb1ci/sync/` (staff/admin) → создать snapshot и запустить sync (асинхронно).
- `GET/POST/PATCH /api/v2/kb1ci/doc-sets/` → управление DocSets.
- `POST /api/v2/kb1ci/parse/` → запустить parse-run (dry-run по умолчанию), вернуть report + (опционально) catalog.

### Driver catalogs by version
- `GET /api/v2/settings/command-schemas/base/versions/?driver=...&platform_version=8.3.23`
- `POST /api/v2/settings/command-schemas/activate/` (staff/admin) → выбрать active base для `driver+platform_version`.
- `GET /api/v2/settings/command-schemas/resolve/?driver=...&cluster_id=...` → какой base catalog применяется к кластеру (для дебага/UX).

### Cluster platform versions
- `GET/PUT /api/v2/clusters/<id>/platform-version/`:
  - `GET` — effective + provenance
  - `PUT` — manual override (staff/admin, tenant-context для staff)

## Парсинг xwiki/2.1
На MVP предлагается:
- храним raw `content` как есть (xwiki markup),
- для CLI/ibcmd парсинга используем:
  - эвристики по заголовкам/таблицам/код-блокам (pattern-based),
  - набор “parser profiles” на DocSet (если разные разделы отличаются структурой),
  - стабильные идентификаторы команд — из “canonical command name”, а не из локализованного `title`.

Если окажется, что нужен HTML-рендер:
- можно использовать XWiki rendering REST (если доступен без CSRF/token), либо fallback через headless browser в dev-only инструментах.
  - В рамках этого change предпочтение — REST-only, без браузерной автоматизации.

## i18n (future-proof, без breaking)
- Стабильные идентификаторы (`doc_id`, `command_id`, `param_name`) не зависят от языка.
- В каталоге драйвера сохраняем тексты в одном “primary” языке как текущие строки.
- Дополнительно (опционально) сохраняем `*_i18n` в метаданных (`{lang: text}`), но UI/операции по умолчанию используют legacy `string`.

## Последовательность внедрения (минимальная)
1) Синхронизация дерева + хранение snapshot (без парсинга).
2) UI: просмотр дерева + создание DocSets.
3) Parse-run dry-run + отчёт (без publish).
4) Публикация base catalog per version + настройка “active”.
5) Cluster platform versioner (manual override сначала, auto позже) + resolve API.

