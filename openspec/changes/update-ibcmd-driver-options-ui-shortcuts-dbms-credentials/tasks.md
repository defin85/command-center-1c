## 1. Implementation
- [ ] 1.1 Добавить новую модель DBMS маппинга (CC user ↔ db user/password) и миграции
- [ ] 1.2 Добавить API/permission слой для управления DBMS маппингом (создать/обновить/сбросить пароль/листинг)
- [ ] 1.3 Определить и реализовать резолв DBMS connection/creds per target для `ibcmd_cli` (api/worker граница)
- [ ] 1.4 Обновить worker: инжект DBMS creds per target (argv-only), запрет интерактива
- [ ] 1.5 Оптимизировать UI `Driver options` (сворачиваемые секции + “common/advanced” + скрытие DBMS кредов)
- [ ] 1.6 Shortcuts v2: сохранять/загружать полную конфигурацию (`driver options`/`params`/`args`) + валидация/миграция при изменении схемы
- [ ] 1.7 Обновить тесты: Django unit + frontend e2e (shortcuts, скрытие кредов, layout), worker unit
- [ ] 1.8 Обновить документацию (миграция поведения, что креды не вводятся в UI, как заводить маппинги)

## 2. Validation
- [ ] 2.1 `openspec validate update-ibcmd-driver-options-ui-shortcuts-dbms-credentials --strict --no-interactive`
- [ ] 2.2 `./scripts/dev/lint.sh` (после apply‑стадии)
- [ ] 2.3 Точечные тесты: `pytest` (orchestrator) + `frontend` tests + worker tests (после apply‑стадии)

