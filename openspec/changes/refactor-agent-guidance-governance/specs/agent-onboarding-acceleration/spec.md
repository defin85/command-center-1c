## MODIFIED Requirements

### Requirement: Репозиторий MUST публиковать task routing matrix для типовых agent tasks

Система ДОЛЖНА (SHALL) иметь stable checked-in task routing asset для типовых task families.

Task routing matrix ДОЛЖЕН (SHALL):
- покрывать типовые task families как минимум для product/domain questions, frontend work, orchestrator work, go-services work, contracts/OpenSpec work и runtime-debug flows;
- указывать для каждой task family minimum-required docs, кодовые entry points, verification commands и релевантные machine-readable surfaces;
- явно различать обязательные first reads и conditional/deeper reads;
- указывать route-specific escalation points, после которых агенту уже нужен более широкий docs bundle, дополнительные skills или runtime verification;
- оставаться bounded reference asset, а не превращаться в исчерпывающий cookbook;
- быть discoverable из root onboarding guidance и canonical agent docs.

Task routing matrix НЕ ДОЛЖЕН (SHALL NOT):
- implicitly требовать один и тот же широкий onboarding bundle для любой задачи;
- подменять собой detailed runbook/spec docs там, где они уже существуют как stable routed references.

#### Scenario: Локальная задача использует minimum-required route вместо широкого onboarding bundle
- **GIVEN** агент получил локальную и достаточно ограниченную задачу в известной подсистеме
- **WHEN** он использует task routing matrix
- **THEN** он видит минимально достаточный набор docs, code entry points и checks для старта
- **AND** понимает, когда нужно расширить чтение, а когда можно сразу переходить к исполнению

