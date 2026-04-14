## Context
После change `add-03-pool-master-data-manual-sync-launches` оператор может запускать manual sync в режиме `cluster_all` или `database_set`. Реализация `cluster_all` сейчас опирается только на `tenant_id + cluster_id`, то есть считает целевым набором все базы кластера.

На практике это недостаточно строго. В одном кластере могут жить:
- базы другой конфигурации;
- пилотные или служебные базы;
- базы, не входящие в operator-approved scope конкретного pool master-data workflow.

Техническая доступность (`odata_url`, service mapping, runtime enabled state) не отвечает на вопрос business participation. Поэтому change должен добавить явный декларативный слой eligibility и сделать `cluster_all` fail-closed поверх него.

## Goals / Non-Goals

### Goals
- Сделать участие базы в `cluster_all` явным и операторски управляемым.
- Блокировать `cluster_all`, пока по каждой базе кластера нет явного решения.
- Оставить `database_set` как explicit override path для one-off запусков.
- Развести business eligibility и technical readiness.
- Дать оператору единый remediation path через `/databases`.

### Non-Goals
- Не строить heuristic classifier "подходит ли база" по connection/runtime metadata.
- Не менять child sync runtime, policy gates или outbox semantics.
- Не делать tenant-wide bulk editor для eligibility в этой версии.
- Не распространять новый contract автоматически на другие cluster-scoped features вне pool master-data sync.

## Decisions

### Decision: Используем explicit tri-state membership вместо bool
Per-database state должен быть именно tri-state:
- `eligible`
- `excluded`
- `unconfigured`

Причины:
- `false` недостаточно различает intentional exclusion и legacy отсутствие решения;
- fail-closed rollout требует уметь блокировать `cluster_all`, пока оператор явно не разобрал legacy cluster membership;
- оператору нужен понятный remediation path, а не неявный default.

### Decision: `cluster_all` включает только `eligible`, `excluded` не блокирует, `unconfigured` блокирует
Target expansion semantics:
- `eligible` базы включаются в immutable launch snapshot;
- `excluded` базы не включаются в snapshot и возвращаются как явные diagnostics;
- если в выбранном кластере есть хотя бы одна `unconfigured` база, create request отклоняется и parent launch не создаётся.

Это сохраняет fail-closed поведение без silent targeting лишних ИБ и без требования включать в launch базы, которые оператор намеренно исключил.

### Decision: Business eligibility и technical readiness живут отдельно
Eligibility отвечает на вопрос "должна ли база участвовать в `cluster_all`".
Readiness отвечает на вопрос "готова ли база технически к запуску сейчас".

Readiness НЕ ДОЛЖЕН (SHALL NOT):
- автоматически переводить `eligible` в `excluded`;
- автоматически помечать `unconfigured` как `eligible`;
- подменять operator decision.

В UI `/databases` readiness summary остаётся отдельным read-only diagnostic слоем рядом с eligibility control.

### Decision: Канонический UI ownership остаётся за `/databases`
Управление per-database eligibility должно жить в `/databases`, потому что это уже canonical operator-facing surface для per-database configuration and metadata management.

`/pools/master-data?tab=sync` остаётся consumer surface:
- показывает summary по кластеру;
- блокирует submit при `unconfigured`;
- даёт handoff в `/databases`.

Это не допускает появления второго конкурирующего editor path для одной и той же per-database настройки.

### Decision: Launch detail хранит resolution summary для `cluster_all`
Если `cluster_all` launch успешно создан, parent launch snapshot должен сохранять не только included `database_ids`, но и resolution summary:
- сколько баз вошло как `eligible`;
- какие базы были `excluded` и почему не вошли в snapshot.

Это нужно, чтобы history/detail объясняли оператору итоговый target set даже после изменения database catalog.

### Decision: `database_set` не использует `cluster_all` membership как hard gate
`database_set` — explicit operator override path. Поэтому eligibility state для `cluster_all` не должен автоматически запрещать manual sync по `database_set`.

Остаются в силе обычные tenant/access/policy/runtime проверки, но `excluded` база может быть выбрана явно для one-off запуска, если оператор на это уполномочен.

## Alternatives Considered

### Alternative: Boolean `cluster_all_eligible=true|false`
Отклонено.

Минусы:
- не различает legacy "ещё не настроено" и intentional exclusion;
- вынуждает либо silently default в `false`, либо silently включать базы;
- ухудшает rollout и диагностику.

### Alternative: Auto-detect eligibility по runtime metadata
Отклонено.

Минусы:
- техническая доступность не равна business participation;
- легко ошибиться на смешанных кластерах;
- противоречит fail-closed цели.

### Alternative: Управлять eligibility прямо из launch drawer
Отклонено.

Минусы:
- создаёт второй competing editor path для per-database настройки;
- ломает canonical ownership `/databases`;
- затрудняет аудит и повторное использование настройки вне одного конкретного launch.

## Risks / Trade-offs
- Роллаут станет строже: существующие `cluster_all` сценарии могут временно блокироваться, пока оператор не проставит explicit state.
  - Это намеренный fail-closed trade-off.
- Оператор может путать `excluded` и "временно не готова".
  - UI должен показывать separate readiness summary и явно разделять эти понятия.
- Потребуется cross-surface handoff между `/pools/master-data` и `/databases`.
  - Это приемлемо, потому что ownership per-database configuration уже закреплён за `/databases`.

## Migration Plan
1. Ввести persisted state с default semantics `unconfigured` для существующих записей.
2. Не менять `database_set`.
3. Перевести `cluster_all` на новый gate:
   - `unconfigured` блокирует create request;
   - `excluded` не попадает в snapshot;
   - `eligible` попадает в snapshot.
4. Добавить UI remediation path в `/databases` и handoff из sync launcher.
5. После rollout оператор заполняет membership states для рабочих кластеров до возврата штатного использования `cluster_all`.
