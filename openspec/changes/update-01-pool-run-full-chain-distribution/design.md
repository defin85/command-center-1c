## Context
Текущий `pool run` execution path в `PoolDomainBackend` использует `execute_pool_runtime_step`, где шаги `distribution_calculation` и `reconciliation_report` работают в режиме summary-only.

Из-за этого в runtime-path отсутствует гарантированная связь между:
- активной версией topology (`PoolNodeVersion/PoolEdgeVersion` по периоду run),
- фактическим распределением суммы по цепочке,
- publication payload (`documents_by_database`), который уходит в `pool.publication_odata`.

При этом в кодовой базе уже есть готовые алгоритмические компоненты:
- `distribute_top_down` с инвариантом сохранения суммы и edge constraints;
- `run_bottom_up_import` с проверкой сходимости input->root.

Они пока не являются source-of-truth для runtime исполнения run.

## Goals
- Сделать runtime distribution artifacts каноническим source-of-truth для publication payload в create-run path.
- Гарантировать full-chain coverage и preservation суммы для активной topology версии в выбранный период.
- Блокировать publication fail-closed при любом нарушении инвариантов распределения.
- Сохранить существующий публичный pools facade API без обязательной миграции клиентов.

## Non-Goals
- Не менять RBAC auth/mapping semantics publication credentials.
- Не вводить новый публичный endpoint.
- Не менять модель хранения topology (узлы/рёбра) и UX topology editor в этом change.

## Decisions
### Decision 1: Runtime distribution artifact как единственный расчётный источник
`pool.distribution_calculation.*` ДОЛЖЕН (SHALL) вычислять и сохранять структурированный artifact (node totals, edge allocations, coverage metadata, balance metadata).

Дальнейшие шаги (`reconciliation`, формирование publication payload) используют только этот artifact как source-of-truth.

Минимальный обязательный контракт `distribution_artifact.v1`:
- `version = "distribution_artifact.v1"`;
- `topology_version_ref` (идентификатор активной версии topology для периода run);
- `node_totals[]` (stable `node_id`, amount, currency);
- `edge_allocations[]` (stable `edge_id`, amount, constraints digest);
- `coverage` (список covered/missing publish-target узлов);
- `balance` (`source_total`, `distributed_total`, `delta`, `tolerance`);
- `input_provenance` (ссылка на source input, без права переопределять расчёт).

### Decision 2: Подключение существующих алгоритмов вместо дублирования логики
- top-down path использует `distribute_top_down`;
- bottom-up path использует bottom-up aggregation/convergence на active topology.

Это минимизирует дублирование и закрывает разрыв между уже протестированными алгоритмами и runtime execution path.

### Decision 3: Reconciliation как hard gate перед publication
`pool.reconciliation_report` превращается в обязательный gate:
- при balance mismatch, coverage gap или недоопределённом distribution artifact выполнение publication блокируется;
- ошибка возвращается в machine-readable формате и проецируется в diagnostics.

### Decision 4: Publication payload формируется из distribution artifact
Для create-run path `pool_runtime_publication_payload.documents_by_database` формируется из рассчитанного распределения.

Raw `run_input` может храниться как provenance входа, но НЕ ДОЛЖЕН (SHALL NOT) быть authoritative источником итогового publication payload.

Решение по совместимости create-run: `run_input.documents_by_database` принимается только как `provenance-only` поле, сохраняется для аудита/диагностики и не участвует в формировании финального publication payload при наличии валидного `distribution_artifact.v1`.

Retry path сохраняет selective-subset контракт, но опирается на зафиксированное расчётное состояние run.

### Decision 5: Стабильная fail-closed taxonomy
Вводятся стабильные machine-readable коды для нарушений distribution invariants (например: баланс, coverage, invalid input/graph).

Коды проходят цепочку runtime -> execution diagnostics -> facade report/problem details без деградации в generic ошибки.

### Decision 6: Distribution artifact — upstream контракт для последующих change-ов
Этот change фиксирует `distribution_artifact` как отдельный integration contract (`distribution_artifact.v1`) и source-of-truth для распределения.

Дальнейшие слои:
- `add-02-pool-document-policy` используют этот artifact как вход для compile `document_plan_artifact`;
- `refactor-03-unify-platform-execution-runtime` используют оба artifact для атомарного workflow compiler.

Семантика document chains/invoice и platform execution observability в данном change не переопределяется.

## Alternatives Considered
### A1. Оставить текущий summary-only runtime и добавить только post-check в worker
Отклонено: проблема появляется до worker и не гарантирует согласованность publication payload с topology.

### A2. Валидировать только в API create-run, без runtime gate
Отклонено: не покрывает retry/runtime drift и не гарантирует инварианты на момент фактического исполнения шагов.

### A3. Немедленно вводить отдельный distribution service
Отклонено как избыточная сложность для текущего scope; достаточно подключить уже существующие модули.

## Risks / Trade-offs
- Риск: ужесточение инвариантов может увеличить число fail-closed run в существующих tenant данных.
  - Mitigation: явные diagnostics + операционный preflight/checklist перед включением в production.
- Риск: historical run с legacy payload может не содержать нужного artifact.
  - Mitigation: backward-compatible read-path для historical данных и постепенное применение gate для новых execution.
- Риск: рассинхрон contract semantics между orchestrator runtime и worker publication transport.
  - Mitigation: spec-first фиксация source-of-truth semantics + integration tests на end-to-end path.

## Migration Plan
1. Зафиксировать OpenSpec deltas для full-distribution invariants и publication payload source-of-truth.
2. Подключить алгоритмы в runtime distribution steps и сохранять canonical artifact.
3. Переключить reconciliation/publication payload на artifact.
4. Включить fail-closed gate и machine-readable diagnostics.
5. Зафиксировать `distribution_artifact.v1` как стабильный input-контракт для downstream change-ов.
6. Дополнить unit/integration/e2e тесты и пройти quality gates.

## Resolved Questions
- Для create-run выбран режим `provenance-only` для `run_input.documents_by_database`; режим полного reject в этом change не вводится, чтобы избежать breaking-change для клиентов.
