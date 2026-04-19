## ADDED Requirements

### Requirement: Репозиторий MUST публиковать stable project memory policy для агента

Система ДОЛЖНА (SHALL) иметь stable checked-in policy surface для manual project memory, когда агент использует Hindsight или эквивалентную memory system.

Project memory policy ДОЛЖНА (SHALL):
- описывать, когда делать recall и retain;
- различать подход для routine lookup и synthesis;
- ссылаться на canonical bank naming или repo-local override, если он есть;
- быть discoverable из authoritative agent guidance;
- описывать, какие сведения memory system дополняет, а не дублирует относительно checked-in docs.

#### Scenario: Агент начинает нетривиальную задачу и выбирает правильный memory workflow
- **GIVEN** агент работает в репозитории с ручной project memory
- **WHEN** он ищет policy для recall/retain
- **THEN** он находит stable checked-in guidance по тому, когда и как использовать память
- **AND** не вынужден восстанавливать workflow по разрозненным примерам прошлых сессий

### Requirement: Project memory MUST оставаться high-signal и не вырождаться в session log

Система ДОЛЖНА (SHALL) ограничивать normal-case memory contract устойчивыми, переиспользуемыми техническими фактами, а не превращать project memory в журнал текущего разговора.

Default memory policy ДОЛЖНА (SHALL):
- ограничивать normal-case note taxonomy как минимум типами `repo-fact`, `gotcha`, `verified-fix`, `active-change-note`;
- требовать, чтобы retain происходил после verified discovery, verified fix или другой проверенной и переиспользуемой находки;
- запрещать как default retain content промежуточные статусы плана, пересказ текущего запроса пользователя, временный operational noise и факты, уже явно зафиксированные в authoritative docs без дополнительной ценности;
- приводить negative examples низкосигнальных записей.

#### Scenario: Агент решает, стоит ли сохранять новую заметку в память
- **GIVEN** агент получил новый факт в ходе работы
- **WHEN** он сравнивает этот факт с memory policy
- **THEN** он понимает, является ли факт high-signal и переиспользуемым
- **AND** не сохраняет его в project memory, если это просто session trace или дубликат checked-in guidance
