# Change: Добавить ручной запуск `extensions.set_flags` из `/operations` (вне workflow)

## Why
Основной сценарий управления расширениями и флагами должен оставаться workflow-first для массовых rollout.

При этом операторам нужен отдельный ручной fallback-путь в `/operations` для:
- аварийных действий,
- разовых индивидуальных прогонов,
- точечной проверки гипотезы до запуска большого workflow.

Сейчас в `/operations` нет явного ручного entrypoint для `extensions.set_flags` с выбором расширения и явным управлением флагами.

## What Changes
- Добавить в мастер `New Operation` на `/operations` ручной тип запуска для `extensions.set_flags` (fallback, вне workflow).
- В ручной форме дать оператору:
  - выбрать `action_id` из effective Action Catalog (`capability=extensions.set_flags`),
  - выбрать/ввести `extension_name`,
  - задать selective apply (`apply_mask`) и значения флагов (runtime input),
  - выполнить preview (execution plan + bindings) до подтверждения запуска.
- Запуск реализовать через существующий pipeline `extensions plan/apply` (с drift check, fail-closed validation и post-completion sync), без отдельного ad-hoc executor пути.

## Impact
- Affected specs:
  - `extensions-plan-apply`
  - `extensions-action-catalog`
- Affected code:
  - Frontend: `frontend/src/pages/Operations/**` (wizard)
  - Frontend: API layer для вызова `POST /api/v2/extensions/plan/` и `POST /api/v2/extensions/apply/`
  - Backend: точечные корректировки только при выявленных gaps контрактов/manual UX-ошибок

## Dependencies
- Change логически совместим с `refactor-extensions-set-flags-workflow-source-of-truth`.
- При его принятии ручной `/operations` flow использует тот же runtime source-of-truth (`flags_values` + `apply_mask`) как и workflow path.

## Non-Goals
- Замена workflow-first bulk rollout на ручной путь.
- Новый отдельный backend endpoint для set_flags, дублирующий `extensions plan/apply`.
- Перенос всех extension-сценариев из `/extensions` в `/operations`.
