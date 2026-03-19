## ADDED Requirements
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
