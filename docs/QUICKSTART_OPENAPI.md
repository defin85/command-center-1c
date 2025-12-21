# OpenAPI Quickstart

Краткий чек-лист для работы с контрактами API.

## 1) Редактирование спецификации

```bash
vim contracts/orchestrator/openapi.yaml
```

## 2) Проверка и генерация

```bash
./contracts/scripts/validate-specs.sh
./contracts/scripts/generate-all.sh
```

## 3) Что обновляется

- `go-services/api-gateway/internal/routes/generated/`
- `frontend/src/api/generated/`

## 4) Коммит

```bash
git add contracts/orchestrator/openapi.yaml
git add go-services/api-gateway/internal/routes/generated/
git add frontend/src/api/generated/
git commit -m "fix: Update orchestrator API spec"
```

## Troubleshooting

- Если Go не компилируется: `cd go-services/api-gateway && go build ./...`
- Если TS типы ругаются: `cd frontend && npx tsc --noEmit`
