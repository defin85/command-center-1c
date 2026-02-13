# OData Compatibility Verification Protocol (Sokolniki_7714476359)

## Metadata
- Date: 2026-02-13
- Environment: production-like 1C infobase provided by user
- Base URL (from this runtime): `http://host.docker.internal/Sokolniki_7714476359/odata/standard.odata`
- Credentials: `odata.user` / `odata.user`
- Target capability: `pool-workflow-execution-core` OData publication compatibility

## Access Check
- `GET /odata/standard.odata/` without auth -> `401`
- `GET /odata/standard.odata/` with provided auth -> `200`
- `GET /odata/standard.odata/$metadata` with provided auth -> `200`
- Response headers include `DataServiceVersion: 3.0`

## Metadata Audit
- `Document_РеализацияТоваровУслуг` exists in service document and metadata.
- `Document_IntercompanyPoolDistribution` is not required for this target configuration check.

## CRUD / Posting Probe
Checked entity: `Document_РеализацияТоваровУслуг`

1. Read:
- `GET .../Document_РеализацияТоваровУслуг?$top=1&$select=Ref_Key,Date,Posted,Number,DeletionMark` -> `200`

2. Write format behavior:
- `POST` with JSON payload -> rejected (`406 Not acceptable` or `500` parse error depending on headers)
- `POST` with Atom XML (`application/atom+xml;type=entry`) -> `201 Created`

3. Update:
- `PATCH` by existing GUID with Atom XML -> `200`

4. Posting:
- `PATCH` with `Posted=true` and `DeletionMark=false` -> `200`
- `PATCH` with `Posted=true` while `DeletionMark=true` -> `500` business error (`Проведенный документ не может быть помечен на удаление!`)

5. Delete:
- `DELETE` by existing GUID -> `500`, insufficient rights for sequence table (`Последовательность.ДокументыОрганизаций`)

## Safety / Cleanup
- Test document was moved to safe state after probe:
  - `Posted=false`
  - `DeletionMark=true`
- Test document GUID: `627f6408-08bb-11f1-8621-9c6b0063a0aa`

## Conclusion
- Target BP 3.0 endpoint for publication can be based on `Document_РеализацияТоваровУслуг`.
- Mandatory compatibility constraint: write operations require Atom XML payloads for this base.
- Current generic JSON write path is not sufficient for this configuration and must be aligned before rollout approval.
