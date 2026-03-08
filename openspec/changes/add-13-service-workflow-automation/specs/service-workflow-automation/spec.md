## ADDED Requirements
### Requirement: Service workflows MUST вызывать только workflow-safe templates
Система ДОЛЖНА (SHALL) разрешать service-domain workflows вызывать только templates, явно помеченные как `workflow-safe`.

Workflow НЕ ДОЛЖЕН (SHALL NOT) вызывать raw `Command Schemas` напрямую.

#### Scenario: Service workflow собирается из workflow-safe templates
- **GIVEN** инженер или аналитик создаёт reusable service workflow
- **WHEN** в workflow добавляются operation steps
- **THEN** editor/runtime разрешает использовать только templates с `workflow-safe` профилем
- **AND** raw command schema не выступает как selectable workflow step target

### Requirement: Workflow-safe templates MUST иметь явный reusable execution contract
Система ДОЛЖНА (SHALL) для workflow-safe templates публиковать reusable execution contract, включающий минимум:
- capability/domain;
- input/output contract;
- target scope;
- side-effect profile;
- idempotency expectation;
- verification semantics.

#### Scenario: Reusable service template публикует contract для workflow authoring
- **GIVEN** template предназначен для переиспользования в service workflows
- **WHEN** пользователь открывает details/selection этого template
- **THEN** UI и API возвращают reusable execution contract
- **AND** contract достаточен для настройки workflow step без чтения raw command schema

### Requirement: Domain surfaces MUST запускать curated workflows через service action binding
Система ДОЛЖНА (SHALL) поддерживать tenant/domain-scoped binding от `service_action` к pinned workflow definition/revision.

Domain UI ДОЛЖЕН (SHALL) запускать curated service workflows через этот binding, а не через raw workflow id selection в обычном пользовательском потоке.

#### Scenario: Domain action резолвится в pinned workflow revision
- **GIVEN** для `service_action="extensions.install"` настроен binding на workflow revision `12`
- **WHEN** пользователь запускает действие из domain UI
- **THEN** система резолвит именно workflow revision `12`
- **AND** UI не требует от пользователя ручного выбора raw workflow definition из каталога

### Requirement: Service workflow lineage MUST быть трассируемой от domain action до template steps
Система ДОЛЖНА (SHALL) сохранять lineage:
- `service_action`;
- workflow definition/revision;
- invoked templates;
- execution identifiers и statuses.

#### Scenario: Оператор трассирует install action до конкретных template steps
- **GIVEN** пользователь запустил `service_action="extensions.install"`
- **WHEN** оператор открывает details выполнения
- **THEN** details показывают связанный workflow revision
- **AND** доступны ссылки на template steps и их diagnostics без потери доменного контекста

### Requirement: Direct single-step execution MAY сосуществовать с workflow automation
Система ДОЛЖНА (SHALL) поддерживать явное сосуществование direct execution path и reusable workflow automation для service operations.

Система МОЖЕТ (MAY) сохранять direct execution path для одношаговых service operations, если orchestration workflow не даёт дополнительной пользы.

Наличие reusable workflow automation НЕ ДОЛЖНО (SHALL NOT) автоматически запрещать direct execution для совместимых single-step сценариев.

#### Scenario: Одношаговая service operation остаётся доступной без обязательного workflow wrapper
- **GIVEN** операция представляет собой один атомарный template step без preflight/verification orchestration
- **WHEN** домен поддерживает direct execution path
- **THEN** пользователь может выполнить её напрямую
- **AND** наличие reusable workflow path не делает workflow обязательным для этого сценария

### Requirement: Pilot service domains MUST включать extensions и infobase users
Система ДОЛЖНА (SHALL) рассматривать как минимум два pilot domains для onboarding reusable service workflows:
- `extensions.*`;
- `database.ib_user.*`.

#### Scenario: Пилотные домены используют единый platform contract
- **GIVEN** домены `extensions` и `database.ib_user`
- **WHEN** для них публикуются curated service workflows
- **THEN** оба домена используют один и тот же binding/runtime lineage contract
- **AND** не вводят отдельный process engine или raw command-schema authoring path
