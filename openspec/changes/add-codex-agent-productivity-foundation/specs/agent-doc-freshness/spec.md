## ADDED Requirements

### Requirement: Authoritative agent docs MUST проходить machine-checkable freshness validation

Система ДОЛЖНА (SHALL) иметь machine-checkable freshness checks для authoritative agent-facing docs.

Freshness checks ДОЛЖНЫ (SHALL) как минимум валидировать:
- существование referenced files/paths;
- соответствие canonical tool versions их source of truth (`.tool-versions` или эквивалент);
- соответствие runtime/entrypoint/start/test references их machine-readable inventory;
- существование referenced scripts/commands/package scripts;
- отсутствие silent drift по важным портам, entry points и verification commands внутри authoritative agent docs.

Freshness checks НЕ ДОЛЖНЫ (SHALL NOT) ограничиваться только style lint; они ДОЛЖНЫ (SHALL) проверять фактическое соответствие checked-in guidance текущему репозиторию.

#### Scenario: Drift в authoritative doc блокирует validation
- **GIVEN** authoritative agent-facing doc ссылается на устаревшую команду, порт, версию или несуществующий path
- **WHEN** запускается doc freshness validation
- **THEN** validation завершается ошибкой
- **AND** диагностический вывод явно показывает, какой source-of-truth был нарушен

### Requirement: Non-authoritative agent docs MUST быть явно помечены

Система ДОЛЖНА (SHALL) явно различать authoritative, supplemental и legacy/non-authoritative agent-related docs.

Если historical doc layer остаётся в репозитории, он ДОЛЖЕН (SHALL):
- содержать явный статус, что он не является canonical onboarding surface;
- направлять к актуальному authoritative path;
- не выглядеть как равноправный современный source of truth.

#### Scenario: Historical onboarding doc не маскируется под canonical источник
- **GIVEN** в репозитории остаётся legacy onboarding-like document
- **WHEN** новый агент или разработчик открывает его
- **THEN** документ явно сообщает свой non-authoritative или legacy статус
- **AND** указывает актуальный canonical agent-facing path
