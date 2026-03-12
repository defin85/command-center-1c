## Контекст
`/decisions` уже умеет создавать новую revision из существующей через обычный edit/revise flow и текущий `POST /api/v2/decisions`.

После `update-business-configuration-identity-for-decision-reuse` default compatible list должен определяться business identity `config_name + config_version`, а не `metadata_hash` или именем ИБ. Это означает, что same-release revisions между ИБ одной конфигурации должны оставаться видимыми по умолчанию.

Проблема не в отсутствии базового механизма, а в отсутствии явного UX-контракта для сценария "после обновления ИБ перевыпустить policy под новый релиз, используя revision предыдущего релиза как исходник". Сейчас этот сценарий требует знания внутренней mechanics revise flow и source picking.

## Цели
- Дать аналитику явный и discoverable flow для rollover `decision_revision` под выбранную ИБ.
- Переиспользовать существующий backend publish path и не вводить новый API, если текущего контракта достаточно.
- Сохранить fail-closed validation против target metadata snapshot.
- Сохранить неизменность старых revisions и pinned consumers.

## Не-цели
- Автоматическое создание новой revision при каждом обновлении ИБ.
- Автоматическая массовая перепривязка workflow bindings, workflow definitions или runtime projections на новую revision.
- Ослабление metadata-aware validation ради convenience UX.
- Изменение текущей модели immutable decision revisions.

## Решения
### Decision 1: Строим guided rollover flow поверх существующего `/api/v2/decisions`
Новая UX-точка входа должна использовать уже существующий контракт публикации revision:
- `parent_version_id` задаёт source revision;
- `database_id` задаёт target metadata context;
- payload policy остаётся обычным decision authoring payload.

Почему:
- backend уже умеет создавать новую revision и сохранять target metadata context в resulting revision;
- минимизируется риск архитектурного дублирования и drift между двумя publish path;
- UI change остаётся локальным и обратимым.

### Decision 2: Revision вне target compatible set допускаются как source-only candidates
Default compatible selection должен оставаться aligned с active business-identity contract: same-release compatible revisions остаются видимыми по умолчанию и не переводятся в hidden state только из-за publication drift или другого имени ИБ.

Но для rollover flow аналитик должен иметь явную возможность выбрать revision вне target compatible set как source. Практический случай для этого flow: source revision предыдущего релиза используется как seed для target database с новым релизом.

Практически это означает:
- revision вне target compatible set не становится "подходящей" автоматически;
- UI должен отличать source selection от ready-to-pin selection;
- после выбора source revision editor открывается уже в target database context.

### Decision 3: Publish остаётся fail-closed относительно target snapshot
Использование старой revision как source не означает compatibility с новой ИБ. На publish path система обязана повторно валидировать policy против resolved metadata snapshot выбранной ИБ и создавать новую revision только при успешной валидации.

Это удерживает корректную семантику:
- source revision используется как editable seed;
- target revision получает собственный auditable metadata context;
- старая revision не мутируется и не теряет исходную provenance.

### Decision 4: Flow не обновляет consumers автоматически
Rollover flow должен завершаться созданием новой revision и показом resulting decision ref. Любая перепривязка consumers остаётся отдельным осознанным действием.

Почему:
- `decision_revision` пинится явно в bindings/workflow references;
- автопереключение увеличивает blast radius и смешивает authoring с rollout;
- это отдельная change-область с собственными рисками и acceptance criteria.

## Риски и компромиссы
- Риск: аналитик может ожидать, что новая revision автоматически заменит старую везде.
  - Mitigation: явный copy в UI и spec-level запрет на auto-rebind.
- Риск: source-picking для предыдущего релиза усложнит экран `/decisions`.
  - Mitigation: сохранить default compatible selection как основной mode и делать rollover flow explicit, а не always-on.
- Риск: overlapping work с `update-business-configuration-identity-for-decision-reuse`, который меняет compatibility/filtering semantics.
  - Mitigation: строить rollover поверх business-identity matching и использовать source mode только для revisions вне target compatible set.

## План миграции
1. Добавить explicit source-target UX contract в `/decisions`.
2. Переиспользовать текущий revise/save path без нового backend endpoint.
3. Обновить frontend tests на сценарии previous-release source revision -> new target revision.
4. Синхронизировать copy/layout с business-identity compatibility contract из связанного active change.
