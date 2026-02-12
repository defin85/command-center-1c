## Context
После cutover `OperationTemplate` удалён из runtime-критичных путей, однако workflow operation-node по контракту всё ещё опирается на `template_id` (alias), а валидация `OperationExposure` не гарантирует полный runtime-контракт payload до этапа исполнения.

Это приводит к двум системным проблемам:
- отсутствует детерминизм при изменении exposure между моментом сохранения workflow и запуском;
- часть ошибок формы payload всплывает поздно (на runtime execution), а не на write/publish.

## Goals / Non-Goals
- Goals:
  - сделать `OperationExposure` явным execution binding в workflow;
  - обеспечить deterministic режим исполнения для критичных workflow;
  - сделать явным data-flow между operation-нодами через контракт `io` вместо неявной implicit передачи всего context;
  - перенести проверку runtime-контракта exposure на write/publish phase;
  - повысить usability и прозрачность UI `/templates` и modal editor при работе со связкой `OperationExposure -> OperationDefinition`;
  - сохранить backward compatibility для текущих клиентов с `template_id`.
- Non-Goals:
  - удалить `template_id` из API в этом change;
  - вводить новый major API version;
  - менять business-semantics operation types.

## Decisions
- Decision: Ввести `operation_ref` как новый контракт workflow operation-node.
  - Shape:
    - `alias: string` (обязательный),
    - `binding_mode: "alias_latest" | "pinned_exposure"` (обязательный),
    - `template_exposure_id?: uuid` (для pinned),
    - `template_exposure_revision?: integer` (для drift-check).
  - `template_id` остаётся как backward-compatible mirror.

- Decision: Поддержать два режима резолва в runtime.
  - `alias_latest`: резолв по `surface=template + alias` (текущее поведение).
  - `pinned_exposure`: резолв по `template_exposure_id` + проверка `template_exposure_revision`; при mismatch — fail-closed `TEMPLATE_DRIFT`.

- Decision: Ввести monotonic `exposure_revision`.
  - Увеличивается при семантически значимом изменении exposure/definition связи, влияющей на execution payload.
  - Выдаётся в list/detail API и прокидывается в execution metadata.

- Decision: Усилить validation pipeline для template surface.
  - Проверки обязательны и единообразны в `validate`, `upsert`, `publish`, `sync-from-registry`.
  - Минимальный contract:
    - `operation_type`: non-empty string и поддерживается backend registry;
    - `template_data`: JSON object.
  - Нарушения блокируют `published` статус.

- Decision: Расширить worker wire contract.
  - Metadata включает `template_id`, `template_exposure_id`, `template_exposure_revision`.
  - Worker/internal API поддерживает resolve по `template_exposure_id` (при pinned режиме), оставаясь совместимым с `template_id`.

- Decision: Ввести runtime setting для поэтапного ужесточения deterministic режима.
  - Ключ: `workflows.operation_binding.enforce_pinned`.
  - Значение по умолчанию: `false` (совместимость).
  - При `true` новые и обновляемые workflow operation-node должны использовать `binding_mode="pinned_exposure"`.
  - Runtime при `enforce_pinned=true` отклоняет alias-only execution fail-closed кодом (например, `TEMPLATE_PIN_REQUIRED`).

- Decision: Выбрать стратегию миграции без обязательного one-time массового rewrite DAG.
  - Базовый путь: lazy upgrade при сохранении workflow (`template_id -> operation_ref`).
  - Read path остаётся backward-compatible для существующих workflow с `template_id`.
  - Для операционной подготовки добавляется idempotent management command backfill (с `--dry-run`) как опциональный инструмент ускоренной миграции.

- Decision: Ввести explicit data-flow contract `io` для operation-node.
  - Shape:
    - `input_mapping: { target_path -> source_path }`,
    - `output_mapping: { target_path -> source_path }`,
    - `mode: "implicit_legacy" | "explicit_strict"`.
  - `explicit_strict`:
    - рендер шаблона получает только данные из `input_mapping`,
    - при отсутствии обязательного source-path выполнение отклоняется fail-closed.
  - `implicit_legacy`:
    - сохраняет текущую implicit context-передачу для backward compatibility.

- Decision: Рефакторить `/templates` list + modal editor под UX-принципы прозрачного binding.
  - List показывает ключевые provenance-поля: `template_id/alias`, `executor.kind`, `executor.command_id`, `template_exposure_id`, `template_exposure_revision`, publish status.
  - Modal editor строится как guided flow с явным source-of-truth для `OperationDefinition` и блоком «что будет выполнено» (preview execution payload).
  - Ошибки `validation_errors` маппятся на поля формы и объясняют причины блокировки publish/validate.

## Alternatives Considered
- Альтернатива A: Оставить только alias и усилить validation без pinned режима.
  - Плюс: меньше изменений.
  - Минус: не решает alias drift и недетерминизм.

- Альтернатива B: Ввести immutable versioned exposure entities (новая таблица версий).
  - Плюс: сильная воспроизводимость.
  - Минус: существенно выше миграционная и операционная сложность.

- Выбор: гибрид `operation_ref + exposure_revision` как минимально достаточный шаг.
  - Детерминизм появляется без полной перестройки persistence-модели.
  - Совместимость с текущим API сохраняется.

## Risks / Trade-offs
- Риск: переходный dual-контракт (`template_id` и `operation_ref`) усложнит код и тесты.
  - Mitigation: чёткий deprecation plan и telemetry по использованию legacy поля.

- Риск: неправильное инкрементирование `exposure_revision` может давать ложные drift-ошибки или пропуски drift.
  - Mitigation: отдельные unit tests на policy обновления revision и contract tests.

- Риск: неполное обновление OpenAPI/generated clients создаст рассинхрон фронта/бэка.
  - Mitigation: обязательный gating через contract checks и регенерацию клиентов в одном change.

- Риск: добавление provenance-деталей перегрузит modal техническими полями.
  - Mitigation: progressive disclosure (основные поля по умолчанию + расширенные детали по запросу), сохранение короткого happy-path.

- Риск: explicit mapping увеличит объём конфигурации operation-ноды.
  - Mitigation: визуальный редактор mapping в Property Editor + mode `implicit_legacy` для плавной миграции.

## Migration Plan
1. Добавить `operation_ref` и `exposure_revision` в schema/models/API (без удаления `template_id`).
2. Реализовать runtime поддержку обоих контрактов (`template_id` legacy + `operation_ref`).
3. Включить strict validation на write/publish/sync path.
4. Обновить enqueue/details metadata и worker model.
5. Обновить frontend workflow designer/editor для записи `operation_ref`.
6. Обновить `/templates` list + modal editor для прозрачного показа binding/provenance.
7. Добавить `io` contract в schema/API/runtime и UI editor operation-ноды.
8. Выполнить compatibility rollout:
   - старые workflow продолжают работать через `template_id`,
   - новые/пересохранённые workflow используют `operation_ref`.

## Resolved Questions
- Принудительный pinned режим вводится через runtime setting `workflows.operation_binding.enforce_pinned` (default `false`).
- Массовый one-time rewrite DAG не делается обязательным; используется lazy upgrade on save + optional backfill command для controlled rollout.
