## ADDED Requirements

### Requirement: Eligible `catalog-detail` routes MAY expose operator-selectable workspace presentation modes

Система ДОЛЖНА (SHALL) разрешать только тем routes, которые явно помечены как eligible в governance inventory, поддерживать operator-selectable presentation modes `auto`, `split` и `drawer`.

Переключение presentation mode НЕ ДОЛЖНО (SHALL NOT) менять route family, selected entity contract или domain navigation semantics совместимого route.

#### Scenario: Supported route переключается между split и drawer без потери selected context

- **GIVEN** route `/databases` объявляет supported presentation modes `auto`, `split` и `drawer`
- **AND** оператор уже выбрал конкретную базу и открыл её detail context
- **WHEN** оператор переключает presentation mode с `split` на `drawer` на wide viewport
- **THEN** выбранная база и detail context сохраняются
- **AND** route остаётся тем же operator workspace, а не превращается в другой `workspaceKind`
- **AND** domain actions продолжают открываться через те же canonical secondary surfaces

### Requirement: Effective presentation mode MUST follow explicit precedence and responsive fallback

Система ДОЛЖНА (SHALL) вычислять effective presentation mode в следующем порядке:
1. per-route operator override;
2. global operator default;
3. route default;
4. responsive fallback.

На narrow viewport система ДОЛЖНА (SHALL) применять mobile-safe detail fallback независимо от сохранённой desktop preference.

#### Scenario: Per-route override имеет приоритет над global default

- **GIVEN** оператор сохранил global default `drawer`
- **AND** для route `/decisions` сохранён per-route override `split`
- **WHEN** оператор открывает `/decisions` на wide viewport
- **THEN** effective mode для `/decisions` равен `split`
- **AND** другие compatible routes без собственного override продолжают использовать global default `drawer`

#### Scenario: Narrow viewport игнорирует desktop split preference

- **GIVEN** оператор сохранил effective desktop mode `split` для compatible route
- **WHEN** тот же route открывается на narrow viewport
- **THEN** detail открывается через canonical mobile-safe fallback
- **AND** page-wide horizontal overflow не становится обязательным primary interaction path

### Requirement: Supported presentation preferences MUST persist across reload for the same operator context

Система ДОЛЖНА (SHALL) сохранять global default и per-route operator overrides так, чтобы supported routes восстанавливали выбранный presentation mode после reload.

Механизм persistence МОЖЕТ (MAY) быть local-first или server-backed, но user-visible contract восстановления выбора после reload ДОЛЖЕН (SHALL) соблюдаться.

#### Scenario: Reload восстанавливает сохранённый route override

- **GIVEN** оператор сохранил per-route override `drawer` для compatible route
- **WHEN** он перезагружает страницу или возвращается к route позже
- **THEN** route восстанавливает тот же presentation mode
- **AND** оператору не требуется повторно включать нужный layout вручную

### Requirement: Unsupported routes MUST ignore incompatible presentation preferences

Система ДОЛЖНА (SHALL) игнорировать global или route-local presentation preferences на routes, которые не объявили совместимость с presentation modes.

Такие preferences НЕ ДОЛЖНЫ (SHALL NOT) менять `workspaceKind`, primary navigation model или ownership secondary surfaces несовместимого route.

#### Scenario: `catalog-workspace` route не меняет family под действием global drawer default

- **GIVEN** оператор сохранил global default `drawer`
- **AND** route `/artifacts` не объявил compatible presentation modes
- **WHEN** оператор открывает `/artifacts`
- **THEN** route сохраняет canonical `catalog-workspace` composition
- **AND** existing secondary drawer contract продолжает работать без внедрения split detail pane
- **AND** unsupported preference не создаёт ошибку или broken empty state
