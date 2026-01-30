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

