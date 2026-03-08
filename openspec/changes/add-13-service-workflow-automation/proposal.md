# Change: Добавить service operations automation через workflow-safe templates

## Why
После `refactor-12-workflow-centric-analyst-modeling` workflows становятся primary process layer для analyst-facing и reusable automation сценариев.

Следующий логичный шаг — разрешить не только pool distribution/publication, но и сервисные операции выполнять через workflows, если эти операции внизу уже выражаются через templates, а templates, в свою очередь, собраны из `Command Schemas`.

Это нужно для сценариев вроде:
- установка/удаление расширений;
- создание/изменение пользователей ИБ;
- многошаговые сервисные операции с preflight, verification, approval, retry;
- reuse одного и того же service flow между несколькими domain surfaces и tenant-контекстами.

При этом workflows НЕ ДОЛЖНЫ (SHALL NOT) вызывать `Command Schemas` напрямую. Правильный слой композиции:
`Command Schema -> Template -> Workflow -> Runtime`.

## What Changes
- Ввести платформенный capability для `service workflow automation`, где workflow может вызывать только `workflow-safe templates`, а не raw command schemas.
- Ввести явный `workflow-safe` контракт для templates, пригодных для вызова из service workflows.
- Ввести tenant/domain-scoped binding от `service_action` к pinned workflow definition, чтобы domain UI мог запускать curated workflow без показа raw workflow catalog.
- Зафиксировать, что прямой запуск одношаговых service operations через `/operations` или существующие domain/manual surfaces может сохраняться, но reusable automation path должен поддерживаться через workflows.
- Разрешить доменным поверхностям, в первую очередь `/extensions`, запускать service actions через workflow binding, сохраняя domain-friendly UX и diagnostics.
- Зафиксировать lineage: domain `service_action` -> workflow revision -> workflow-safe template steps -> execution.

## Impact
- Affected specs:
  - `service-workflow-automation` (new)
  - `operation-templates`
  - `extensions-overview`
- Affected code (expected):
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Operations/**`
  - `frontend/src/pages/Extensions/**`
  - `frontend/src/pages/Databases/**`
  - `frontend/src/components/workflow/**`
  - `orchestrator/apps/templates/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/api_v2/**`
  - `contracts/orchestrator/src/**`
  - `contracts/orchestrator/openapi.yaml`

## Dependencies
- Этот change предполагает, что `refactor-12-workflow-centric-analyst-modeling` уже принят как primary authoring direction для workflows.
- Этот change НЕ ДОЛЖЕН (SHALL NOT) вводить альтернативную process model поверх `refactor-12`; он расширяет её на service operations domains.

## Sequencing
- `add-13-service-workflow-automation` является follow-up phase после `refactor-12-workflow-centric-analyst-modeling`.
- Этот change НЕ ДОЛЖЕН (SHALL NOT) начинаться до тех пор, пока `refactor-12` не зафиксирует:
  - analyst-facing workflow model;
  - decision layer;
  - authored vs generated workflow separation;
  - binding/runtime lineage contract.
- Pilot onboarding service domains (`extensions.*`, `database.ib_user.*`) ДОЛЖЕН (SHALL) опираться на уже внедрённую workflow-centric platform model, а не проектировать её заново локально в домене.

## Non-Goals
- Не переводить все существующие service-domain flows на workflows в одном change.
- Не разрешать workflow nodes вызывать raw `Command Schemas` напрямую.
- Не удалять `/operations` и не запрещать direct execution для одношаговых задач.
- Не обещать полную замену всех existing domain endpoints (`/extensions`, `/databases`, `/users`) в рамках одного релиза.
