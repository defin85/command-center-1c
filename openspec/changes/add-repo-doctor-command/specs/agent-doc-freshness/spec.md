## MODIFIED Requirements

### Requirement: Authoritative agent docs MUST проходить machine-checkable freshness validation

Система ДОЛЖНА (SHALL) иметь machine-checkable freshness checks для authoritative agent-facing docs.

Freshness checks ДОЛЖНЫ (SHALL) как минимум валидировать:
- существование referenced files/paths;
- соответствие canonical tool versions их source of truth (`.tool-versions` или эквивалент);
- соответствие runtime/entrypoint/start/test references их machine-readable inventory;
- существование referenced scripts/commands/package scripts;
- discoverability и executable wiring repository doctor entrypoint (`make doctor` и checked-in wrapper);
- соответствие documented doctor profiles/check contract checked-in doctor implementation;
- отсутствие silent drift по важным портам, entry points, doctor command, verification commands и runtime mapping внутри authoritative agent docs.

Freshness checks НЕ ДОЛЖНЫ (SHALL NOT) ограничиваться только style lint; они ДОЛЖНЫ (SHALL) проверять фактическое соответствие checked-in guidance текущему репозиторию.

#### Scenario: Drift в authoritative doc блокирует validation
- **GIVEN** authoritative agent-facing doc ссылается на устаревшую команду, порт, версию или несуществующий path
- **WHEN** запускается doc freshness validation
- **THEN** validation завершается ошибкой
- **AND** диагностический вывод явно показывает, какой source-of-truth был нарушен

#### Scenario: Doctor command drift блокирует validation
- **GIVEN** authoritative agent-facing docs advertise `make doctor` or a doctor profile
- **WHEN** checked-in `Makefile`, doctor wrapper, or doctor implementation no longer provides that command/profile
- **THEN** freshness validation fails
- **AND** diagnostic output points to the mismatched doctor command or profile
