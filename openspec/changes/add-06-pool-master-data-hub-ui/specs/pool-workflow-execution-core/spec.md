## ADDED Requirements
### Requirement: Pools facade MUST возвращать стабильный `master_data_gate` read-model для run inspection
Система ДОЛЖНА (SHALL) возвращать в `GET /api/v2/pools/runs/{run_id}` и `GET /api/v2/pools/runs/{run_id}/report` стабилизированный блок `master_data_gate`, достаточный для operator-facing диагностики.

Блок `master_data_gate` ДОЛЖЕН (SHALL) находиться внутри `run` payload (`run.master_data_gate`) в обоих endpoint-ах.

Минимальный состав блока:
- `status` (`completed|failed|skipped`);
- `mode` (`resolve_upsert`);
- `targets_count`;
- `bindings_count`;
- `error_code` (optional);
- `detail` (optional);
- `diagnostic` (optional structured object).

Для historical run-ов без шага `master_data_gate` система МОЖЕТ (MAY) возвращать `null`.

#### Scenario: Успешный run возвращает summary master-data gate
- **GIVEN** workflow execution выполнил шаг `pool.master_data_gate` успешно
- **WHEN** клиент запрашивает run details/report через facade
- **THEN** ответ содержит `master_data_gate.status=completed`
- **AND** содержит `targets_count` и `bindings_count` из execution context

#### Scenario: Fail-closed gate возвращает structured diagnostic
- **GIVEN** `pool.master_data_gate` завершился ошибкой
- **WHEN** клиент запрашивает run details/report через facade
- **THEN** ответ содержит `master_data_gate.status=failed` и machine-readable `error_code`
- **AND** поле `diagnostic` содержит structured контекст для remediation

#### Scenario: Неконсистентный gate feature flag блокирует публикацию fail-closed
- **GIVEN** effective runtime value `pools.master_data.gate_enabled` неконсистентен и не приводится к bool
- **WHEN** workflow выполняет `pool.master_data_gate`
- **THEN** шаг завершается fail-closed с machine-readable `error_code=MASTER_DATA_GATE_CONFIG_INVALID`
- **AND** side effects публикации в OData не выполняются
