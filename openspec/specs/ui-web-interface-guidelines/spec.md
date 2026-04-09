# ui-web-interface-guidelines Specification

## Purpose
TBD - created by archiving change update-frontend-ui-ux-a11y. Update Purpose after archive.
## Requirements
### Requirement: Icon-only элементы управления имеют aria-label
Система ДОЛЖНА (SHALL) обеспечивать, что все icon-only кнопки (без видимого текста) имеют `aria-label` с понятным действием.

#### Scenario: Иконка действия в таблице доступна для скринридера
- **GIVEN** в таблице есть icon-only кнопка (например cancel, details, open)
- **WHEN** пользователь взаимодействует со страницей скринридером
- **THEN** control имеет `aria-label`, описывающий действие

### Requirement: Интерактивные элементы доступны с клавиатуры
Система ДОЛЖНА (SHALL) обеспечивать, что любой интерактивный элемент:
- является семантическим `<button>/<a>` или
- имеет `role`, `tabIndex` и keyboard handlers (Enter/Space).

#### Scenario: Trigger поповера фокусируем и управляется Enter/Space
- **GIVEN** popover/tooltip открывается по клику на trigger
- **WHEN** пользователь использует только клавиатуру
- **THEN** trigger доступен через Tab и открывается по Enter/Space

### Requirement: Формы и фильтры имеют label или aria-label
Система ДОЛЖНА (SHALL) обеспечивать, что `Input`, `Select` и прочие form controls имеют связанный label (через `Form.Item label`/`htmlFor`) или `aria-label`.

Placeholder-only имя НЕ ДОЛЖНО (SHALL NOT) считаться достаточным accessible name для shell-level selector, route-level filter или table-toolbar control, если после выбора значения пользователь теряет явное имя поля.

#### Scenario: Фильтры операций имеют доступные имена
- **GIVEN** на странице есть фильтры операций по ID/Workflow/Node
- **WHEN** пользователь использует скринридер
- **THEN** каждый фильтр имеет доступное имя (label или `aria-label`)

#### Scenario: Shell selector сохраняет понятное имя после выбора значения
- **GIVEN** в общем shell есть selector tenant context или другой shared route control
- **WHEN** пользователь уже выбрал значение и возвращается к контролу с клавиатуры или скринридером
- **THEN** control сохраняет устойчивое доступное имя
- **AND** placeholder не является единственным способом понять назначение поля

### Requirement: Типографика использует символ многоточия
Система ДОЛЖНА (SHALL) использовать `…` вместо `...` в пользовательском UI тексте (loading/empty states/truncation).

#### Scenario: Loading/empty states отображают корректное многоточие
- **GIVEN** UI показывает загрузку или пустое состояние
- **WHEN** текст содержит многоточие
- **THEN** используется `…`, а не `...`

### Requirement: Основной контент имеет понятную навигацию
Система ДОЛЖНА (SHALL) предоставлять пользователю способ быстро перейти к основному контенту (skip link) и иметь семантический контейнер основного контента.

#### Scenario: Пользователь может пропустить навигацию
- **GIVEN** пользователь навигирует с клавиатуры
- **WHEN** он попадает в начало страницы
- **THEN** доступна ссылка "Skip to content" (или эквивалент), переводящая фокус в основной контент

### Requirement: Видимый текст interactive control MUST совпадать с accessible name
Система ДОЛЖНА (SHALL) обеспечивать, что interactive element с видимым текстовым label имеет accessible name, включающий тот же пользовательски видимый label, а не unrelated internal wording.

Это особенно относится к shared shell status controls, buttons и links, которые пользователь может называть по видимому тексту при работе со screen reader, voice control или accessibility tooling.

#### Scenario: Stream status control имеет совпадающий visible label и accessible name
- **GIVEN** в shared shell есть control с видимым текстом `Stream: Connected` или эквивалентным состоянием
- **WHEN** пользователь обращается к нему через assistive technology
- **THEN** accessible name включает тот же видимый label
- **AND** control не использует unrelated internal name, который не совпадает с видимым текстом

### Requirement: Heading hierarchy MUST быть последовательной внутри page и dialog sections
Система ДОЛЖНА (SHALL) обеспечивать, что headings на operator-facing surfaces идут в последовательной иерархии без необоснованных скачков уровня внутри page section или dialog/drawer section.

#### Scenario: Detail drawer не прыгает от page title сразу к deep nested heading
- **GIVEN** пользователь открыл detail section или drawer на platform-governed route
- **WHEN** screen reader или audit tool анализирует heading structure
- **THEN** headings follow sequential hierarchy
- **AND** section heading не перескакивает на более глубокий уровень без промежуточного контекста

### Requirement: Operator-facing text and state labels MUST проходить WCAG AA contrast в default theme
Система ДОЛЖНА (SHALL) обеспечивать для default theme, что operator-facing text, status indicators, selected navigation states и action labels на platform-governed surfaces и shared shell проходят WCAG AA contrast requirements.

Это относится минимум к:
- secondary explanatory text, которое участвует в основном operator flow;
- primary и danger action labels;
- selected navigation item states;
- shared status badges и similar inline state indicators.

#### Scenario: Shared shell и page action states проходят contrast audit
- **GIVEN** пользователь открывает platform-governed route, включая `/pools/binding-profiles`
- **WHEN** automated accessibility audit проверяет shared shell и primary page states
- **THEN** selected navigation state, status badges, page subtitles и primary/danger action labels проходят WCAG AA contrast
- **AND** страница не зависит от known failing contrast exceptions в этих состояниях

### Requirement: High-traffic operational routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать route pages `/`, `/operations`, `/databases`, `/pools/catalog` и `/pools/runs` как platform-governed surfaces следующей волны UI migration.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `DashboardPage` или `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog/detail/authoring flows вместо raw `antd` containers как page-level foundation.

Raw `antd` imports МОГУТ (MAY) оставаться внутри leaf presentational blocks, если route shell и primary orchestration уже проходят через platform layer, но НЕ ДОЛЖНЫ (SHALL NOT) оставаться основным способом сборки route-level workspace.

#### Scenario: Lint блокирует возврат raw page shell на platform-governed route
- **GIVEN** разработчик меняет `/operations` или другой route из governance perimeter
- **WHEN** route-level page module снова импортирует raw `Card`, `Row`, `Col`, `Table`, `Drawer` или аналогичный container как основу primary composition
- **THEN** frontend lint сообщает явное platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Operational platform migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated operational routes так, чтобы automated checks покрывали:
- platform-boundary regressions, которые ловятся lint;
- route-state restore и same-route stability, которые проверяются browser-level tests;
- shell-safe internal handoff и отсутствие redundant shell reads на authenticated route;
- mobile-safe detail fallback и отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression в route-state и responsive contract
- **GIVEN** migrated operational route уже использует platform workspace
- **WHEN** regression ломает reload/back-forward restore, same-route re-entry, shell-safe internal handoff или narrow-viewport detail flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change

### Requirement: Authenticated internal navigation MUST сохранять shared shell runtime
Система ДОЛЖНА (SHALL) использовать SPA navigation для внутренних переходов между authenticated frontend route, которые живут под общим application shell.

Такие handoff path НЕ ДОЛЖНЫ (SHALL NOT) использовать full-document navigation как основной путь, если целевой route находится внутри того же frontend приложения и может быть открыт через router navigation.

Shared shell/bootstrap + authz providers ДОЛЖНЫ (SHALL) оставаться canonical owner для user/staff/tenant context. Route pages НЕ ДОЛЖНЫ (SHALL NOT) дублировать `/api/v2/system/bootstrap/`, `/api/v2/system/me/` и `/api/v2/tenants/list-my-tenants/` на default operator path, если тот же context уже доступен через shared shell runtime.

Исключения допускаются только для dedicated login/logout path, explicit refresh flows, tenant-management surfaces или route, где shell context ещё не инициализирован по design.

#### Scenario: Internal CTA переводит оператора на другой route без document reload
- **GIVEN** оператор находится на authenticated route внутри frontend shell
- **WHEN** он нажимает internal CTA или handoff action, ведущий на другой route того же приложения
- **THEN** navigation выполняется внутри SPA shell без full-document reload
- **AND** bootstrap budget не расходуется повторно только из-за этого перехода

#### Scenario: Route page использует shell-owned user и tenant context вместо повторных shell reads
- **GIVEN** shared shell runtime уже загрузил bootstrap и синхронизировал `isStaff` и active tenant
- **WHEN** route page монтируется по своему default operator path
- **THEN** страница получает user/staff/tenant context через shared providers
- **AND** не инициирует redundant вызовы `/api/v2/system/bootstrap/`, `/api/v2/system/me/` и `/api/v2/tenants/list-my-tenants/` без явного runtime trigger

### Requirement: Stateful workspace routes MUST синхронизировать primary navigation state с URL
Система ДОЛЖНА (SHALL) обеспечивать, что stateful workspace routes отражают primary filter/selection state в URL, если без этого пользователь теряет адресуемый рабочий контекст.

Для catalog/detail surfaces сюда входят как минимум selected entity, активный filter mode, поисковый запрос и detail-open state, если они меняют основной смысл текущего экрана.

#### Scenario: Пользователь делится ссылкой на конкретный workspace context
- **GIVEN** пользователь выбрал сущность и фильтры в stateful catalog/detail route
- **WHEN** он копирует URL и открывает его в новой вкладке или использует back/forward
- **THEN** система восстанавливает тот же основной workspace context
- **AND** не требует повторно выбирать entity/filter вручную

### Requirement: Master-detail selection MUST использовать semantic control и явный selected state
Система ДОЛЖНА (SHALL) обеспечивать, что primary selection в master-detail surface выполняется через semantic interactive control, а выбранное состояние читается и визуально, и программно.

Row click без отдельного semantic trigger МОЖЕТ (MAY) существовать как дополнительное удобство, но НЕ ДОЛЖЕН (SHALL NOT) быть единственным primary path.

#### Scenario: Выбор элемента каталога доступен с клавиатуры и имеет selected state
- **GIVEN** пользователь работает с catalog/detail page
- **WHEN** он выбирает элемент списка только с клавиатуры
- **THEN** selection trigger является semantic control
- **AND** текущий выбранный элемент имеет явный selected state (`aria-selected`, `aria-current` или эквивалентный корректный путь)
- **AND** визуальное выделение выбранного элемента читается без наведения мышью

### Requirement: Workflow and template routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать `/workflows`, `/workflows/executions`, `/workflows/new`, `/workflows/:id`, `/workflows/executions/:executionId`, `/templates`, `/pools/templates` и `/pools/master-data` как следующую волну platform-governed surfaces.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog/detail/authoring flows вместо raw `antd` containers как page-level foundation.

#### Scenario: Lint блокирует возврат raw page shell на workflow/template route
- **GIVEN** разработчик меняет `/workflows` или другой route из workflow/template perimeter
- **WHEN** route-level page module снова использует raw `Layout`, `Card`, `Tabs`, `Table`, `Modal` или `Drawer` как основу primary composition
- **THEN** frontend lint сообщает platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Workflow/template migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated workflow/template routes так, чтобы automated checks покрывали:
- route-state restore и same-route stability;
- shell-safe handoff между workflow/template route и соседними authenticated route;
- mobile-safe detail or inspect fallback;
- отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression на workflow/template route
- **GIVEN** migrated workflow или template route уже использует platform workspace
- **WHEN** regression ломает reload/deep-link restore, same-route re-entry, shell-safe handoff или narrow-viewport inspect flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change

### Requirement: Privileged admin/support routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать route pages `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions`, `/settings/runtime`, `/settings/command-schemas` и `/settings/timeline` как следующую волну platform-governed surfaces внутри authenticated shell.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog/detail/authoring flows вместо raw `antd` containers как page-level foundation.

Raw `antd` imports МОГУТ (MAY) оставаться внутри leaf presentational blocks, если route shell и primary orchestration уже проходят через platform layer, но НЕ ДОЛЖНЫ (SHALL NOT) оставаться основным способом сборки route-level workspace.

#### Scenario: Lint блокирует возврат raw page shell на privileged route
- **GIVEN** разработчик меняет `/rbac`, `/extensions` или другой route из admin/support perimeter
- **WHEN** route-level page module снова использует raw `Card`, `Row`, `Col`, `Drawer`, `Modal`, `Tabs` или аналогичный container как основу primary composition
- **THEN** frontend lint сообщает platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Admin/support platform migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated admin/support routes так, чтобы automated checks покрывали:
- platform-boundary regressions, которые ловятся lint;
- route-state restore и same-route stability;
- shell-safe handoff на соседние authenticated route;
- mobile-safe detail fallback и отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression на migrated admin/support route
- **GIVEN** migrated admin/support route уже использует platform workspace
- **WHEN** regression ломает reload/deep-link restore, same-route re-entry, shell-safe handoff или narrow-viewport detail flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change

### Requirement: Infrastructure and observability routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать `/clusters`, `/system-status` и `/service-mesh` как platform-governed surfaces внутри authenticated frontend.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog, diagnostics и inspect flows вместо bespoke raw `antd` page shells.

#### Scenario: Lint блокирует возврат bespoke page shell на infra route
- **GIVEN** разработчик меняет `/clusters`, `/system-status` или `/service-mesh`
- **WHEN** route-level page module снова использует raw `Card`, `Row`, `Col`, `Layout`, `Modal`, `Drawer` или custom div/css shell как основу primary composition
- **THEN** frontend lint сообщает platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Infra/observability migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated infra/observability routes так, чтобы automated checks покрывали:
- route-state restore и same-route stability;
- responsive fallback и отсутствие page-wide horizontal overflow;
- shell-safe handoff на соседние authenticated route;
- polling/realtime stability на operator-facing route path.

#### Scenario: Browser validation ловит regression на infra/observability route
- **GIVEN** migrated infra или observability route уже использует platform workspace
- **WHEN** regression ломает route-state restore, responsive fallback или polling/realtime interaction contract
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change

