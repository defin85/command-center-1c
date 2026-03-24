## ADDED Requirements

### Requirement: Binding profile usage summary MUST использовать dedicated scoped read model
Система ДОЛЖНА (SHALL) предоставлять для `/pools/binding-profiles` dedicated backend read-model, scoped к выбранному `binding_profile_id`, чтобы operator-facing usage summary не зависел от broad tenant-wide pool catalog hydration.

Scoped usage projection ДОЛЖНА (SHALL):
- возвращать только attachment-ы, pinned на выбранный reusable profile;
- возвращать attachment count и summary по revision-ам, которые сейчас используются;
- включать достаточно pool/binding context для явного handoff в `/pools/catalog`;
- не требовать от shipped frontend path загрузки полного списка pools и client-side фильтрации нерелевантных attachment-ов.

UI МОЖЕТ (MAY) lazy-load usage по требованию оператора, но default shipped path НЕ ДОЛЖЕН (SHALL NOT) вычислять usage summary через broad organization pool list scan.

#### Scenario: Profile detail получает scoped usage без tenant-wide pool scan
- **GIVEN** оператор открыл detail reusable profile на `/pools/binding-profiles`
- **WHEN** detail pane загружает usage summary
- **THEN** backend возвращает только attachment-ы, pinned на выбранный profile, вместе с counts и revision summary
- **AND** UI может открыть соответствующий pool attachment workspace без отдельной broad pool catalog hydration

#### Scenario: Нерелевантные pools не участвуют в profile usage response
- **GIVEN** tenant содержит множество pools, не использующих выбранный reusable profile
- **WHEN** оператор открывает usage summary для этого profile
- **THEN** shipped path остаётся scoped к выбранному `binding_profile_id`
- **AND** нерелевантные pools не загружаются только ради client-side aggregation usage summary
