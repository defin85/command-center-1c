# Rollback runbook: refactor-shared-odata-core

## Trigger conditions (any)
- Critical regression in publication path affecting business side effects.
- Repeated compatibility failures across target databases.
- Sustained incident beyond agreed abort threshold.

## Rollback strategy
Только full release rollback (без mixed-mode и без partial fallback).

## Preconditions
- [ ] Previous stable artifacts available for worker and orchestrator
- [ ] DB migrations reviewed for backward compatibility
- [ ] Rollback operator assigned

## Rollback steps
1. [ ] Announce rollback start in incident channel.
2. [ ] Roll back worker to previous stable release.
3. [ ] Roll back orchestrator to previous stable release.
4. [ ] Revert runtime/config flags to pre-cutover baseline.
5. [ ] Confirm bridge endpoint behavior matches pre-cutover contract.
6. [ ] Run smoke checks on critical flows (CRUD + publication).

## Validation after rollback
- [ ] `pool.publication_odata` executes via pre-cutover path
- [ ] `PoolRunReport` payload unchanged for clients
- [ ] Error rates and queue lag return to baseline

## Closure
- [ ] Incident timeline documented
- [ ] Root cause hypothesis recorded
- [ ] Follow-up tasks created in Beads
