# `stroygrupp` Bootstrap Verified on Dev (`2026-03-06`)

## Что выполнено
На dev применён deterministic bootstrap baseline для:
- tenant: `default`
- database: `stroygrupp_7751284461`
- pool: `stroygrupp-full-publication-baseline`
- topology: `Общество -> ООО "СТРОЙГРУПП"`
- document policy: `Document_РеализацияТоваровУслуг -> Услуги`

Management command:
- `python manage.py bootstrap_stroygrupp_publication_baseline --tenant-slug default --actor-username admin --json`

Команда:
- создала dedicated pool и single-edge topology;
- проставила `edge.metadata.document_policy`;
- создала/обновила canonical entities:
  - `party.stroygrupp`
  - `party.proekt-st`
  - `contract.osnovnoy` (owner `proekt-st`)
  - `item.packing-service`
- создала/обновила bindings для organization/counterparty/contract/item;
- привязала `Organization.master_party` для `ООО "СТРОЙГРУПП"`.

## Что верифицировано после apply
Проверка через Django runtime показала:
- pool `stroygrupp-full-publication-baseline` существует;
- nodes:
  - `Общество` (`is_root=true`)
  - `ООО "СТРОЙГРУПП"` (`is_root=false`)
- edges:
  - ровно одна связь `Общество -> ООО "СТРОЙГРУПП"` с `weight = 1`
- canonical master data и bindings присутствуют в tenant `default`
- `ООО "СТРОЙГРУПП".master_party -> party.stroygrupp`

## Обновление статуса после live acceptance
Изначальный blocker с actor mapping был снят:
- UI user `admin` смапплен на dedicated IB actor `ГлавБух / 22022`;
- bootstrap baseline теперь даёт `readiness.ready_for_ui_run = true`;
- `actor_coverage.has_gaps = false`;
- `service_coverage.has_gaps = false`.

Текущее состояние:
- bootstrap sequence на `default/stroygrupp_7751284461` полностью применён;
- `Database.metadata.odata_transport.verify_tls = false` проставляется детерминированно для self-signed dev OData;
- полный live UI run и OData verification сохранены в отдельном артефакте:
  - `artifacts/stroygrupp-ui-run-verified-2026-03-06.md`
