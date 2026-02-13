# OData Compatibility Profile (Unified Pools Publication)

## Purpose
Этот профиль является source-of-truth для production rollout шага `publication_odata` в unified execution core.

Rollout ДОЛЖЕН (SHALL) быть заблокирован (`No-Go`), если для целевой 1С-конфигурации отсутствует утверждённая запись в этом профиле.

## Ownership and Versioning
- Owner: `platform + pools` (совместная ответственность за актуальность profile и rollout gate).
- Текущая версия профиля: `0.4.1-draft`.
- Версионирование: `MAJOR.MINOR.PATCH`.
  - `MAJOR`: несовместимое изменение schema/profile policy.
  - `MINOR`: добавление новой конфигурации или нового поддерживаемого паттерна endpoint/posting.
  - `PATCH`: редакционные правки без изменения rollout-решения.
- Любой production rollout unified publication ДОЛЖЕН (SHALL) фиксировать используемую `profile_version` в release-артефактах.

## Normative References (kb.1ci.com)
- JSON format and media types: `17.4.7. JSON format`:
  - https://kb.1ci.com/1C_Enterprise_Platform/Guides/Developer_Guides/1C_Enterprise_8.3.23_Developer_Guide/Chapter_17._Integration_with_external_systems/17.4._Standard_OData_interface/17.4.7._JSON_format/
- OData access methods and request patterns: `17.4.8. Methods of accessing data`:
  - https://kb.1ci.com/1C_Enterprise_Platform/Guides/Developer_Guides/1C_Enterprise_8.3.23_Developer_Guide/Chapter_17._Integration_with_external_systems/17.4._Standard_OData_interface/17.4.8._Methods_of_accessing_data/
- OData modify methods and expected HTTP semantics: `17.4.9. Methods of modifying data`:
  - https://kb.1ci.com/1C_Enterprise_Platform/Guides/Developer_Guides/1C_Enterprise_8.3.23_Developer_Guide/Chapter_17._Integration_with_external_systems/17.4._Standard_OData_interface/17.4.9._Methods_of_modifying_data/

## Profile Schema
Для каждой поддерживаемой конфигурации фиксируются:
- `configuration_id` (stable identifier),
- `configuration_version_range` (supported version range),
- `document_upsert_endpoint_pattern`,
- `document_posting_operation` (endpoint/action + required fields),
- `document_identity_fields_priority` (например: `Ref_Key`, `_IDRRef`, `ExternalRunKey`),
- `external_run_key_field`,
- `known_limitations`,
- `profile_entry_version` (локальная версия записи, `vN`),
- `source_reference` (ссылка на подтверждающий артефакт: spike/protocol/test evidence),
- `verification_status` (`draft|verified|approved`),
- `verified_at`,
- `verified_by`.

## Supported Configurations
| configuration_id | configuration_version_range | document_upsert_endpoint_pattern | document_posting_operation | document_identity_fields_priority | external_run_key_field | known_limitations | profile_entry_version | source_reference | verification_status | verified_at | verified_by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cc1c-internal-test-double-intercompany-doc | n/a (internal test baseline) | `/odata/standard.odata/Document_IntercompanyPoolDistribution` | `PATCH Document_IntercompanyPoolDistribution(guid'{Ref_Key}')` body: `{"Posted": true}` | Ref_Key -> _IDRRef -> ExternalRunKey | ExternalRunKey | Используется в автотестах как internal test-double; в типовой БП 3.0 такой document entity может отсутствовать | v1 | `orchestrator/apps/intercompany_pools/publication.py`; `orchestrator/apps/intercompany_pools/tests/test_publication.py`; `contracts/orchestrator/openapi.yaml` | verified | 2026-02-13 | automated-test-baseline |
| 1c-accounting-3.0-standard-odata | 3.0.x (Sokolniki_7714476359 baseline) | `/odata/standard.odata/Document_РеализацияТоваровУслуг` | `PATCH Document_РеализацияТоваровУслуг(guid'{Ref_Key}')` body: `{"Posted": true}` (runtime JSON headers: `application/json;odata=nometadata`) | Ref_Key -> _IDRRef -> ExternalRunKey | ExternalRunKey (or mapped extension field) | Legacy compatibility mode (`<=8.3.7`) requires dedicated JSON write policy per KB `17.4.7`; this baseline rejects `application/json;odata=verbose` for write (`406`) and uses `application/json;odata=nometadata`; DELETE may require elevated rights (`Последовательность.ДокументыОрганизаций`) | v4 | `openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-verification-2026-02-13-sokolniki.md`; `orchestrator/apps/databases/odata/client.py`; KB refs `17.4.7/17.4.8/17.4.9` | approved | 2026-02-13 | production-like-check (Sokolniki_7714476359) |

## Rollout Gate
`publication_odata` rollout in production разрешён только если:
- для каждой target configuration есть строка в таблице выше;
- `verification_status=approved`;
- подтверждена стратегия fallback на `ExternalRunKey`;
- preflight подтверждает совместимость compatibility mode целевой ИБ и media-type policy профиля (legacy `<=8.3.7` не может использовать runtime JSON policy без отдельной approved записи);
- соответствующая запись не помечена как deprecated/unsupported;
- release-пакет ссылается на конкретную `profile_version`.

## Change Control
- Любое изменение endpoint/posting fields требует обновления этой таблицы в том же change-set, что и runtime-код/контракт.
- Изменения profile обязаны:
  - обновлять `profile_version` согласно правилам выше;
  - обновлять `profile_entry_version` затронутых строк;
  - добавлять `source_reference` на проверяющий артефакт.
- Для неоднозначных расхождений с источниками документации решение принимается в пользу более консервативного режима (`No-Go`) до подтверждения profile.

## Verification Policy
- `draft`:
  - есть только проектный контракт без подтверждения кодом/тестами.
- `verified`:
  - endpoint/posting-паттерн подтверждён кодом и автоматизированными тестами;
  - есть `source_reference` на реализацию и тесты.
- `approved`:
  - дополнительно к `verified` выполнена проверка на целевой production-like конфигурации 1С;
  - есть подтверждённый rollout протокол и владелец-аппрувер (platform/pools).
  - runtime-path публикации совместим с transport/format требованиями записи целевой конфигурации.

## Target Eligibility Rule
- Статус `verified` на internal test-double записи НЕ является основанием для production rollout.
- Для production rollout обязательна запись именно для целевой 1С-конфигурации (например, `1c-accounting-3.0-standard-odata`) со статусом `approved`.

## Change Log
| profile_version | date | summary |
| --- | --- | --- |
| 0.4.1-draft | 2026-02-13 | Aligned profile with KB 17.4.7/17.4.8/17.4.9 and added explicit compatibility-mode/media-type preflight gate. |
| 0.4.0-draft | 2026-02-13 | Confirmed runtime JSON write compatibility for BP 3.0 baseline and promoted target entry to approved; replaced false Atom-only constraint. |
| 0.3.0-draft | 2026-02-13 | Added real BP 3.0 baseline entry from Sokolniki metadata/probe and documented write-format constraint (Atom XML required). |
| 0.2.0-draft | 2026-02-13 | Split internal test baseline vs target BP 3.0; downgraded target entry to draft until real metadata mapping and production-like verification. |
| 0.1.0-draft | 2026-02-13 | Initial profile contract, rollout gate, schema and versioning rules. |
