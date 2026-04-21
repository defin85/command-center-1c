## ADDED Requirements
### Requirement: UI validation runtime MUST use reproducible performance evidence instead of single-run noise
Система ДОЛЖНА (SHALL) предоставлять repo-owned measurement workflow для полного frontend UI validation contour, который позволяет сравнивать runtime по воспроизводимому baseline, а не по одному случайному noisy run.

Workflow ДОЛЖЕН (SHALL) как минимум:
- разделять Vitest и browser-level measurements;
- фиксировать wall-clock и доступный component breakdown;
- поддерживать bounded repeated sampling или equivalent summary, достаточный для review perf claims.

#### Scenario: Performance claim is backed by repeated baseline evidence
- **GIVEN** change заявляет improvement или regression UI validation runtime
- **WHEN** команда собирает acceptance evidence
- **THEN** она использует repo-owned measurement workflow, а не один произвольный ручной прогон
- **AND** evidence показывает отдельные результаты для полного Vitest и browser UI gate

#### Scenario: Single noisy full run is not treated as authoritative regression by default
- **GIVEN** один full UI run резко расходится с недавним стабильным baseline
- **WHEN** у команды нет repeated samples или явного объяснения инфраструктурного фактора
- **THEN** такой run НЕ ДОЛЖЕН (SHALL NOT) считаться достаточным основанием для окончательного perf вывода
- **AND** measurement workflow требует повторной выборки или зафиксированного diagnostic explanation

### Requirement: Browser UI platform contract MUST be decomposed into explicit runtime shards
Система ДОЛЖНА (SHALL) хранить browser-level UI platform contract coverage в explicit checked-in shard topology вместо single-file monolith, если canonical browser gate становится трудно профилировать, review-ить или локально итерировать.

Каждый browser contract test file ДОЛЖЕН (SHALL) принадлежать ровно одному shard family, чтобы full browser gate не приводил к скрытому drop или duplicate execution.

#### Scenario: Canonical browser gate runs all shards exactly once
- **GIVEN** browser UI contract split по нескольким checked-in shard files
- **WHEN** разработчик или CI запускает canonical `npm run test:browser:ui-platform`
- **THEN** все обязательные browser contract shards исполняются как часть полного gate
- **AND** ни один shard не теряется и не исполняется повторно через другой script path

#### Scenario: Focused browser rerun uses reviewable shard boundary
- **GIVEN** разработчик меняет ограниченную route/contract family
- **WHEN** он запускает repo-owned focused browser command
- **THEN** запускается только релевантный shard set
- **AND** shard boundary выражен checked-in files/scripts, которые можно review-ить и документировать

### Requirement: Full UI validation gate MUST remain blocking while using explicit runtime topology
Система ДОЛЖНА (SHALL) сохранять blocking semantics полного UI validation gate после введения measurement workflow и browser shard topology.

Focused commands, measurement scripts и shard-level reruns НЕ ДОЛЖНЫ (SHALL NOT) заменять canonical full gate как source of truth для landing acceptance.

#### Scenario: Full gate remains mandatory after topology refactor
- **GIVEN** репозиторий уже использует repo-owned measurement commands и browser shards
- **WHEN** изменение готовится к handoff или landing
- **THEN** canonical full UI gate всё ещё выполняет полный обязательный frontend/browser surface
- **AND** change не считается завершённым при падении любой обязательной части full gate

#### Scenario: Docs and guard checks stay aligned with runtime topology
- **GIVEN** package scripts, Playwright topology и verification docs являются checked-in source of truth
- **WHEN** в runtime topology появляется drift между scripts, docs и guard tests
- **THEN** validation surface сообщает явную причину несоответствия
- **AND** команда не может silently сменить canonical UI validation path без обновления этих surfaces
