# Engineering Guidelines

## Цель: уменьшать размер файлов до ~700 строк

В проекте много больших исходных файлов (тысячи строк). Это усложняет сопровождение и снижает эффективность работы LLM/агентов (сложно держать контекст).

Мы используем ориентир: **цель — <= 700 строк на файл** (по `wc -l`) за счёт **реального разноса по модулям**, без “искусственных” обходов.

### Что считается “исходниками”
- Включаем: `*.ts`, `*.tsx`, `*.py`, `*.go` **включая тесты**.
- Считаем строки как `wc -l` (количество символов перевода строки).
- Файлы берём только из `git ls-files` (т.е. git-tracked).

### Что исключаем из отчёта
Исключения фиксируются в `scripts/dev/file-size-report.config.json:1` и включают:
- сгенерированное: `frontend/src/api/generated/**`, `frontend/src/api/generated-gateway/**`
- артефакты сборки/зависимости: `frontend/dist/**`, `frontend/node_modules/**`
- архивы: `**/archive/**` (в т.ч. `orchestrator/tests/archive/**`, `docs/archive/**`)
- миграции Django: `**/migrations/**`

## Как получить отчёт

### Быстро
`make file-sizes`

### По подсистеме
`python3 scripts/dev/file-size-report.py --scope frontend`
`python3 scripts/dev/file-size-report.py --scope orchestrator`
`python3 scripts/dev/file-size-report.py --scope go-services`

Опции:
- `--limit 700` (порог)
- `--top 30` (сколько показывать)
- `--all` (показать все файлы > порога)

## Как делать рефакторинг (важно)
- Только декомпозиция по ответственности (components/hooks/utils/services и т.п.).
- Не использовать директивы/прагмы/локальные allowlist'ы ради метрики.
- Не менять поведение и публичные контракты (только перенос кода).

