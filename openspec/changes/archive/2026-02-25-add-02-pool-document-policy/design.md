## Context
Текущий execution path pool публикации принимает payload в форме `entity_name + documents_by_database`, что не даёт оператору управлять:
- набором документов на конкретном ребре;
- связями документов в цепочке;
- маппингом реквизитов и табличных частей по tenant-варианту.

Для сценариев с `Реализация/Поступление + соответствующая СчетФактура` это приводит к hardcode в backend и плохо масштабируется.

## Goals / Non-Goals
- Goals:
  - дать оператору декларативный, versioned способ конфигурировать документы на рёбрах;
  - сохранить separation: domain policy отдельно от execution orchestration;
  - обеспечить deterministic compile в runtime и fail-closed поведение при ошибках policy.
- Non-Goals:
  - не делать Turing-complete DSL или workflow scripting;
  - не менять auth/mapping security модель публикации;
  - не делать полноценный low-code конструктор всех документов 1С.

## Decisions
### Decision 1: Policy как domain-data, а не execution-logic
`document_policy` хранится как доменная конфигурация (основной вариант: `PoolEdgeVersion.metadata.document_policy`), а runtime только интерпретирует policy и строит execution artifact.

Это сохраняет разделение ответственности:
- domain layer: что публиковать и как заполнять;
- execution layer: когда и в каком порядке исполнять, ретраить и фиксировать статус.

### Decision 2: Versioned schema `document_policy.v1`
Policy фиксируется как versioned schema с минимальными сущностями:
- `chains[]` (ordered steps),
- `documents[]` внутри chain,
- `entity_name`,
- `field_mapping`,
- `table_parts_mapping`,
- `link_to`/`link_rules`,
- `invoice_mode` (`optional|required`) для связанных счёт-фактур.

Явная versioning стратегия нужна для безопасной эволюции контракта и backward compatibility.

### Decision 3: Runtime compile в `document_plan_artifact`
До publication runtime формирует детерминированный `document_plan_artifact` на основе:
- активной topology версии за период run;
- distribution artifact (source-of-truth по суммам/coverage);
- document-policy.

`document_plan_artifact` становится единственным источником для create path публикации и retry.

### Decision 4: Publication contract для document chains
Publication payload расширяется до per-document chain semantics (несколько документов разных `entity_name` в рамках одной target database) с сохранением backward compatibility для legacy single-entity payload.

Обязательная связанная счёт-фактура реализуется policy-правилом (`invoice_mode=required`) и проверяется fail-closed до side effects.

### Decision 5: Fail-closed taxonomy
Ошибки policy и chain-компиляции не деградируют в generic сообщения.
Вводится стабильный набор machine-readable кодов (например):
- `POOL_DOCUMENT_POLICY_INVALID`
- `POOL_DOCUMENT_POLICY_CHAIN_INVALID`
- `POOL_DOCUMENT_POLICY_MAPPING_INVALID`
- `POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE`

Коды проходят цепочку runtime -> diagnostics -> facade/API.

### Decision 6: Document plan artifact как промежуточный контракт между distribution и execution runtime
`document_plan_artifact` фиксируется как отдельный versioned контракт (`document_plan_artifact.v1`):
- вход: `distribution_artifact.v1` + active topology + `document_policy.v1`;
- выход: детализированный план document chains, пригодный для atomic workflow compile.

Минимальный обязательный контракт `document_plan_artifact.v1`:
- `version = "document_plan_artifact.v1"`;
- `run_id`;
- `distribution_artifact_ref` (id/version/checksum);
- `topology_version_ref`;
- `policy_refs[]` (привязка к edge и версии policy);
- `targets[]` с ordered `chains[]` и ordered `documents[]` в каждой цепочке;
- per-document поля: `entity_name`, `document_role`, `field_mapping`, `table_parts_mapping`, `link_rules`, `invoice_mode`, `idempotency_key`;
- `compile_summary` (warnings/errors digest, timestamp).

Этот change не вводит platform-level execution orchestration; downstream исполнение атомарных шагов принадлежит `refactor-03-unify-platform-execution-runtime`.

### Decision 7: Topology metadata contract обязателен на write/read path
Topology mutating path валидирует `edge.metadata.document_policy` до persistence (fail-closed), а topology/graph read-path всегда возвращает `node.metadata` и `edge.metadata` (включая `edge.metadata.document_policy`) без потери данных между round-trips.

## Alternatives Considered
### A1. Хранить policy только в `run_input`
Отклонено: плохо переиспользуется между run-ами и повышает риск drift/дубликатов конфигурации.

### A2. Жёстко зашить пары документов в backend
Отклонено: не масштабируется по tenant-вариантам и противоречит требованию пользовательской кастомизации.

### A3. Вынести всё в отдельный workflow-DSL
Отклонено как избыточная сложность для текущего scope; достаточно ограниченного declarative policy-контракта.

## Risks / Trade-offs
- Риск перегруженной конфигурации policy для оператора.
  - Mitigation: ограниченный `v1` schema + preflight + preview.
- Риск несовместимости разных 1С-конфигураций по документам/полям.
  - Mitigation: whitelist supported entities + явные fail-closed коды.
- Риск конфликтов с in-flight change `update-01-pool-run-full-chain-distribution`.
  - Mitigation: явная зависимость от distribution artifact и staged delivery.

## Migration Plan
1. Зафиксировать OpenSpec контракты `document_policy` + связанные runtime/publication требования.
2. Привязать compile вход к upstream `distribution_artifact.v1`.
3. Добавить topology metadata read/write + validation для policy.
4. Добавить runtime compile `document_plan_artifact.v1`.
5. Добавить publication support для document chains и required invoice rules.
6. Обновить retry и diagnostics path на работу от persisted artifact.
7. Зафиксировать downstream handoff контракта для atomic workflow compile в `refactor-03-unify-platform-execution-runtime`.
8. Прогнать contract/tests/rollout preflight.

## Resolved Questions
- Отдельный catalog обязательных полей в `v1` не вводится; применяется fail-closed whitelist/runtime validation на стороне compile/publication.
- `invoice_mode=required` применяется только при явном указании в policy; implicit defaults для `sale/purchase` в этом change не вводятся.
