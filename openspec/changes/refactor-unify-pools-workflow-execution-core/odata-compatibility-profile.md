# OData Compatibility Profile (Unified Pools Publication)

## Purpose
Этот профиль является source-of-truth для production rollout шага `publication_odata` в unified execution core.

Rollout ДОЛЖЕН (SHALL) быть заблокирован (`No-Go`), если для целевой 1С-конфигурации отсутствует утверждённая запись в этом профиле.

## Ownership and Versioning
- Owner: `platform + pools` (совместная ответственность за актуальность profile и rollout gate).
- Текущая версия профиля: `0.1.0-draft`.
- Версионирование: `MAJOR.MINOR.PATCH`.
  - `MAJOR`: несовместимое изменение schema/profile policy.
  - `MINOR`: добавление новой конфигурации или нового поддерживаемого паттерна endpoint/posting.
  - `PATCH`: редакционные правки без изменения rollout-решения.
- Любой production rollout unified publication ДОЛЖЕН (SHALL) фиксировать используемую `profile_version` в release-артефактах.

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
| (to be filled) | (to be filled) | (to be filled) | (to be filled) | Ref_Key -> _IDRRef -> ExternalRunKey | (to be filled) | (to be filled) | v1 | (to be filled) | draft | - | - |

## Rollout Gate
`publication_odata` rollout in production разрешён только если:
- для каждой target configuration есть строка в таблице выше;
- `verification_status=approved`;
- подтверждена стратегия fallback на `ExternalRunKey`;
- соответствующая запись не помечена как deprecated/unsupported;
- release-пакет ссылается на конкретную `profile_version`.

## Change Control
- Любое изменение endpoint/posting fields требует обновления этой таблицы в том же change-set, что и runtime-код/контракт.
- Изменения profile обязаны:
  - обновлять `profile_version` согласно правилам выше;
  - обновлять `profile_entry_version` затронутых строк;
  - добавлять `source_reference` на проверяющий артефакт.
- Для неоднозначных расхождений с источниками документации решение принимается в пользу более консервативного режима (`No-Go`) до подтверждения profile.

## Change Log
| profile_version | date | summary |
| --- | --- | --- |
| 0.1.0-draft | 2026-02-13 | Initial profile contract, rollout gate, schema and versioning rules. |
