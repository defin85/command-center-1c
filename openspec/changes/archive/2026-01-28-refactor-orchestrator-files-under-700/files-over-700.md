# Файлы orchestrator > 700 строк (git-tracked)

Критерии:
- только `orchestrator/**/*.py` (включая тесты);
- исключено: `orchestrator/tests/archive/**`, `**/migrations/**` и прочие исключения из `scripts/dev/file-size-report.config.json`;
- метрика: `wc -l`;
- отсортировано по убыванию строк.

## Состояние на 2026-01-28

По `python3 scripts/dev/file-size-report.py --scope orchestrator --all`:

| Строк | Путь |
|------:|------|
| 0 | (offenders отсутствуют) |
