## ADDED Requirements

### Requirement: `/pools/catalog` MUST поддерживать template-based topology instantiation для типовых pool схем
Система ДОЛЖНА (SHALL) предоставлять на `/pools/catalog` operator-facing path создания и обновления topology через выбор `topology_template_revision` и назначение concrete организаций в template slot-ы.

Этот path ДОЛЖЕН (SHALL) быть preferred reuse path для типовых новых pool схем, где shape graph повторяется между несколькими `pool`.

Этот change НЕ ДОЛЖЕН (SHALL NOT) требовать automatic in-place conversion already existing pools; template-based path применяется к новым или явно пересозданным после hard reset `pool`.

#### Scenario: Оператор создаёт новый pool из reusable topology template
- **GIVEN** в tenant catalog опубликована активная `topology_template_revision`
- **WHEN** оператор создаёт новый `pool` через `/pools/catalog` и выбирает template-based path
- **THEN** интерфейс предлагает выбрать revision и назначить организации в required slot-ы
- **AND** оператору не нужно вручную собирать все узлы и рёбра заново edge-by-edge

#### Scenario: Existing pool не переводится в template mode как побочный эффект rollout
- **GIVEN** в tenant уже существует `pool`, собранный вручную до появления topology templates
- **WHEN** оператор открывает `/pools/catalog` после rollout
- **THEN** existing `pool` не получает template revision и slot assignments автоматически
- **AND** переход на template-based path требует явного пересоздания или отдельного операторского действия вне этого change

### Requirement: Manual topology authoring MUST оставаться fallback path для нестандартных схем
Система ДОЛЖНА (SHALL) сохранять manual topology editor как fallback/remediation path для нестандартных или разовых схем, которые не укладываются в reusable template.

Manual topology authoring НЕ ДОЛЖЕН (SHALL NOT) оставаться единственным штатным способом тиражирования типовых схем между pool.

#### Scenario: Нестандартная схема всё ещё может быть собрана вручную
- **GIVEN** оператору нужна разовая topology, для которой нет подходящего template
- **WHEN** оператор выбирает manual topology authoring
- **THEN** current snapshot editor остаётся доступным
- **AND** отсутствие подходящего template не блокирует создание или изменение `pool`

### Requirement: Template-based instantiation MUST сохранять concrete graph compatibility с existing read APIs
Система ДОЛЖНА (SHALL) после template-based instantiation возвращать concrete materialized topology через existing `/api/v2/pools/{pool_id}/graph/` и snapshots read endpoints.

Operator-facing graph preview, topology diagnostics и runtime consumers НЕ ДОЛЖНЫ (SHALL NOT) требовать отдельный template-specific read path как единственный источник active pool graph в MVP.

#### Scenario: Graph preview читает concrete topology после template instantiation
- **GIVEN** `pool` был создан или обновлён через template-based instantiation
- **WHEN** оператор открывает graph preview или topology read path
- **THEN** existing graph API возвращает concrete active nodes и edges этого `pool`
- **AND** UI/runtime продолжают работать через current graph contract без дополнительной ручной реконструкции template shape
