# Roadmap: Schema-driven IBCMD (полный охват команд 4.10.* + IDE-like UI)

Цель: уйти от хардкода `ibcmd_*` и получить **schema-driven** механизм, аналогичный `designer_cli`:
- полный список команд IBCMD берётся из каталога (генерируется из ITS-документации);
- UI строит удобную форму (guided) по схеме и поддерживает manual режим (как в IDE);
- Orchestrator валидирует и нормализует вызов (RBAC-ready), Worker исполняет и стримит прогресс/логи;
- покрываем **все команды** раздела `4.10.*` (server/infobase/config/extension/mobile-app/mobile-client/session/lock/eventlog/binary-data-storage).

---

## Драйверы и проблема унификации

Сейчас:
- `designer_cli` уже “catalog-driven”: есть каталог команд, UI builder, один operation type и “сырой” runner в worker.
- `ibcmd` частично “типизирован”: набор `ibcmd_*` (backup/restore/replicate/create/load_cfg/extension_update) + возможность выполнить `args[]` напрямую.

Нужно:
- для IBCMD сделать тот же паттерн, что и для designer CLI: **каталог → UI форма → нормализация → запуск**;
- унифицировать **схему команд и UI builder** для обоих драйверов;
- не сливать драйверы в один “монолитный”, а вынести общий слой исполнения (artifact/masking/exec) в shared-пакет.

---

## Ключевые требования (фиксировано)

1) Охват: **все команды** IBCMD из `4.10.*`.
2) Доступ к каталогу: **всем auth users**, с заделом на RBAC-фильтрацию позже.
3) Подключение к standalone server:
   - online: `--pid` и `--remote`;
   - offline: `--config`, `--data`, `--dbms/--db-server/--db-name/--db-user/--db-pwd`, и т.п.
4) Удобный UI:
   - guided режим по схеме;
   - manual режим (raw args);
   - поддержка `artifact://` (MinIO) для файловых параметров.
5) Безопасность:
   - пометка “dangerous” команд + подтверждение в UI;
   - подготовка к RBAC (в будущем: ограничение команд/режимов по ролям).

---

## Термины

- **Driver catalog**: описание команд и параметров драйвера (формат v2), которое UI использует для построения форм.
- **Base catalog**: полный каталог, генерируется из ITS и считается “read-only”. Хранится как версионируемый артефакт в MinIO.
- **Overrides catalog**: локальные правки поверх base (UI/labels/defaults/risk/RBAC). Хранится как версионируемый артефакт в MinIO.
- **Command descriptor**: описание команды: `id`, `argv`, `params`, `risk_level`, `scope`.
- **Schema-driven execution**: UI отправляет `command_id + params`, Orchestrator строит канонический `argv[]`, Worker исполняет.
- **Scope**:
  - `per_database`: команда исполняется “на выбранных базах” (как обычный BatchOperation).
  - `global`: команда относится к standalone server целиком (не должна дублироваться по базам).

---

## Текущее состояние (as-is) и пробелы

1) В UI нет общего “Command Builder” для IBCMD (есть только частичные формы под `ibcmd_*`).
2) Нет каталога IBCMD команд и импорта из ITS.
3) Нет публичного (auth) endpoint для чтения driver-catalog (есть только staff-only в `/settings/driver-catalogs/*`).
4) Модель `BatchOperation` и API сейчас заточены на `database_ids min_length=1`:
   - `global` команды IBCMD (server/session/lock/etc.) некуда корректно “положить”.
5) `--pid` в проде с несколькими worker-host’ами не детерминирован (нужна стратегия).

---

## Целевая архитектура (to-be)

### 1) Каталог команд (source of truth) — C) Base+Overrides v2 (RBAC-ready) + MinIO artifacts

Хранение:
- Base catalogs (generated):
  - `driver_catalog.ibcmd.base` — base v2 каталог для IBCMD
  - `driver_catalog.cli.base` — base v2 каталог для Designer CLI (миграция/экспорт из текущего формата)
- Overrides catalogs (hand-edited, small diffs):
  - `driver_catalog.ibcmd.overrides`
  - `driver_catalog.cli.overrides`

Все каталоги — **версионируемые артефакты** (MinIO + Postgres registry). Управление версиями — через алиасы:
- Base:
  - `latest` — последняя импортированная версия (не обязательно “продовая”)
  - `approved` — активная “last-known-good” версия, которую видят пользователи и используют операции
- Overrides:
  - `active` — текущие overrides (можно быстро откатывать сменой алиаса)

Runtime модель:
- Orchestrator получает “effective catalog” как `merge(base@approved, overrides@active)`.
- Далее (в будущем) применяет `filter_catalog_for_user(user, effective_catalog)` (RBAC-ready).

Надёжность:
- In-process cache по ключу `(base_version_id, overrides_version_id)`.
- Fallback: last-known-good кэш на диске/в БД, чтобы UI не “падал” при временной недоступности MinIO.

### 2) API слой

- Staff-only:
  - `POST /api/v2/settings/driver-catalogs/import-its` (driver=ibcmd|cli):
    - строит base v2 из ITS/registry,
    - загружает как новую версию `*.base`,
    - обновляет алиас `latest`.
  - `POST /api/v2/settings/driver-catalogs/promote`:
    - переводит `*.base:approved` на выбранную версию (rollout/rollback).
  - `GET/POST /api/v2/settings/driver-catalogs/overrides/get|update`:
    - читает/пишет `*.overrides` как новую версию и сдвигает `active`.
  - `GET /api/v2/settings/driver-catalogs/versions|aliases`:
    - список версий/алиасов для UI (можно проксировать существующие `/api/v2/artifacts/*`).
  - `GET /api/v2/settings/driver-catalogs/diff`:
    - diff “base vs overrides” и/или “version A vs version B” (для ревью перед promote).
- Auth users:
  - `GET /api/v2/operations/driver-commands/?driver=ibcmd` (возвращает каталог, отфильтрованный под пользователя)

### 3) Исполнение (Operation Types)

Добавить один универсальный тип:
- `ibcmd_cli` — schema-driven запуск команды из каталога (как `designer_cli`).

Старые `ibcmd_*`:
- оставить как “shortcuts” (и позже/по желанию мигрировать UI на `ibcmd_cli`).

### 4) Где строится argv

Рекомендуемый вариант (RBAC-ready):
- UI отправляет `command_id + params`.
- Orchestrator по каталогу:
  - валидирует `command_id` и параметры;
  - строит канонический `argv[]` (включая `yes/no`, enum и positional);
  - сохраняет в `BatchOperation.payload.data.argv` и `payload.data.argv_masked` (для аудита).
- Worker только исполняет `argv[]`, плюс делает `artifact://` resolve и masking при логировании.

---

## Формат driver catalog (v2, Base + Overrides)

### Base catalog (полный, генерируемый)

```json
{
  "catalog_version": 2,
  "driver": "ibcmd",
  "platform_version": "8.3.27",
  "source": {
    "type": "its_import",
    "doc_id": "TI000001193",
    "section_prefix": "4.10"
  },
  "generated_at": "2026-01-04T12:00:00Z",
  "commands_by_id": {
    "infobase.extension.update": {
      "label": "infobase extension update",
      "description": "Установить значения свойств у выбранного расширения.",
      "argv": ["infobase", "extension", "update"],
      "scope": "per_database",
      "risk_level": "safe",
      "params_by_name": {
        "name": { "kind": "flag", "flag": "--name", "expects_value": true, "required": true },
        "safe_mode": { "kind": "flag", "flag": "--safe-mode", "expects_value": true, "required": false, "enum": ["yes", "no"] }
      },
      "ui": { "group": "Infobase / Extension" },
      "source_section": "4.10.4.7.12. Команды группы extension"
    }
  }
}
```

### Overrides catalog (маленький, ручной)

```json
{
  "catalog_version": 2,
  "driver": "ibcmd",
  "overrides": {
    "commands_by_id": {
      "infobase.extension.update": {
        "risk_level": "dangerous",
        "ui": { "hidden": false },
        "params_by_name": {
          "safe_mode": { "default": "yes" }
        }
      }
    }
  }
}
```

### Семантика merge (важно для RBAC и стабильных диффов)

- Ключи верхнего уровня: deep-merge объекта `overrides` поверх `base` (без удаления полей по умолчанию).
- `commands_by_id`: merge по `command_id` (стабильно, без массивов/индексов).
- `params_by_name`: merge по `param.name`.
- “Отключение” команды/параметра не через удаление, а через явные флаги:
  - `ui.hidden=true` (скрыть в UI),
  - `disabled=true` (запретить выполнение даже при ручном вводе),
  - (RBAC позже) `permissions.allowed_roles` / `permissions.deny_roles`.

### Примечания по полям

- `id` строго ASCII, стабильный и уникальный.
- `argv` всегда массив токенов без “ibcmd” в начале (это добавляет runner).
- `risk_level`: минимум `safe|dangerous` (дальше можно расширять).
- `scope`: минимум `per_database|global`.
- `params_by_name.*.input_type` / `artifact_kinds` / `file_extensions` добавляем эвристикой при импорте.

---

## Roadmap по этапам

### Phase 0 — Дизайн, контракты, “общая схема” (MVP contracts-first)

Deliverables:
- Единый JSON schema / TS types для driver catalogs v2 (`cli` + `ibcmd`).
- Контракт merge (Base + Overrides) + формат overrides.
- Naming/aliases стратегия (`latest/approved/active`) и политика rollback.
- OpenAPI контракт для:
  - public read endpoint `GET /api/v2/operations/driver-commands/`
  - staff import endpoint `POST /api/v2/settings/driver-catalogs/import-its` (ibcmd)

Ключевые решения:
- `ibcmd_cli` как новый operation type (короткий, влезает в `operation_type max_length=32`).
- `argv` строит Orchestrator (рекомендовано), чтобы RBAC/валидация были на сервере.

### Phase 1 — Backend: IBCMD catalog parser + base artifact (MinIO)

1) Реализовать `orchestrator/apps/operations/ibcmd_catalog_v2.py`:
   - `build_base_catalog_from_its(payload) -> catalog_v2`
   - `validate_catalog_v2(catalog)`
2) Реализовать storage слой “driver catalog as artifacts”:
   - `get_or_create_catalog_artifacts(driver)` → `{base_artifact, overrides_artifact}`
   - `upload_base_catalog_version(driver, catalog, version)` → обновляет алиас `latest`
   - `promote_base_alias(driver, version, alias='approved')`
   - на первом запуске: создать пустой overrides (alias `active`).
3) Поддержать `driver=ibcmd` в `/api/v2/settings/driver-catalogs/import-its/`:
   - генерировать v2 base и грузить как artifact version.
4) Тесты:
   - unit: структура `commands_by_id`, уникальность `id`, валидность `argv/params`.
   - snapshot (опционально): стабилизировать генерацию и хранить ожидаемый результат.

### Phase 2 — Backend: Overrides + merge + public read endpoint (auth users) + “задел под RBAC”

1) Реализовать merge: `merge_catalogs(base, overrides) -> effective` (v2).
2) Реализовать `GET/POST /api/v2/settings/driver-catalogs/overrides/get|update`:
   - update создаёт новую версию overrides и сдвигает `active`.
3) Добавить `GET /api/v2/operations/driver-commands/?driver=ibcmd|cli`:
   - читает `base@approved` и `overrides@active`, возвращает effective catalog для UI builders.
   - возвращает также метаданные: `{base_version, overrides_version, generated_at}` и ETag.
4) Встроить “hooks” под RBAC:
   - `filter_catalog_for_user(user, catalog)` (пока passthrough).
5) Кэширование и отказоустойчивость:
   - in-process cache + invalidate на `import/promote/overrides.update`,
   - LKG fallback на случай недоступности MinIO.

### Phase 3 — Execution model: поддержка global scope команд

Причина: команды `4.10.*` включают server/session/lock/eventlog/binary-data-storage, которые **не должны** исполняться N раз по списку баз.

Варианты:
- A) Расширить `BatchOperation/Task`, чтобы поддержать `global` операции без `target_databases` (рекомендуется).
- B) Ввести отдельную модель `SystemOperation` (дороже по инфраструктуре).

MVP-подход (A):
1) Разрешить `database_ids` быть пустым для operation types со `scope=global`.
2) Обновить сериализаторы/permission checks:
   - на старте можно ограничить `global` команды staff-only, но схема должна позволять RBAC позже.
3) Обновить `Task` модель, если `database` сейчас обязательный FK:
   - либо `database` nullable для global tasks,
   - либо отдельный “virtual task” без FK.

### Phase 4 — Execution: `ibcmd_cli` end-to-end (Orchestrator + Worker)

1) Добавить новый operation type:
   - `BatchOperation.TYPE_IBCMD_CLI = 'ibcmd_cli'`
   - registry + catalog UI meta
2) API execute:
   - либо расширить существующий `execute-ibcmd`,
   - либо использовать общий `/api/v2/operations/execute/`.
3) Payload (рекомендация):
```json
{
  "command_id": "infobase.extension.update",
  "params": {
    "name": "MyExt",
    "safe_mode": "yes"
  },
  "connection": {
    "remote": "http://host:port",
    "pid": null,
    "offline": {
      "dbms": "PostgreSQL",
      "db_server": "db:5432",
      "db_name": "db",
      "db_user": "u",
      "db_pwd": "p"
    }
  }
}
```
4) Orchestrator:
   - валидирует `command_id`, параметры и scope;
   - собирает `argv[]` (и `argv_masked[]`) по каталогу и параметрам;
   - сохраняет в `payload.data`.
5) Worker:
   - получает `argv[]`, выполняет через ibcmd executor;
   - резолвит `artifact://` в аргументах;
   - маскирует секреты в логах/таймлайне.

`--pid` стратегия:
- MVP: разрешить только в dev/staging (или при явном allowlist env), иначе ошибка.
- Далее: worker affinity (маршрутизация на host) — отдельный проект.

### Phase 5 — Frontend: общий Command Builder (cli + ibcmd)

1) Вынести общий компонент:
   - `CommandCatalogBuilder(driver)` + общий `ParamField`.
2) Подключить:
   - `designer_cli` guided режим переводится на общий builder (опционально),
   - `ibcmd_cli` полностью на общий builder.
3) Safety UX:
   - `risk_level=dangerous` → confirm modal + пояснение.
4) Manual режим:
   - Monaco editor для raw args (один аргумент в строке) + подсветка/валидация.

### Phase 6 — Унификация worker исполнения (shared abstraction)

Цель: не объединять драйверы целиком, но убрать дублирование.

1) Вынести общий пакет, например `worker/internal/commandrunner`:
   - resolve `artifact://` args
   - запуск процесса (stdout/stderr, timeout)
   - masking секретов
   - (опционально) upload outputs в artifacts
2) `designerops` и `ibcmdops` остаются адаптерами:
   - строят args и credentials context,
   - вызывают runner.

### Phase 7 — RBAC и governance

1) Добавить поля в каталоге:
   - `permissions`, `allowed_roles`, `tags`
2) Реализовать `filter_catalog_for_user`:
   - сначала coarse (staff vs non-staff),
   - затем полноценный RBAC.
3) Аудит:
   - логирование `command_id`, scope, initiator, параметров (masked).

### Phase 8 — Миграция/депрекация legacy `ibcmd_*` (по желанию)

1) Оставить `ibcmd_*` как shortcuts для часто используемых операций (UI/UX).
2) Для остальных — `ibcmd_cli`.
3) Если решим упростить:
   - пометить `ibcmd_*` deprecated в каталоге операций,
   - перевести UI на `ibcmd_cli`.

---

## Тестирование и качество

- Parser:
  - unit tests на “все `4.10.*` разделы → команды”;
  - snapshot тесты на ITS 8.3.27 (и добавление нового снапшота при апгрейде версии).
- API:
  - тесты на public read endpoint (auth) + staff import/update.
- Worker:
  - тесты на сборку args из `argv[]` и masking,
  - тесты на artifact resolve.
- Frontend:
  - Playwright тесты формы builder (id поля, basic UX).

---

## Риски и меры

1) Хрупкий парсинг ITS (версия/формат текста):
   - snapshot + версионирование каталогов.
2) Aliases/версии и человеческий фактор:
   - `latest != approved`, promote через ревью/diff,
   - быстрый rollback сменой алиаса.
3) Недоступность MinIO:
   - кэш LKG + graceful деградация (UI видит последний рабочий каталог).
4) `--pid` в проде (несколько host’ов):
   - запрет/ограничение в MVP, затем affinity.
5) Опасные команды (`delete`, `clear`, etc.):
   - `risk_level`, confirm, RBAC, audit.
6) Drift схемы между UI и backend:
   - build argv на backend (рекомендуется), UI отправляет только params.
