## MODIFIED Requirements

### Requirement: `/templates` MUST использовать canonical template management workspace

Система ДОЛЖНА (SHALL) представлять `/templates` как template management workspace с route-addressable selected template/filter context и canonical authoring surfaces для create/edit/inspect flows.

На desktop primary master pane ДОЛЖЕН (SHALL) оставаться compact template catalog, который помогает быстро выбрать template и увидеть короткий execution/publish summary. Wide provenance grid, много-колоночная table-first composition и horizontal overflow НЕ ДОЛЖНЫ (SHALL NOT) быть default primary path в master pane.

Template provenance, publish/access state и richer execution contract ДОЛЖНЫ (SHALL) жить в detail pane или canonical secondary surfaces, чтобы detail surface объяснял "что именно будет выполнено" без перегрузки primary catalog.

#### Scenario: Template workspace восстанавливает selected template context из URL

- **GIVEN** оператор открывает `/templates` с query state, указывающим фильтры и выбранный template
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же template context
- **AND** primary create/edit flow использует canonical secondary surface внутри platform workspace

#### Scenario: Desktop template workspace показывает compact catalog вместо wide provenance table

- **GIVEN** оператор открывает `/templates` на desktop viewport
- **WHEN** route рендерит primary template catalog
- **THEN** master pane остаётся compact selection surface с коротким publish/executor summary
- **AND** primary catalog не превращается в wide provenance table с horizontal overflow

#### Scenario: Provenance и publish actions живут в detail surface

- **GIVEN** оператор выбрал template в catalog
- **WHEN** он inspect-ит execution contract, publish/access posture или provenance binding
- **THEN** detail surface показывает эти данные и связанные primary actions
- **AND** оператору не требуется читать wide master-pane grid как единственный источник этой информации

## REMOVED Requirements

### Requirement: `/templates` list MUST прозрачно показывать provenance template binding

**Reason**: compact `catalog-detail` normalisation убирает provenance-heavy list/table как default primary master-pane path для `/templates`.

**Migration**: master pane сохраняет только короткий execution/publish summary для scan/select, а exposure id, revision, publish/access posture и richer execution contract переходят в detail pane или canonical secondary surfaces.
