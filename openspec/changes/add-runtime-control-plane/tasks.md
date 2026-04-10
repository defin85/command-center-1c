## 1. Contracts And Permissions
- [x] 1.1 Ввести capability `runtime-control-plane` и описать allowlisted runtime catalog, async action runs, provider constraints и scheduler desired-state semantics.
- [x] 1.2 Добавить dedicated permission/shell capability для runtime controls и зафиксировать diagnostics-only fallback для пользователей без него.
- [x] 1.3 Зафиксировать global-only runtime-control settings semantics, чтобы scheduler/runtime keys не попадали в tenant override APIs.

## 2. Backend
- [ ] 2.1 Реализовать runtime-control API для catalog/detail/action history/action execution/desired-state updates.
- [ ] 2.2 Добавить provider-backed executor для local/hybrid runtimes со stable runtime instance identity, allowlisted actions per runtime, detached dispatch для self-target lifecycle actions и bounded/redacted result excerpts.
- [ ] 2.3 Добавить модель/журнал operator-triggered runtime actions с actor, reason, target, persisted-before-dispatch lifecycle, status и timestamps.
- [ ] 2.4 Обновить worker scheduler, чтобы global/per-job enablement применялись через global desired state без обязательного process restart, а schedule/cadence edits имели явный controlled apply path.
- [ ] 2.5 Связать operator-triggered scheduler actions с existing `SchedulerJobRun`, чтобы `trigger_now` имел correlatable execution history.

## 3. Frontend
- [ ] 3.1 Расширить `/system-status` runtime drill-down'ом (`Overview`, `Controls`, `Scheduler`, `Logs`) с route-addressable runtime/tab/job context.
- [ ] 3.2 Спрятать mutating controls за runtime-control capability, сохранив diagnostics-only UX для остальных пользователей.
- [ ] 3.3 Доработать `/settings/runtime` как advanced authoring path для scheduler/runtime policy keys и deep-link handoff из `/system-status`, не обещая второй live control console.
- [ ] 3.4 Сохранить различие между global scheduler `trigger_now` и domain-specific actions вроде `Refresh factual sync` в `/pools/factual`.

## 4. Verification
- [ ] 4.1 Добавить backend tests для RBAC, async action audit trail, self-target action completion, allowlisted provider actions, redaction, scheduler/action correlation и global-only key filtering.
- [ ] 4.2 Добавить frontend tests для capability gating, deep-link restore, privileged control visibility и narrow-viewport fallback.
- [ ] 4.3 Прогнать релевантные checks из `docs/agent/VERIFY.md` и `openspec validate add-runtime-control-plane --strict --no-interactive`.
