## Context
На текущем стеке уже есть:
- `Command Schemas` как низкоуровневый контракт команды и driver-level/options schema;
- `templates` как runtime-resolvable operation exposures;
- `workflow` как reusable orchestration layer;
- единый execution runtime для operations/workflows/pools.

Это означает, что service operations уже почти готовы к workflow orchestration, но отсутствует явный platform contract, который ответит на вопросы:
- какие templates безопасно и осмысленно вызывать из workflow;
- как domain UI запускает curated workflow без выбора raw workflow definition;
- как сохранить domain-friendly UX и lineage, если underlying execution идёт через workflow.

Особенно важно не сломать layering:
- `Command Schemas` остаются low-level contract;
- `templates` остаются атомарными исполняемыми шагами;
- `workflow` композирует templates и decisions в процесс;
- domain UI запускает `service_action`, а не raw command schema.

## Goals
- Дать service domains reusable workflow automation path поверх templates.
- Сохранить strict layering `command schema -> template -> workflow`.
- Ввести критерии `workflow-safe template`.
- Дать domain surfaces способ запускать curated workflows по `service_action`.
- Сохранить direct execution path для простых одношаговых операций.
- Сохранить unified observability и deterministic lineage.

## Non-Goals
- Не переводить raw command builder в workflow authoring UI.
- Не перепроектировать целиком все domain UIs.
- Не удалять manual/template-based flows там, где они по-прежнему уместны.
- Не превращать любой template автоматически в workflow-safe step без явного контракта.

## Decisions
### Decision 1: Workflow вызывает только templates
Workflow nodes для service automation вызывают только template exposures через `operation_ref`.

`Command Schemas` остаются внутренним уровнем, который используется при создании/редактировании template, но не является прямым runtime target для workflow authoring.

### Decision 2: Вводится `workflow-safe template` профиль
Template, пригодный для service workflow reuse, должен иметь явный metadata/profile контракт:
- capability/domain tags;
- input/output contract;
- target scope;
- side-effect profile;
- idempotency expectation;
- verification contract;
- optional approval/rollback hints.

Без такого профиля template может оставаться valid template для direct execution, но не должен автоматически считаться reusable workflow step.

### Decision 3: Domain surfaces запускают `service_action`, а не raw workflow id
Для domain UI вводится binding:
- `service_action` -> pinned workflow definition/revision.

Это позволяет:
- скрыть технический workflow catalog от конечного доменного пользователя;
- менять workflow implementation через controlled binding;
- использовать один и тот же reusable workflow из разных entrypoints.

### Decision 4: Direct execution path остаётся
Не каждая service operation обязана идти через workflow.

Если операция одношаговая и не требует orchestration, direct template/operation launch остаётся допустимым путём. Workflow path добавляется как reusable automation mode, а не как mandatory replacement для всех single-step операций.

### Decision 5: Curated service subworkflows становятся основным reusable артефактом
Для многошаговых сервисных сценариев основным reusable артефактом становится service subworkflow:
- install/uninstall extension;
- create/update/delete infobase user;
- bulk maintenance flows;
- preflight + apply + verify processes.

Эти subworkflows состоят из workflow-safe templates и, при необходимости, decision nodes.

### Decision 6: Domain UX остаётся доменным, runtime остаётся workflow-based
`/extensions`, `/databases` и другие domain surfaces не обязаны превращаться в generic workflow monitor.

Они должны показывать domain intent, выбранный `service_action`, status и diagnostics, но underlying execution lineage должен вести к workflow definition/revision и template steps.

## Trade-offs
- Плюс: reuse сложных сервисных процессов без дублирования orchestration logic по доменам.
- Плюс: сохраняется единый runtime и единый template layer.
- Плюс: `Command Schemas` остаются на своём месте и не протекают в process authoring.
- Минус: нужен новый binding layer `service_action -> workflow`.
- Минус: часть существующих manual/domain flows потребует адаптации, чтобы стать reusable workflows.
- Минус: придётся поддерживать dual path: direct single-step execution и workflow automation.

## Migration Plan
1. Ввести spec и data/API contract для workflow-safe templates и service action workflow bindings.
2. Добавить workflow-safe metadata в template catalog.
3. Добавить launch path из domain surfaces через `service_action -> workflow`.
4. Сохранить direct/manual path как compatibility и pragmatic mode.
5. Начать onboarding с pilot domains: `extensions.*` и `database.ib_user.*`.

## Open Questions
- Binding должен быть единым generic ресурсом `service_action_workflow_binding` для всех доменов или домены могут иметь свои scoped binding tables/API?
- Нужно ли на первом этапе требовать workflow-safe profile только для curated reusable steps, или для любых templates, которые разрешено вставлять в analyst-facing workflow library?
