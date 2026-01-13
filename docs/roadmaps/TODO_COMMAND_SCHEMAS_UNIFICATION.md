# TODO: Command Schemas — единая точка истины + Raw JSON режимы (cli/ibcmd)

Контекст:
- Сейчас `/settings/driver-catalogs` и `/settings/command-schemas` живут параллельно и могут расходиться.
- Требование: сделать `Command Schemas` единой точкой истины для схем команд `cli/ibcmd`.
- В `Command Schemas` добавить отдельный режим "Raw JSON" (как в driver-catalogs) для прямой правки:
  - base + overrides (основной advanced-режим),
  - отдельный "опасный" режим целиковой правки effective.
- Совместимость с legacy `config/cli_commands.json` не требуется (можно удалять/выключать).
- Доступ: тот же `operations.manage_driver_catalogs`.
- Должно быть расширяемо на будущие драйверы (без жёсткой привязки к cli/ibcmd по всему коду).

Затронутые места (ориентировочно):
- Frontend:
  - `frontend/src/pages/CommandSchemas/CommandSchemasPage.tsx`
  - `frontend/src/pages/DriverCatalogs/DriverCatalogsPage.tsx` (депрекейт/удаление/редирект)
  - `frontend/src/api/commandSchemas.ts`
  - `frontend/src/api/driverCatalogs.ts`
  - `frontend/src/App.tsx`, `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/tests/browser/command-schemas-ui.spec.ts`
- Backend:
  - `contracts/orchestrator/openapi.yaml` (+ regeneration)
  - `orchestrator/apps/api_v2/urls.py`
  - `orchestrator/apps/api_v2/views/driver_catalogs.py`
  - `orchestrator/apps/operations/driver_catalog_artifacts.py`
  - `orchestrator/apps/operations/driver_catalog_effective.py`
  - `orchestrator/apps/api_v2/tests/test_command_schemas_editor.py` (+ новые тесты)

---

## P0 — обязательно (делает Command Schemas SoT)

### Контракты (OpenAPI contract-first)

- [ ] Обновить `contracts/orchestrator/openapi.yaml`:
  - [ ] Добавить write endpoints для base (raw редактирование):
    - [ ] `POST /api/v2/settings/command-schemas/base/update/` (v2 base catalog, reason, expected_etag/If-Match)
  - [ ] Добавить "опасный" write endpoint для effective:
    - [ ] `POST /api/v2/settings/command-schemas/effective/update/` (v2 effective catalog, reason, expected_etag/If-Match)
  - [ ] Уточнить/зафиксировать семантику:
    - base/update: загружает новую версию base и двигает alias `latest` (approved не трогает).
    - effective/update (dangerous): создаёт новый base=effective и сбрасывает overrides в пустой каталог (новая версия overrides + alias `active`).
  - [ ] Сгенерировать клиенты: `./contracts/scripts/generate-all.sh` и убедиться, что фронтенд использует обновлённые типы/клиенты.

### Backend (Orchestrator)

- [ ] Реестр драйверов/возможностей (для расширяемости):
  - [ ] Ввести "capabilities" для драйвера (поддерживает guided editor, raw base edit, raw overrides edit, effective edit, import ITS).
  - [ ] Не размазывать `if driver in {"cli","ibcmd"}` по коду: централизовать список и проверки.

- [ ] Base update endpoint (raw base edit):
  - [ ] Принять v2 base catalog (`DriverCatalogV2`) + `reason`.
  - [ ] Применить оптимистичную конкуренцию по ETag:
    - [ ] принимать `If-Match` header или `expected_etag` в body (единый приоритет).
    - [ ] при рассинхроне возвращать 409 + текущий ETag.
  - [ ] Валидировать base каталог (строго, как для effective; минимум - структура, команды/параметры, invariants по драйверу).
  - [ ] Upload version в MinIO artifacts (base) и сдвиг alias `latest`.
  - [ ] Audit log (action/outcome/metadata/reason) + метрики.
  - [ ] `invalidate_driver_catalog_cache(driver)` после успешного апдейта.

- [ ] Effective update endpoint (dangerous):
  - [ ] Принять v2 effective catalog + `reason`.
  - [ ] Оптимистичная конкуренция (ETag / 409) как выше.
  - [ ] Валидация как для effective (строго).
  - [ ] Сохранение:
    - [ ] Upload base version = payload, сдвиг alias `latest`.
    - [ ] Создать/загрузить пустой overrides catalog и сдвиг alias `active` (чтобы effective стал равен base).
  - [ ] Audit log должен явно фиксировать "dangerous overwrite effective" и факт reset overrides.
  - [ ] Метрики/алерты: отдельный счётчик для effective/update.

- [ ] Убрать зависимость от legacy файла (совместимость не нужна):
  - [ ] Прекратить `save_cli_command_catalog(...)` в flow `command-schemas` (import ITS / base update / effective update).
  - [ ] Удалить/депрекейт `bootstrap-cli` endpoint и связанную UI-логику/копирайт.
  - [ ] Убедиться, что runtime execution (`/api/v2/operations/driver-commands/`) получает данные только из artifacts/effective.

- [ ] Депрекейт `/settings/driver-catalogs` для cli/ibcmd:
  - [ ] Запретить write операции для `cli/ibcmd` через `/settings/driver-catalogs/*` (410/400 + явный код ошибки).
  - [ ] (Опционально) Оставить read-only или редирект-сообщение: "единая точка истины = Command Schemas".

### Frontend (UI)

- [ ] В `Command Schemas` добавить переключение режимов:
  - [ ] `Guided` (текущий редактор) / `Raw JSON` (advanced).
  - [ ] URL-параметры для deeplink: `?driver=cli|ibcmd&mode=guided|raw`.

- [ ] `Raw JSON` режим (base/overrides/effective):
  - [ ] Табы: `Base`, `Overrides`, `Effective`.
  - [ ] `Base` и `Overrides` — редактируемые JSON editor'ы с `Format/Copy`.
  - [ ] `Effective` — read-only viewer (с `Copy`).
  - [ ] Save flows:
    - [ ] `Save base...` -> reason required -> вызывает `base/update`.
    - [ ] `Save overrides...` -> reason required -> вызывает существующий `overrides/update`.
    - [ ] Перед сохранением: `validate` + показ ошибок/варнингов (не дать сохранить при errors).
  - [ ] Поддержка optimistic concurrency:
    - [ ] передавать `expected_etag`/`If-Match` на write,
    - [ ] при 409 показывать конфликт и предлагать refresh.

- [ ] Dangerous режим "Edit effective":
  - [ ] Явный переключатель внутри `Effective` (например, "Enable dangerous edit").
  - [ ] Double-confirm (checkbox + modal) + заметный текст о последствиях (перезапись base + reset overrides).
  - [ ] `Save effective...` -> reason required -> вызывает `effective/update`.

- [ ] Убрать/заменить `Driver Catalogs` как источник правды:
  - [ ] Скрыть пункт меню `/settings/driver-catalogs` или заменить на редирект в `Command Schemas` (`mode=raw`).
  - [ ] Если оставляем страницу временно: сделать её read-only и показать баннер "Moved to Command Schemas".

### Тесты и DoD

- [ ] Backend tests:
  - [ ] base/update: создаёт версию + двигает `latest`, пишет audit, invalidates cache, конфликт по ETag -> 409.
  - [ ] effective/update: создаёт base версию + reset overrides (новая overrides версия), audit/metrics, конфликт по ETag.
  - [ ] import ITS: без записи в legacy файл (после отключения совместимости).

- [ ] Frontend e2e (Playwright):
  - [ ] Raw mode smoke: открыть страницу, увидеть base/overrides/effective.
  - [ ] Save overrides: правка поля -> reason -> success -> versions обновились.
  - [ ] Save base: правка JSON -> reason -> success.
  - [ ] Effective dangerous: включение режима -> подтверждение -> save -> overrides reset.

DoD (для завершения P0):
- Command Schemas является единственной точкой записи для cli/ibcmd.
- Raw JSON режим доступен в Command Schemas (base/overrides/effective + dangerous effective edit).
- В UI и копирайте нет упоминаний "опубликуйте legacy config/cli_commands.json".
- Все мутации требуют `reason`, все мутации пишутся в audit.

---

## P1 — желательно (полировка и эксплуатация)

- [ ] UX: скачать JSON (export) для base/overrides/effective (кнопка Download).
- [ ] UX: показать "что изменится" перед сохранением base/effective (diff summary).
- [ ] Вынести общие компоненты JSON editor (Format/Copy/height/path) в переиспользуемый компонент для Command Schemas.
- [ ] Документация для операторов: короткий гайд "Guided vs Raw", когда использовать dangerous effective edit.

---

## P2 — опционально (cleanup и подготовка к новым драйверам)

- [ ] Полное удаление/выпиливание `/settings/driver-catalogs` (UI + API), либо оставить только для legacy/non-schema драйверов.
- [ ] Единая модель "drivers registry" на backend + фронтенде:
  - [ ] выдача списка драйверов/возможностей через API,
  - [ ] UI строится по capabilities (готово к ras/odata и будущим драйверам).
- [ ] Расширить overrides-формат (если понадобится правка top-level полей каталога через overrides, а не только commands_by_id).

