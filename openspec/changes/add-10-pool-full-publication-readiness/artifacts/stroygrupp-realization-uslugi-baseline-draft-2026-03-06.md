# `stroygrupp` Baseline Draft: `Document_РеализацияТоваровУслуг -> Услуги`

## Scope
Этот артефакт фиксирует первый практический baseline для dev acceptance после живого OData исследования базы:
- infobase: `stroygrupp_7751284461`
- entity: `Document_РеализацияТоваровУслуг`
- operation variant: `ВидОперации = Услуги`
- required table part: `Услуги`

Цель baseline:
- получить минимальный по количеству документов, но полно заполненный BP 3.0 payload;
- собрать первый исполнимый `document_policy` draft под текущий DSL;
- явно зафиксировать, что уже работает, а что ещё блокирует универсальный сервисный слой.

## Golden Sample
Источник: живой документ из OData:
- `Document_РеализацияТоваровУслуг(Ref_Key=guid'2d3209c4-50ce-11f0-904c-bbb30f628b54')`

Header sample:
- `ВидОперации = "Услуги"`
- `Организация_Key = 789df375-0873-11ea-a5d4-0c9d92779da8`
- `Контрагент_Key = e28bd6fe-50c9-11f0-904c-bbb30f628b54`
- `ДоговорКонтрагента_Key = f77692fd-50ca-11f0-904c-bbb30f628b54`
- `СпособЗачетаАвансов = "Автоматически"`
- `ВалютаДокумента_Key = 171b30af-54e8-11e9-80ee-0050569f2e9f` (`руб.`)
- `КурсВзаиморасчетов = 1`
- `КратностьВзаиморасчетов = 1`
- `СуммаВключаетНДС = true`
- `СчетУчетаРасчетовСКонтрагентом_Key = 020635d6-54e8-11e9-80ee-0050569f2e9f` (`62.01`)
- `СчетУчетаРасчетовПоАвансам_Key = 020635d7-54e8-11e9-80ee-0050569f2e9f` (`62.02`)
- `СуммаДокумента = 12956834`
- `ВидЭлектронногоДокумента = "АктВыполненныхРабот"`
- `ЭтоУниверсальныйДокумент = true`

У этой реализации ровно одна строка `Услуги`:
- `Номенклатура_Key = cf616608-aaef-11ea-b223-b42e99cf3459` (`Упаковка/Фасовка товаров на складе`)
- `Содержание = "Упаковка/Фасовка товаров на складе"`
- `Количество = 1`
- `Цена = 12956834`
- `Сумма = 12956834`
- `СтавкаНДС = "НДС20"`
- `СуммаНДС = 2159472.33`
- `СчетДоходов_Key = 02063683-54e8-11e9-80ee-0050569f2e9f` (`90.01.1`)
- `СчетРасходов_Key = 02063686-54e8-11e9-80ee-0050569f2e9f` (`90.02.1`)
- `СчетУчетаНДСПоРеализации_Key = 02063688-54e8-11e9-80ee-0050569f2e9f` (`90.03`)
- `Субконто = "62953114-54e8-11e9-80ee-0050569f2e9f"` (`НоменклатурныеГруппы: Услуги`)
- `Субконто_Type = "StandardODATA.Catalog_НоменклатурныеГруппы"`

Связанные master-data объекты из OData:
- организация: `СТРОЙГРУПП ООО`, `ИНН 7751284461`
- контрагент: `ПРОЭКТ СТ ООО`, `ИНН 9701309107`
- договор: `Основной`, `ВидДоговора = СПокупателем`
- номенклатура: `Упаковка/Фасовка товаров на складе`
- номенклатурная группа: `Услуги`

## Current DSL Fit
Текущий `document_policy` DSL уже позволяет собрать значительную часть baseline:
- literals: строки, числа, bool, вложенные objects/lists;
- `allocation.<path>`;
- `*.ref` для документных ссылок;
- `master_data.party.*.ref`, `master_data.contract.*.ref`, `master_data.item.*.ref`, `master_data.tax_profile.*.ref`.

После текущей правки runtime больше не инжектит несуществующее generic поле `Amount` в BP payload и fail-closed проверяет обязательные header fields из completeness profile.

## Executable-Now Draft Policy
Ниже черновик policy, который совместим с текущим DSL.

Ограничение:
- в таком виде он исполним только для фиксированного baseline amount `12956834.00`, потому что `СуммаНДС` пока нельзя вычислить из `allocation.amount`.

```json
{
  "version": "document_policy.v1",
  "chains": [
    {
      "chain_id": "stroygrupp_realization_services_baseline",
      "documents": [
        {
          "document_id": "sale",
          "entity_name": "Document_РеализацияТоваровУслуг",
          "document_role": "sale",
          "invoice_mode": "optional",
          "field_mapping": {
            "ВидОперации": "Услуги",
            "Организация_Key": "master_data.party.stroygrupp.organization.ref",
            "Контрагент_Key": "master_data.party.proekt-st.counterparty.ref",
            "ДоговорКонтрагента_Key": "master_data.contract.osnovnoy.proekt-st.ref",
            "СпособЗачетаАвансов": "Автоматически",
            "ВалютаДокумента_Key": "171b30af-54e8-11e9-80ee-0050569f2e9f",
            "КурсВзаиморасчетов": 1,
            "КратностьВзаиморасчетов": 1,
            "СуммаВключаетНДС": true,
            "СчетУчетаРасчетовСКонтрагентом_Key": "020635d6-54e8-11e9-80ee-0050569f2e9f",
            "СчетУчетаРасчетовПоАвансам_Key": "020635d7-54e8-11e9-80ee-0050569f2e9f",
            "СуммаДокумента": "allocation.amount",
            "ВидЭлектронногоДокумента": "АктВыполненныхРабот",
            "ЭтоУниверсальныйДокумент": true
          },
          "table_parts_mapping": {
            "Услуги": [
              {
                "Номенклатура_Key": "master_data.item.packing-service.ref",
                "Содержание": "Упаковка/Фасовка товаров на складе",
                "Количество": 1,
                "Цена": "allocation.amount",
                "Сумма": "allocation.amount",
                "СтавкаНДС": "НДС20",
                "СуммаНДС": 2159472.33,
                "СчетДоходов_Key": "02063683-54e8-11e9-80ee-0050569f2e9f",
                "СчетРасходов_Key": "02063686-54e8-11e9-80ee-0050569f2e9f",
                "СчетУчетаНДСПоРеализации_Key": "02063688-54e8-11e9-80ee-0050569f2e9f",
                "Субконто": "62953114-54e8-11e9-80ee-0050569f2e9f",
                "Субконто_Type": "StandardODATA.Catalog_НоменклатурныеГруппы"
              }
            ]
          },
          "link_rules": {}
        }
      ]
    }
  ],
  "completeness_profiles": {
    "minimal_documents_full_payload": {
      "entities": {
        "Document_РеализацияТоваровУслуг": {
          "required_fields": [
            "ВидОперации",
            "Организация_Key",
            "Контрагент_Key",
            "ДоговорКонтрагента_Key",
            "СпособЗачетаАвансов",
            "ВалютаДокумента_Key",
            "КурсВзаиморасчетов",
            "КратностьВзаиморасчетов",
            "СуммаВключаетНДС",
            "СчетУчетаРасчетовСКонтрагентом_Key",
            "СчетУчетаРасчетовПоАвансам_Key",
            "СуммаДокумента",
            "ВидЭлектронногоДокумента",
            "ЭтоУниверсальныйДокумент"
          ],
          "required_table_parts": {
            "Услуги": {
              "min_rows": 1,
              "required_fields": [
                "Номенклатура_Key",
                "Содержание",
                "Количество",
                "Цена",
                "Сумма",
                "СтавкаНДС",
                "СуммаНДС",
                "СчетДоходов_Key",
                "СчетРасходов_Key",
                "СчетУчетаНДСПоРеализации_Key",
                "Субконто",
                "Субконто_Type"
              ]
            }
          }
        }
      }
    }
  }
}
```

## Confirmed Blockers
### 1. No arithmetic/derived-value DSL
Текущий compile/publication mapping не умеет вычислять производные значения наподобие:
- `СуммаНДС = allocation.amount / 6`
- потенциально будущие derived totals / quantity * price

Следствие:
- первый baseline сегодня можно сделать только как fixed-amount scenario;
- для общего решения нужен либо arithmetic DSL, либо отдельный resolver для типовых BP derived fields.

### 2. Master-data token coverage is narrower than BP payload needs
Сейчас service-layer токенизирует:
- `party`
- `contract`
- `item`
- `tax_profile`

Этого недостаточно для универсального BP payload, где часто нужны:
- `ВалютаДокумента_Key`
- бухгалтерские счета (`62.01`, `62.02`, `90.01.1`, `90.02.1`, `90.03`)
- субконто/аналитики
- иногда сотрудники/склады/типы цен

Следствие:
- для первого baseline допустимы literals/IB refs;
- для production-like rollout потребуется расширение canonical master-data surface.

### 3. Canonical bootstrap is still missing for the selected live objects
Чтобы этот draft стал реально исполнимым через `master_data.*.ref`, в dev надо создать и связать как минимум:
- `party.stroygrupp` -> role `organization`
- `party.proekt-st` -> role `counterparty`
- `contract.osnovnoy.proekt-st` -> owner `party.proekt-st`
- `item.packing-service`

Пока этого нет, master-data gate корректно остановит run.

## Immediate Actionable Path
1. Зафиксировать fixed-amount acceptance для `starting_amount = 12956834.00`.
2. Подготовить canonical master data и bindings для 4 объектов из списка выше.
3. Подложить этот policy в `edge.metadata.document_policy`.
4. Прогнать run через UI на single-edge topology (`weight = 1`).
5. Проверить OData verifier, что создан ровно один `Document_РеализацияТоваровУслуг` с одной строкой `Услуги`.
