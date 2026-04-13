## ADDED Requirements

### Requirement: Factual monitoring workspace MUST use canonical frontend i18n and formatter boundaries

Система ДОЛЖНА (SHALL) рендерить operator-facing factual workspace на `/pools/factual` через canonical frontend i18n runtime, shell-owned effective locale и shared locale-aware formatter layer.

Этот contract ДОЛЖЕН (SHALL) покрывать как минимум:
- route page chrome и alert copy;
- detail surface, empty/error/status states и deep-link guidance;
- review reason/action labels и review modal copy;
- user-visible timestamps, quarter windows и аналогичные factual workspace summaries.

Factual workspace НЕ ДОЛЖЕН (SHALL NOT) завершать migration через hardcoded route-local English/Russian copy, route-local locale runtime или ad hoc timestamp/quarter replacement helpers как primary path.

Machine-readable factual payload vocabulary, review actions и source-profile metadata МОГУТ (MAY) оставаться неизменными; локализуется operator-facing presentation layer над ними.

#### Scenario: Reloaded factual detail keeps one effective locale

- **GIVEN** shell locale установлен в `ru` или `en`
- **AND** оператор открывает `/pools/factual` с выбранным pool и `detail=1`
- **WHEN** страница перезагружается или открывается по deep link
- **THEN** route header, alerts, detail title, empty/error states и user-visible formatting используют один и тот же effective locale
- **AND** пользователь не видит mixed-language split между shell navigation и factual workspace

#### Scenario: Review modal and labels inherit canonical factual locale semantics

- **GIVEN** оператор работает с review queue в factual workspace
- **WHEN** он открывает review action modal или запускает review action
- **THEN** review reason/action labels, modal copy, validation copy и user-visible formatting используют canonical i18n runtime и shared formatter layer
- **AND** route-owned helper modules не создают отдельный locale owner или route-local string registry как primary path
