## 1. Contract Baseline (architecture-first)
- [ ] 1.1 Зафиксировать canonical contract `publication_auth` (`strategy`, `actor_username`, `source`) для workflow runtime path.  
  `Quality gate`: контракт согласован между orchestrator/worker owners.
- [ ] 1.2 Зафиксировать internal credentials request contract (`created_by`, `ib_auth_strategy`) и machine-readable ошибки (`ODATA_MAPPING_NOT_CONFIGURED`, `ODATA_MAPPING_AMBIGUOUS`, `ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`).  
  `Depends on`: 1.1. `Quality gate`: contract review + backward compatibility note.
- [ ] 1.3 Обновить OpenSpec deltas (`pool-odata-publication`, `pool-workflow-execution-core`, `worker-odata-transport-core`) под mapping-only auth и fail-closed semantics.  
  `Depends on`: 1.2.

## 2. Orchestrator: Publication Auth Context
- [ ] 2.1 Добавить формирование `publication_auth` в workflow input context для pool run (strategy + actor_username + source).  
  `Depends on`: 1.1.
- [ ] 2.2 Для safe-команд (`confirm_publication`, `retry_publication`) гарантировать actor provenance от фактического инициатора команды, а не от generic `workflow_engine`.  
  `Depends on`: 2.1. `Quality gate`: deterministic actor propagation tests.
- [ ] 2.3 Обновить runtime serialization/bridge path, чтобы `publication_auth` не терялся до worker node.  
  `Depends on`: 2.2.

## 3. Worker: Context-aware Credentials Lookup
- [ ] 3.1 Прокинуть `publication_auth` из workflow execution context в `OperationRequest`/node runtime contract.  
  `Depends on`: 2.3.
- [ ] 3.2 В `pool.publication_odata` использовать `credentials.WithRequestedBy(...)` и `credentials.WithIbAuthStrategy(...)` при fetch credentials.  
  `Depends on`: 3.1.
- [ ] 3.3 Добавить раннюю fail-closed валидацию `publication_auth` до OData transport side effects.  
  `Depends on`: 3.2.

## 4. Credentials Resolver Hardening
- [ ] 4.1 Обновить orchestrator handler `get-database-credentials` для mapping-only resolution OData auth в publication use-case.  
  `Depends on`: 3.2.
- [ ] 4.2 Устранить недетерминированный lookup (`.first()`), введя однозначные constraints/валидацию для actor/service mapping и явные конфликт-ошибки.  
  `Depends on`: 4.1.
- [ ] 4.3 Добавить migration/backfill checks и preflight coverage report для окружений перед cutover на mapping-only auth.  
  `Depends on`: 4.2.

## 5. UX Alignment
- [ ] 5.1 Уточнить UI copy/поведение: для pool publication OData credentials задаются в `/rbac` (Infobase Users), а не в legacy database credentials modal.  
  `Depends on`: 4.1.
- [ ] 5.2 Добавить раннюю операторскую валидацию/подсказки по missing mapping (до запуска или на раннем шаге run) с remediation route в `/rbac`.  
  `Depends on`: 5.1.

## 6. Observability and Operability
- [ ] 6.1 Добавить telemetry/logging labels для outcomes resolution (`actor_success`, `service_success`, `missing_mapping`, `ambiguous_mapping`, `invalid_auth_context`).  
  `Depends on`: 4.2.
- [ ] 6.2 Подготовить rollout checklist и rollback drill для staging/prod с mandatory operator sign-off.  
  `Depends on`: 4.3, 5.2, 6.1.

## 7. Validation and Release Gates
- [ ] 7.1 Backend tests: actor/service resolution, missing mapping fail-closed, ambiguous mapping fail-closed, invalid `publication_auth` fail-closed.
- [ ] 7.2 Worker tests: propagation `publication_auth` -> credentials request (`created_by`, `ib_auth_strategy`) и отсутствие legacy fallback.
- [ ] 7.3 Integration tests: e2e pool run publication с `/rbac` mapping (actor success, service success, missing/ambiguous mapping failure).
- [ ] 7.4 Contract checks: `openspec validate update-pool-publication-odata-auth-mapping --strict --no-interactive` + contract drift checks.
- [ ] 7.5 Staging rehearsal + prod go/no-go: обязательный operator sign-off задокументирован и приложен к release evidence.
