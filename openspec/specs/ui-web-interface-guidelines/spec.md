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
Система ДОЛЖНА (SHALL) обеспечивать, что `Input/Select` и прочие form controls имеют связанный label (через `Form.Item label`/`htmlFor`) или `aria-label`.

#### Scenario: Фильтры операций имеют доступные имена
- **GIVEN** на странице есть фильтры операций по ID/Workflow/Node
- **WHEN** пользователь использует скринридер
- **THEN** каждый фильтр имеет доступное имя (label или `aria-label`)

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

