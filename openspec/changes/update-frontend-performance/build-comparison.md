# Build comparison

## Baseline
См. `baseline-build.md` (лог `cd frontend && npm run build`).

## After
См. `after-build.md` (лог `cd frontend && npm run build` после правок этого change).

## Notes
- Сборки имеют близкие размеры, но отличается состав/трассировка чанков (удобнее смотреть через `npm run analyze`).

## Bundle analyzer
Добавлена команда:

```bash
cd frontend
npm run analyze
```

Результат: `frontend/dist/bundle-report.html` (локальный артефакт, не коммитится).
