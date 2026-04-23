## MODIFIED Requirements
### Requirement: Machine-readable traces/errors/actions MUST быть достаточным minimal contract для default agent monitoring path

Система ДОЛЖНА (SHALL) считать достаточным minimal contract для default agent monitoring path следующий набор сигналов:
- semantic UI action events, включая route-changing operator intent с устойчивыми `surface_id` / `control_id`;
- route/session/release/build metadata;
- route-write attribution (`route_writer_owner`, `write_reason`, `navigation_mode`, bounded `param_diff`, `caused_by_ui_action_id` при наличии);
- runtime/render/network error events;
- bounded route loop/oscillation diagnostics;
- correlated identifiers `trace_id`, `request_id`, `ui_action_id`;
- canonical backend trace lookup metadata.

Visual replay, DOM/session recording и video-like playback НЕ ДОЛЖНЫ (SHALL NOT) быть обязательным условием для работы default agent monitoring path.

#### Scenario: Агент диагностирует route loop без screen replay
- **GIVEN** на operator-facing route возникает oscillation между конкурирующими route states
- **WHEN** агент читает dev bundle или ordered prod/dev timeline через canonical observability path
- **THEN** он видит последний explicit route-changing intent, attributed route writes и machine-readable `route.loop_warning`
- **AND** он может отличить operator action от self-generated route churn внутри route-owned shell
- **AND** отсутствие session replay не блокирует базовую диагностику инцидента
