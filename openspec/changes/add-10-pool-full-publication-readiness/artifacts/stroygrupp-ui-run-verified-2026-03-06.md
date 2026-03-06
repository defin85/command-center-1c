# `stroygrupp` Live UI Run + OData Verification (`2026-03-06`)

## Run Context
- tenant: `default`
- database: `stroygrupp_7751284461`
- pool: `stroygrupp-full-publication-baseline`
- UI actor: `admin`
- actor IB mapping: `ГлавБух / 22022`

## Live UI Run
Проверенный UI run:
- `PoolRun.id = ca4f7da6-298a-4536-bbdd-278102162f3d`
- `WorkflowExecution.id = b1c67191-71d9-4c96-8c8d-f50f3c0f297c`

Подтверждённый операторский путь:
1. run создан через UI;
2. workflow дошёл до `awaiting_approval`;
3. в `Safe Actions` нажато `Confirm publication`;
4. publication attempt завершился `success`;
5. в `PoolPublicationAttempt.response_summary.successful_document_refs` зафиксирован опубликованный документ:
   - `doc-plan:713b85f98f93070a1dfc5b26ddec19cd -> f4990e04-19a3-11f1-8cae-000c29b79fe4`

Worker log подтвердил реальные OData side effects:
- `POST /Document_РеализацияТоваровУслуг -> 201`
- `PATCH /Document_РеализацияТоваровУслуг(guid'f4990e04-19a3-11f1-8cae-000c29b79fe4') -> 200`

## OData Fact
Проверка через OData по `Ref_Key = f4990e04-19a3-11f1-8cae-000c29b79fe4` показала:

Header:
- `Posted = true`
- `DeletionMark = false`
- `ВидОперации = "Услуги"`
- `Организация_Key = 789df375-0873-11ea-a5d4-0c9d92779da8`
- `Контрагент_Key = e28bd6fe-50c9-11f0-904c-bbb30f628b54`
- `ДоговорКонтрагента_Key = f77692fd-50ca-11f0-904c-bbb30f628b54`
- `СуммаДокумента = 12956834`
- `АдресДоставки = ""`
- `ВидЭлектронногоДокумента = "АктВыполненныхРабот"`
- `ЭтоУниверсальныйДокумент = true`

Table part `Услуги`:
- `LineNumber = "1"`
- `Номенклатура_Key = cf616608-aaef-11ea-b223-b42e99cf3459`
- `Содержание = "Упаковка/Фасовка товаров на складе"`
- `Количество = 1`
- `Цена = 12956834`
- `Сумма = 12956834`
- `СтавкаНДС = "НДС20"`
- `СуммаНДС = 2159472.33`
- `СчетДоходов_Key = 02063683-54e8-11e9-80ee-0050569f2e9f`
- `СчетРасходов_Key = 02063686-54e8-11e9-80ee-0050569f2e9f`
- `СчетУчетаНДСПоРеализации_Key = 02063688-54e8-11e9-80ee-0050569f2e9f`
- `Субконто = 62953114-54e8-11e9-80ee-0050569f2e9f`
- `Субконто_Type = "StandardODATA.Catalog_НоменклатурныеГруппы"`
- `СчетНаОплатуПокупателю_Key = 00000000-0000-0000-0000-000000000000`
- `ИдентификаторСтрокиГосконтрактаЕИС = ""`
- `ИдентификаторСтроки = 8cdc13d0-5545-431b-8faa-a80b69494e71`

## Verification Bug Found and Closed
Первоначально `pool_runtime_verification` для этого run был `failed`, хотя документ в ИБ уже существовал и был полно заполнен.

Установленная причина:
- verifier делал single-entity GET с `$expand`, а 1С отвечает на это `501 The $expand option is not supported when querying single entities`;
- verifier ходил к self-signed HTTPS endpoint с TLS verification по умолчанию.

Исправление:
- single-entity verification path переведён на отдельный `ODataDocumentAdapter` без `$expand`;
- для Python OData adapters введён явный database-scoped override через `Database.metadata.odata_transport.verify_tls`;
- для `stroygrupp_7751284461` baseline bootstrap теперь проставляет `verify_tls = false`.

Повторная ручная post-run verification по тому же `document_plan_artifact` и `PoolPublicationAttempt` после фикса:
- `status = passed`
- `checked_targets = 1`
- `verified_documents = 1`
- `mismatches_count = 0`

## Current Baseline Verdict
Для выбранного first baseline подтверждено end-to-end:
- bootstrap готовит topology + policy + canonical master data + bindings;
- UI actor mapping готов;
- run реально проходит через UI;
- публикация реально создаёт документ в 1С;
- OData verifier после transport fix подтверждает полную заполненность документа без mismatch.
