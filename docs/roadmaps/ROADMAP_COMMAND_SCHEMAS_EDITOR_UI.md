# Roadmap: человеко-ориентированный редактор схем команд (CLI + IBCMD)

Цель: сделать единый UI для редактирования **схем команд** (driver catalogs v2) для `cli` и `ibcmd`, чтобы операторы могли безопасно править команды/параметры без ручного JSON, с обязательным `reason`, аудитом и быстрым rollback.

Ключевой принцип хранения: схемы команд храним **в существующем MinIO** как **артефакты** (как и расширения), с версионированием и алиасами.

---

## Термины (как в текущей реализации driver catalogs v2)

- **Base catalog**: полный каталог (generated), read-only, версионируемый артефакт.
- **Overrides catalog**: патч поверх base (hand-edited), версионируемый артефакт.
- **Effective catalog**: `merge(base@approved, overrides@active)` (то, что видит UI builder и что использует оркестратор).

---

## Storage / MinIO (обязательная часть дизайна)

- [ ] Зафиксировать, что source of truth для CLI/IBCMD схем = артефакты в MinIO (через `ArtifactStorageClient`), а не файлы в репо.
- [ ] Использовать существующую модель артефактов (как у расширений): `Artifact` + `ArtifactVersion` + `ArtifactAlias`.
- [ ] Держать 2 артефакта на драйвер:
  - [ ] `driver_catalog.<driver>.base` (aliases: `latest`, `approved`)
  - [ ] `driver_catalog.<driver>.overrides` (alias: `active`)
- [ ] Для версии каталога сохранять метаданные (driver, catalog_version, platform_version, source doc_id/doc_url, fingerprint).
- [ ] Обеспечить быстрый rollback:
  - [ ] rollback = смена алиаса `active`/`approved` на выбранную `ArtifactVersion` (как rollback расширений по версии).

---

## Milestone 0 — уточнение UX/DoD (1-2 дня)

- [ ] Зафиксировать DoD для MVP (CLI+IBCMD):
  - [ ] редактирование overrides на уровне команды и параметра (не всего JSON целиком);
  - [ ] обязательный `reason` на save/promote/import/rollback;
  - [ ] audit log запись на каждое действие;
  - [ ] rollback для overrides (выбор версии) и promote для base (latest -> approved).
- [ ] Описать единый “Command Schema Editor” layout:
  - [ ] список команд (поиск/фильтры);
  - [ ] карточка команды (редактирование);
  - [ ] preview (форма + argv/argv_masked) + diff.

---

## Milestone 1 — Backend: API для редактора (MVP)

### Read model для UI

- [ ] Добавить staff endpoint “editor view model” для `cli|ibcmd`, который возвращает:
  - [ ] base: alias `approved` (+ `latest` метаданные), версии/ids
  - [ ] overrides: alias `active`, версия/id
  - [ ] effective catalog (или base+overrides, если diff/merge делаем на фронте)
  - [ ] etag/версии для optimistic concurrency (предупреждать о конкурирующих правках)

### Write model (save -> active)

- [ ] `POST overrides/update` принять overrides v2 catalog (+ `reason`) и:
  - [ ] валидировать структуру (минимум: `catalog_version`, `driver`, `overrides` shape);
  - [ ] загрузить новую версию в MinIO;
  - [ ] сдвинуть alias `active`;
  - [ ] вызвать `invalidate_driver_catalog_cache(driver)`;
  - [ ] записать audit log (action + outcome + metadata + reason).

### Версии и rollback

- [ ] Добавить “list versions” для base/overrides по драйверу (или безопасно переиспользовать общий API артефактов).
- [ ] Добавить “rollback overrides” endpoint:
  - [ ] вход: `driver`, `version` (или `version_id`), `reason`
  - [ ] действие: сдвиг alias `active` на выбранную версию (без перезагрузки JSON).
- [ ] Добавить “promote base” endpoint (latest -> approved) с `reason` (уже есть promote; проверить требования UI).

### Валидация (особенно для IBCMD)

- [ ] Добавить серверную валидацию effective catalog для IBCMD (минимум: id/argv/scope/risk/params).
- [ ] Добавить серверный “preview/diagnostics” endpoint (опционально для MVP):
  - [ ] проверить конфликт флагов/позиционных параметров;
  - [ ] подсказать потенциально dangerous изменения (risk/scope/permissions).

### Тесты

- [ ] Добавить тесты на:
  - [ ] сохранение overrides -> новая версия + алиас `active`;
  - [ ] rollback алиаса;
  - [ ] audit log с reason;
  - [ ] cache invalidation.

---

## Milestone 2 — Frontend: человеко-ориентированный редактор (MVP)

### Навигация и доступ

- [ ] Добавить страницу `Settings -> Command Schemas` (или заменить текущую `Driver Catalogs`).
- [ ] Доступ: staff + право `operations.manage_driver_catalogs` (не “просто staff”).

### Экран редактора

- [ ] Driver switcher: `CLI` / `IBCMD` (единый UI и единые компоненты).
- [ ] Command list (левая панель):
  - [ ] поиск по id/label/description;
  - [ ] фильтры: scope, risk, disabled, “has overrides”.
- [ ] Command detail (центр):
  - [ ] базовые поля команды (label/description/scope/risk/disabled);
  - [ ] permissions editor (allowed/denied roles/envs, min_db_level) с пресетами;
  - [ ] params editor (таблица параметров, inline edit).
- [ ] Override UX:
  - [ ] per-field toggle “Inherited / Overridden”;
  - [ ] “Reset to base” удаляет ключ из patch.
- [ ] Preview (правая панель):
  - [ ] форма параметров (guided) + `argv/argv_masked` preview;
  - [ ] подсветка sensitive параметров и dangerous команд.
- [ ] Diff:
  - [ ] “что изменится” (base vs effective) по текущей команде/параметрам.

### Save flow

- [ ] Sticky бар “Unsaved changes”.
- [ ] Save modal:
  - [ ] поле `reason` (required);
  - [ ] summary изменений (кол-во команд/параметров).
- [ ] На save:
  - [ ] собрать overrides catalog v2 (патч) и отправить в `overrides/update`;
  - [ ] обновить версии/alias, перезагрузить effective.

---

## Milestone 3 — Rollback + safety rails

- [ ] Rollback UI:
  - [ ] список версий overrides (ovr-*) с датой/автором/причиной (если доступно);
  - [ ] применить выбранную версию (reason required).
- [ ] Опасные изменения:
  - [ ] подтверждение при `risk_level: safe -> dangerous` (и наоборот);
  - [ ] предупреждение при включении disabled команды;
  - [ ] предупреждение при изменении permissions/env constraints.
- [ ] Конкурентные правки:
  - [ ] если `active` версия изменилась с момента загрузки — показать конфликт и предложить refresh.

---

## Milestone 4 — Полировка и эксплуатация

- [ ] Метрики:
  - [ ] счётчики save/promote/rollback, failed validation, conflict occurrences.
- [ ] Документация:
  - [ ] как импортировать ITS;
  - [ ] как откатывать overrides;
  - [ ] рекомендации по permissions/risk_level.
- [ ] Регрессионные тесты UI (минимум smoke на загрузку/сохранение/rollback).

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

