## 1. Реализация
- [x] Устранить все offenders >700 под `orchestrator/` (включая тесты), проверяя `python3 scripts/dev/file-size-report.py --scope orchestrator --all`.
- [x] `apps.api_internal`: разнести крупные тесты (`orchestrator/apps/api_internal/tests/test_views.py`) на несколько файлов по доменам.
- [x] `apps.operations`: разнести `orchestrator/apps/operations/event_subscriber.py` на подпакет и разбить крупные тесты.
- [x] `apps.databases`: разнести `models.py` и `admin.py` на подмодули с сохранением публичных импортов.
- [x] `apps.templates`: разнести `workflow/models.py`, `tracing.py` и крупные тесты (`test_registry.py`, `test_validator.py`, `test_tracing.py`, `test_benchmarks.py`) на несколько файлов.

## 2. Валидация
- [x] 2.1 `./scripts/dev/lint.sh` (ruff + др.)
- [x] 2.2 `pytest` (релевантные пакеты/полный прогон по договорённости)
- [x] 2.3 `openspec validate refactor-orchestrator-files-under-700 --strict --no-interactive`
