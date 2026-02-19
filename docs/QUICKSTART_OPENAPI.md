# OpenAPI Quickstart

Краткий чек-лист для работы с OpenAPI контрактами после перехода orchestrator на modular source.

## 1) Редактирование спецификации

Редактируйте только source-модули:

```bash
vim contracts/orchestrator/src/openapi.yaml
vim contracts/orchestrator/src/paths/<path-module>.yaml
vim contracts/orchestrator/src/components/schemas/<SchemaName>.yaml
```

`contracts/orchestrator/openapi.yaml` редактировать вручную не нужно: это generated bundle.

## 2) Сборка и проверка bundle

```bash
./contracts/scripts/build-orchestrator-openapi.sh build
./contracts/scripts/build-orchestrator-openapi.sh check
```

## 3) Валидация и генерация

```bash
./contracts/scripts/validate-specs.sh
./contracts/scripts/generate-all.sh
```

## 4) Что обновляется

- `contracts/orchestrator/openapi.yaml` (bundle)
- `go-services/api-gateway/internal/routes/generated/`
- `frontend/src/api/generated/`

## 5) Коммит

```bash
git add contracts/orchestrator/src/
git add contracts/orchestrator/openapi.yaml
git add go-services/api-gateway/internal/routes/generated/
git add frontend/src/api/generated/
git commit -m "refactor(openapi): modularize orchestrator contract"
```

## Troubleshooting

- `bundle is out of date`:
  - `./contracts/scripts/build-orchestrator-openapi.sh build`
- Ошибки TS типов:
  - `cd frontend && npx tsc --noEmit`
- Ошибки Go компиляции:
  - `cd go-services/api-gateway && go build ./...`
