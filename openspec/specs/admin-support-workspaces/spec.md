# admin-support-workspaces Specification

## Purpose
TBD - created by archiving change 03-refactor-ui-platform-admin-support-workspaces. Update Purpose after archive.
## Requirements
### Requirement: `/rbac` MUST использовать canonical governance workspace
Система ДОЛЖНА (SHALL) представлять `/rbac` как privileged governance workspace с URL-addressable selected mode/tab context и canonical secondary surfaces для управления ролями и назначениями.

RBAC access gates (`RbacRoute`, staff-only sections) ДОЛЖНЫ (SHALL) сохраняться, но НЕ ДОЛЖНЫ (SHALL NOT) оправдывать bespoke page-level composition вне platform layer.

#### Scenario: Deep-link восстанавливает выбранный режим и tab RBAC workspace
- **GIVEN** оператор открывает `/rbac` с query state, указывающим режим и активный tab
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает выбранный mode/tab context
- **AND** primary inspect/manage flow остаётся внутри platform-owned shell

### Requirement: `/users` MUST использовать canonical user management workspace
Система ДОЛЖНА (SHALL) представлять `/users` как catalog/detail/authoring workspace с URL-addressable selected user context и canonical secondary surfaces для create/edit/password flows.

Primary authoring path НЕ ДОЛЖЕН (SHALL NOT) зависеть от page-level raw `Modal` orchestration как единственного contract boundary.

#### Scenario: User authoring идёт через canonical secondary surface
- **GIVEN** staff пользователь открывает `/users`
- **WHEN** выбирает create, edit или password reset flow
- **THEN** flow открывается через canonical secondary surface внутри platform workspace
- **AND** selected user context остаётся адресуемым и не теряется при reload/back-forward

### Requirement: `/dlq` MUST использовать remediation workspace с shell-safe handoff
Система ДОЛЖНА (SHALL) представлять `/dlq` как remediation workspace с URL-addressable selected message context, canonical detail/remediation surface и shell-safe handoff в `/operations`.

#### Scenario: Оператор переходит из DLQ в Operations без потери shared shell
- **GIVEN** оператор открыл конкретное DLQ сообщение и доступен связанный `operation_id`
- **WHEN** он выбирает handoff в `/operations`
- **THEN** navigation выполняется внутри SPA shell без full-document reload
- **AND** selected message context в `/dlq` остаётся восстанавливаемым через URL

### Requirement: `/artifacts` MUST использовать canonical catalog workspace
Система ДОЛЖНА (SHALL) представлять `/artifacts` как catalog workspace с URL-addressable tab/artifact context и canonical secondary surfaces для create/details/purge/remediation flows.

#### Scenario: Artifact detail и active/deleted catalog state восстанавливаются из URL
- **GIVEN** оператор открывает `/artifacts` с query state, указывающим catalog tab и выбранный artifact
- **WHEN** страница загружается повторно или пользователь использует browser back/forward
- **THEN** workspace восстанавливает выбранный tab и artifact context
- **AND** detail/create/purge surfaces не требуют отдельного bespoke page reflow

