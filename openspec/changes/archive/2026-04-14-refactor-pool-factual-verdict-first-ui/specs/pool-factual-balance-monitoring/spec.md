## ADDED Requirements

### Requirement: Factual workspace MUST surface operator verdict and aggregate pool movement before technical diagnostics

Система ДОЛЖНА (SHALL) для выбранного `pool + quarter` в `/pools/factual` показывать above the fold один operator-facing verdict, который даёт быстрый ответ, всё ли у factual workspace в порядке.

Этот primary summary ДОЛЖЕН (SHALL) как минимум включать:
- один итоговый status verdict для selected workspace context;
- одну основную причину текущего verdict;
- одно рекомендуемое следующее действие;
- prominently rendered aggregate `incoming_amount`, `outgoing_amount` и `open_balance`;
- derived completion ratio, если `incoming_amount` ненулевой.

Если route использует `MasterDetail` или другой selection/detail shell, система ДОЛЖНА (SHALL) дополнительно показывать в selection context compact per-pool health summary, достаточный чтобы отличить problematic pool от healthy pool без открытия каждого detail.
Selection-context health summary ДОЛЖЕН (SHALL) быть доступен без необходимости последовательно открывать detail каждого pool.
Если route использует explicit quarter context, selection summary и selected detail verdict ДОЛЖНЫ (SHALL) отражать один и тот же quarter context.

Technical diagnostics, включая `scope lineage`, per-checkpoint details, raw error codes и workflow/operation handoff links, МОГУТ (MAY) оставаться доступными, но НЕ ДОЛЖНЫ (SHALL NOT) предшествовать primary operator verdict и aggregate pool movement summary.

#### Scenario: Operator can identify the problematic pool from the selection pane

- **GIVEN** factual workspace показывает несколько pools в compact master pane
- **WHEN** часть pools healthy, а часть имеет failed/stale/backlog/review signals
- **THEN** каждая строка списка показывает compact health summary
- **AND** оператор может выбрать problematic pool без последовательного открытия каждого detail

#### Scenario: Selected pool shows verdict and aggregate movement before diagnostics

- **GIVEN** оператор открыл `/pools/factual` и выбрал конкретный pool
- **WHEN** detail pane загружается
- **THEN** пользователь сначала видит overall verdict и aggregate `incoming_amount`, `outgoing_amount`, `open_balance`
- **AND** может сразу понять, всё ли хорошо и сколько суммарно завели/вывели по пулу
- **AND** technical diagnostics остаются ниже как secondary explanation, а не как первый ответ интерфейса

#### Scenario: Explicit quarter context stays aligned between selection and detail

- **GIVEN** `/pools/factual` открыт с explicit `quarter_start`
- **WHEN** route показывает compact selection summary и оператор открывает detail выбранного pool
- **THEN** selection summary и selected detail verdict описывают один и тот же quarter context
- **AND** интерфейс не сравнивает pools по скрыто разным quarter contexts внутри одного route state
