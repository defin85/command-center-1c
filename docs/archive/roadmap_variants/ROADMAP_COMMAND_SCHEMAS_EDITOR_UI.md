# Roadmap: человеко-ориентированный редактор схем команд (CLI + IBCMD)

Цель: сделать единый UI для редактирования **схем команд** (driver catalogs v2) для `cli` и `ibcmd`, чтобы операторы могли безопасно править команды/параметры без ручного JSON, с обязательным `reason`, аудитом и быстрым rollback.

Ключевой принцип хранения: схемы команд храним **в существующем MinIO** как **артефакты** (как и расширения), с версионированием и алиасами.

Текущий статус (2026-01-12):

- Milestone 1 (Backend API) — реализован.
- Milestone 2 (Frontend) — реализован: человеко-ориентированный редактор (списки/фильтры/формы) + preview/diff/validate/save/rollback.
- Milestone 3 (Rollback + safety rails) — реализован.
- Milestone 4 (Полировка и эксплуатация) — реализован.

---

## Термины (как в текущей реализации driver catalogs v2)

- **Base catalog**: полный каталог (generated), read-only, версионируемый артефакт.
- **Overrides catalog**: патч поверх base (hand-edited), версионируемый артефакт.
- **Effective catalog**: `merge(base@approved, overrides@active)` (то, что видит UI builder и что использует оркестратор).

---

## Storage / MinIO (обязательная часть дизайна)

- [x] Зафиксировать, что source of truth для CLI/IBCMD схем = артефакты в MinIO (через `ArtifactStorageClient`) и `Artifact*` модели (legacy `config/cli_commands.json` остается для совместимости/импорта).
- [x] Использовать существующую модель артефактов (как у расширений): `Artifact` + `ArtifactVersion` + `ArtifactAlias`.
- [x] Держать 2 артефакта на драйвер:
  - [x] `driver_catalog.<driver>.base` (aliases: `latest`, `approved`)
  - [x] `driver_catalog.<driver>.overrides` (alias: `active`)
- [x] Для версии каталога сохранять метаданные (driver, catalog_version, platform_version, source*, generated_at) + fingerprint в строке версии (`ovr-<fp>` / `<platform>-<doc_id>-<fp>`).
- [x] Обеспечить быстрый rollback:
  - [x] rollback = смена алиаса `active`/`approved` на выбранную `ArtifactVersion` (как rollback расширений по версии).

---

## Milestone 0 — уточнение UX/DoD (1-2 дня)

- [x] Зафиксировать DoD для MVP (Milestone 1 + временный UI рядом):
  - [x] Доступ: `IsAdminUser` + право `operations.manage_driver_catalogs` (403 без права).
  - [x] На любые изменения обязателен `reason`: save overrides / rollback overrides / promote base / import ITS.
  - [x] Оптимистичная конкуренция: ETag на editor-view, `If-Match`/`expected_etag` на write (409 CONFLICT при рассинхроне).
  - [x] Серверная валидация effective catalog:
    - [x] `ibcmd`: строгая (id/argv/scope/risk/params) + диагностика конфликтов флагов/позиционных.
    - [x] `cli`: строгая (id/argv[0]=="/<id>"/scope/risk/params schema).
  - [x] Диагностика/UX endpoints для UI: validate/preview/diff + audit list.
  - [x] Хранилище/версии: версии артефактов + алиасы, быстрый rollback/promote через переключение алиаса.
  - [x] UI v0 (временно): редактирование overrides как JSON (без человеко-ориентированного редактора) + read-only effective.
- [x] Описать layout для UI v0 (для проверки API и первичного UX):
  - [x] Driver switcher (CLI/IBCMD).
  - [x] Блок версий (base approved/latest, overrides active) + ETag.
  - [x] Overrides JSON editor + Save modal (reason required).
  - [x] Rollback modal (выбор версии overrides + reason required).
  - [x] Effective catalog viewer (read-only).

---

## Milestone 1 — Backend: API для редактора (MVP)

### Read model для UI

- [x] Добавить staff endpoint “editor view model” для `cli|ibcmd`, который возвращает:
  - [x] base: alias `approved` (+ `latest` метаданные), версии/ids
  - [x] overrides: alias `active`, версия/id
  - [x] effective catalog (merge делаем на бэке)
  - [x] ETag для optimistic concurrency (`If-None-Match` -> 304, `If-Match`/`expected_etag` -> 409)

### Write model (save -> active)

- [x] `POST overrides/update` принять overrides v2 catalog (+ `reason`) и:
  - [x] валидировать структуру (минимум: `catalog_version`, `driver`, `overrides` shape);
  - [x] валидировать effective catalog (строго для `ibcmd` и `cli`);
  - [x] загрузить новую версию в MinIO;
  - [x] сдвинуть alias `active`;
  - [x] вызвать `invalidate_driver_catalog_cache(driver)`;
  - [x] записать audit log (action + outcome + metadata + reason).

### Версии и rollback

- [x] Добавить “list versions” для base/overrides по драйверу.
- [x] Добавить “rollback overrides” endpoint:
  - [x] вход: `driver`, `version` (или `version_id`), `reason`
  - [x] действие: сдвиг alias `active` на выбранную версию (без перезагрузки JSON).
- [x] Добавить “promote base” endpoint (latest/approved) с `reason`.

### Валидация (особенно для IBCMD)

- [x] Добавить серверную валидацию effective catalog (IBCMD + CLI, включая проверки конфликтов флагов/позиционных параметров).
- [x] Добавить серверные endpoints для диагностики/UX:
  - [x] `POST /validate/` (в т.ч. draft overrides без сохранения)
  - [x] `POST /preview/` (argv/argv_masked, в т.ч. draft overrides)
  - [x] `POST /diff/` (base -> effective diff по команде, в т.ч. draft overrides)
  - [x] `GET /audit/` (выдача audit log по `driver_catalog.*`)

### Тесты

- [x] Добавить тесты на:
  - [x] сохранение overrides -> новая версия + алиас `active`;
  - [x] rollback алиаса;
  - [x] audit log с reason;
  - [x] cache invalidation.

---

## Milestone 2 — Frontend: человеко-ориентированный редактор (MVP)

### Навигация и доступ

- [x] Добавить страницу `Settings -> Command Schemas` (рядом с текущей `Driver Catalogs`).
- [x] Доступ: staff + право `operations.manage_driver_catalogs` (не “просто staff”).
  - [x] Backend: все endpoints `/api/v2/settings/command-schemas/*` и `/api/v2/settings/driver-catalogs/*` защищены `operations.manage_driver_catalogs`.
  - [x] Frontend: скрыть пункт меню/роут без права.

### Экран редактора

- [x] Driver switcher: `CLI` / `IBCMD` (временный UI).
- [x] Command list (левая панель):
  - [x] поиск по id/label/description;
  - [x] фильтры: scope, risk, disabled, “has overrides”.
- [x] Command detail (центр):
  - [x] базовые поля команды (label/description/scope/risk/disabled);
  - [x] permissions editor (allowed/denied roles/envs, min_db_level) (без пресетов);
  - [x] params editor (inline edit).
- [x] Override UX:
  - [x] per-field toggle “Inherited / Overridden”;
  - [x] “Reset to base” удаляет ключ из patch.
- [x] Preview (правая панель):
  - [x] форма параметров (guided) + `argv/argv_masked` preview;
  - [x] подсветка sensitive параметров и dangerous команд.
- [x] Diff:
  - [x] “что изменится” (base vs effective) по текущей команде/параметрам.

### Save flow

- [x] Sticky бар “Unsaved changes”.
- [x] Save modal:
  - [x] поле `reason` (required);
  - [x] summary изменений (кол-во команд/параметров).
- [x] На save:
  - [x] собрать overrides catalog v2 (патч) и отправить в `overrides/update`;
  - [x] обновить версии/alias, перезагрузить effective.

---

## Milestone 3 — Rollback + safety rails

- [x] Rollback UI:
  - [x] список версий overrides (ovr-*) с датой/автором/причиной (если доступно);
  - [x] применить выбранную версию (reason required).
- [x] Опасные изменения:
  - [x] подтверждение при `risk_level: safe -> dangerous` (и наоборот);
  - [x] предупреждение при включении disabled команды;
  - [x] предупреждение при изменении permissions/env constraints.
- [x] Конкурентные правки:
  - [x] если `active` версия изменилась с момента загрузки — показать конфликт и предложить refresh.

---

## Milestone 4 — Полировка и эксплуатация

- [x] Метрики:
  - [x] счётчики save/promote/rollback, failed validation, conflict occurrences + errors по `error.code` (включая ранние причины вроде `BASE_CATALOG_MISSING`).
- [x] Документация:
  - [x] как импортировать ITS;
  - [x] как откатывать overrides;
  - [x] рекомендации по permissions/risk_level.
- [x] Регрессионные тесты UI (минимум smoke на загрузку/сохранение/rollback).

---

## Ссылки на текущие реализации (для ориентира при разработке)

- [ ] Backend:
  - [ ] `orchestrator/apps/api_v2/views/driver_catalogs.py` (staff endpoints: import/promote/overrides)
  - [ ] `orchestrator/apps/operations/driver_catalog_artifacts.py` (MinIO artifacts для base/overrides)
  - [ ] `orchestrator/apps/operations/driver_catalog_effective.py` (merge + cache + LKG)
  - [ ] `orchestrator/apps/api_v2/views/operations.py` (`GET /api/v2/operations/driver-commands/`)
- [ ] Frontend:
  - [ ] `frontend/src/components/driverCommands/DriverCommandBuilder.tsx` (preview builder)
  - [ ] `frontend/src/pages/DriverCatalogs/DriverCatalogsPage.tsx` (текущий JSON-редактор — кандидат на замену)
