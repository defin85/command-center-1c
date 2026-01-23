## Контекст
Платформа уже умеет:
- хранить `ui.action_catalog` (bindings “action → executor/driver/command/workflow”);
- для schema-driven драйверов формировать канонический `argv[]` и `argv_masked[]` на стороне API до enqueue;
- запускать действия через существующие endpoints (`execute-ibcmd-cli`, `execute-workflow`, `designer_cli`) и показывать прогресс/результаты через Operations UI/Streams.

Но отсутствует явный и единый слой “планирования”:
- неясно, какие значения откуда взялись и где применились;
- часть поведения может быть runtime-only (на worker), и это не отображается;
- безопасное логирование неполное/неструктурированное.

## Цели / Не цели
### Цели
- Дать staff пользователю понятный и безопасный ответ:
  - **что будет выполнено** (preview),
  - **что выполнено** (persisted plan),
  - **откуда что берётся** (provenance),
  - **что было подставлено автоматически** (и почему).
- Не хранить секреты в plan/provenance: только masked представление и метаданные.
- Сразу покрыть:
  - schema-driven CLI executors (`ibcmd_cli`, `designer_cli`),
  - `workflow` executors.
- Показывать в UI в трёх местах:
  - `/operations` details (и детали workflow executions),
  - `/databases` drawer запуска,
  - `/settings/action-catalog` preview для staff.
- Видимость plan/provenance: staff-only по умолчанию, с возможностью расширения через RBAC.

### Не цели (MVP)
- Делать plan/provenance security boundary для выполнения (исполнение остаётся защищено RBAC на существующих endpoints).
- Хранить/показывать реальные секреты или значения “как есть”.
- Полностью стандартизировать все драйверы (MVP: schema-driven CLI + workflow).

## Модель данных (концептуально)
### Execution Plan
Plan — это безопасное описание того, что система намерена выполнить:
- `kind`: `ibcmd_cli | designer_cli | workflow`
- `title`/`summary` (опционально): человекочитаемое описание
- `argv_masked[]` (для CLI), `stdin_masked` (если применимо)
- `workflow_id` и `input_context_masked` (для workflow)
- `targets` (например: `per_database`, количество, перечисление ID баз — допустимо как не-секретные значения)
- `generated_at`, `generated_by` (опционально, для аудита)

### Binding Provenance
Provenance — список биндингов, каждый описывает:
- `target_ref`: куда подставляем (например `argv[3]`, `flag:--remote`, `workflow.input_context.target_database_ids`)
- `source_ref`: откуда берём (строго типизированный источник)
- `resolve_at`: `api` или `worker`
- `sensitive`: `true|false` (значения не храним; при `true` всегда редактируем value)
- `status`: `applied|skipped|unresolved` (MVP допускает `unresolved` для preview)
- `reason` (для skipped/unresolved): например `missing_source`, `blocked_by_allowlist`, `unsupported_for_command`

Источники (`source_ref`) задаём как ограниченный словарь, например:
- `request.params.<name>`
- `request.connection.<path>`
- `database.connection.<path>`
- `runtime_setting.ui.action_catalog.extensions.actions[<id>].executor.<path>`
- `driver_catalog.driver_schema.<path>`
- `driver_catalog.commands_by_id.<command_id>.params_by_name.<name>`
- `workflow_template.<workflow_id>.<path>` (например “ожидаемое поле”)
- `env.<name>` / `credentials_store.<name>` (всегда `sensitive=true`)

## Семантика / сборка plan
### CLI (schema-driven)
- Plan строится там же, где сейчас строится `argv[]/argv_masked[]`, и включает:
  - результат нормализации `argv` (например алиасы под реальный CLI),
  - список биндингов на основе источников:
    - driver options (`connection.*`),
    - command params (`params`),
    - `additional_args` (и конфликты),
    - runtime-only инъекции/переписывания (если есть) маркируются `resolve_at=worker`.

### Workflow
- Plan строится на этапе создания execution:
  - `workflow_id` + `input_context_masked`;
  - provenance для полей `input_context`:
    - target databases (из UI selection),
    - fixed params (из action catalog),
    - любые значения из env/secret store — как `sensitive=true` без хранения value.

## API / UI точки интеграции (MVP)
### Preview (для UI до запуска)
Нужен API, который возвращает plan + provenance **без создания операции**.
Использование:
- `/databases` drawer: staff делает preview перед подтверждением.
- `/settings/action-catalog`: staff делает preview для выбранного action.

Предпочтение (MVP): единый preview endpoint на стороне Orchestrator (path TBD), который принимает:
- `executor` (kind + driver/command_id или workflow_id),
- `mode/params/additional_args/stdin/fixed` (как в action catalog),
- `target_database_ids` (опционально; для drawer это известно),
- `connection` (опционально; может быть частично известно),
и возвращает `execution_plan` + `bindings[]`.

### Persisted plan (после запуска)
- При создании операции/воркфлоу-execution система сохраняет plan + bindings (без секретов) в объекте исполнения.
- В details (`/operations`, `/workflows/executions`) staff видит сохранённый plan и provenance.

### Runtime-only bindings (worker)
- Для биндингов с `resolve_at=worker` worker обязан вернуть `status`/`reason`.
- Orchestrator сохраняет эту информацию так, чтобы UI мог показать per-task детали (без секретов).

## Безопасность / доступы
- По умолчанию plan/provenance доступны только `staff`.
- В дальнейшем можно расширить через RBAC permission, например `view_execution_plan`, не меняя формат.
- В логах/ивентах запрещено хранить секреты:
  - plan содержит только `argv_masked` и masked workflow input;
  - provenance не содержит raw values.

## Открытые вопросы (для реализации)
- Точный формат `input_context_masked` для workflow (полное дерево vs только “интересные” поля).
- Где хранить persisted plan (отдельное поле vs `metadata`) и как версионировать (например `plan_version`).
- Унификация отображения plan в `/operations` vs `/workflows/executions` (общий компонент UI).

