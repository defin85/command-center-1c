# Orchestrator OpenAPI Modular Source

`contracts/orchestrator/src/**` является единственным editable source-of-truth для public OpenAPI orchestrator.

`contracts/orchestrator/openapi.yaml` это generated bundle для tooling/clients и не должен редактироваться вручную.

## Layout

```text
contracts/orchestrator/src/
├── openapi.yaml
├── paths/
└── components/
    └── schemas/
```

## Naming conventions

- `paths/*.yaml`:
  - имя строится от URL path (slash -> `_`, `{param}` сохраняется как `{param}` в имени файла);
  - пример: `/api/v2/pools/runs/{run_id}/retry/` -> `api_v2_pools_runs_{run_id}_retry_.yaml`.
- `components/schemas/*.yaml`:
  - имя файла совпадает с именем schema в OpenAPI (`PascalCase`).
- `operationId`:
  - должен быть уникальным в рамках всего контракта.

## Edit workflow

1. Внести изменения в `src/**`.
2. Пересобрать bundle:
   - `./contracts/scripts/build-orchestrator-openapi.sh build`
3. Проверить актуальность:
   - `./contracts/scripts/build-orchestrator-openapi.sh check`
4. Запустить:
   - `./contracts/scripts/validate-specs.sh`
   - `./contracts/scripts/generate-all.sh`

## Troubleshooting

- Если `check` падает с "bundle is out of date":
  - запустите `build` и закоммитьте обновленный `contracts/orchestrator/openapi.yaml`.
