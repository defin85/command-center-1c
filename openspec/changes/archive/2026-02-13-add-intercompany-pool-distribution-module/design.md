## Context
Нужен отдельный функциональный контур внутри orchestrator для межорганизационного распределения в пуле организаций с публикацией результатов в 1С через OData.

Ограничения и договорённости:
- Справочник организаций master-данные на нашей стороне, с внешней синхронизацией/актуализацией.
- Организация связана с ИБ как `1:1`.
- Пул моделируется как DAG с одним root.
- Multi-parent допустим только для узлов верхнего уровня (прямые дети root).
- Нужна версионность структуры по времени для узлов и рёбер.
- Денежная точность: остаток на последнем узле.
- Итоги должны сходиться строго по суммам (за исключением строк с ошибками источника, которые явно диагностируются).

## Goals / Non-Goals
- Goals:
  - Закрыть foundation домена: каталог организаций, каталоги пулов и версионный граф.
  - Закрыть foundation API/UI: graph view, schema templates, tenant-aware каталог.
  - Синхронизировать public contract `/api/v2/pools/*` с фактической реализацией.
  - Подготовить совместимый фасад для последующего unified execution.
- Non-Goals:
  - Поддержка всех внешних форматов файлов в первом релизе.
  - Сложная многослойная RBAC-модель сверх базовых ролей модуля.
  - Финализация отдельного `pools` runtime исполнения в этом change.
  - Отказ от OData в пользу других каналов публикации.

## Decisions
- Decision: Модуль реализуется как отдельный bounded context внутри orchestrator (отдельные модели/API/сервисы), но использует общую инфраструктуру auth/RBAC/audit.
- Decision: Этот change фиксирует только foundation слой (catalog/data/contracts/UI foundation), не расширяя standalone runtime исполнения.
- Decision: Ограничения распределения (`min/max/weight`) являются каноническими на уровне ребра `parent -> child`; узловые дефолты допускаются только как шаблон заполнения.
- Decision: Идемпотентный ключ run:
  - `pool_id + period + direction + source_hash`.
  - Повторный run по тому же ключу обновляет существующие документы/результаты, не создавая дубликаты.
- Decision: Состояния run:
  - `draft -> validated -> publishing -> partial_success|published|failed`.
  - В этом change фиксируются как vocabulary facade/API; source-of-truth для runtime-проекции задаётся в `refactor-unify-pools-workflow-execution-core`.
- Decision: Safe/unsafe режимы:
  - `safe`: обязательные pre-publish проверки + ручное подтверждение публикации;
  - `unsafe`: пропуск стадии подтверждения пользователем.
- Decision: Публикация выполняется через документы 1С (не прямые записи регистров), с последующим проведением документа на стороне 1С.
- Decision: Частичный успех допустим; для failed-частей используется дозапись с ретраями (`max_attempts=5`, настраиваемый интервал, верхняя граница дефолта 120 секунд).
  - В этом change фиксируется доменный контракт; runtime-исполнение retry/publishing делегировано в `refactor-unify-pools-workflow-execution-core`.
- Decision: Внешний API предоставляется сразу в первом релизе: запуск run, просмотр статуса, повторная дозапись.
- Decision: XLSX-шаблоны являются публичными переиспользуемыми шаблонами (не жёстко привязаны к периоду); допускается опциональная привязка к workflow.
- Decision: Внешний идентификатор документа для OData upsert выбирается strategy-based resolver:
  - primary: стабильный GUID документа из OData (`_IDRRef` или `Ref_Key`);
  - fallback: `ExternalRunKey` (детерминированный ключ вида `runkey-<sha256[:32]>` от `run_id + target_database_id + document_kind + period`).
  - выбранная стратегия и итоговый идентификатор фиксируются в audit trail run.
- Decision: Вопрос совместимости OData endpoint/posting fields закрывается отдельным execution source-of-truth артефактом `openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.md`; foundation change на него ссылается и не переопределяет.
- Decision: Все execution/runtime задачи (фактический run execution, lifecycle orchestration, workflow provenance, unified retry/audit projection) передаются в `refactor-unify-pools-workflow-execution-core`.

## Domain Model (Target)
- `Organization`:
  - мастер-справочник, включая ИНН, статус жизненного цикла, связь `1:1` на ИБ.
- `OrganizationPool`:
  - контейнер графа с единственным root.
- `PoolNodeVersion`:
  - временная версия узла (`effective_from`, `effective_to`).
- `PoolEdgeVersion`:
  - временная версия связи + ограничения распределения (`weight`, `min_amount`, `max_amount`).
- `PoolSchemaTemplate`:
  - публичные XLSX/JSON шаблоны импорта с версией схемы.
- `PoolRun`:
  - ключ run, режим (`safe|unsafe`), направление (`top_down|bottom_up`), период (`month|quarter`), `seed`, статусы, агрегированные метрики.
- `PoolRunLine`:
  - детальные расчётные строки (пара продажа/покупка, суммы, parent/child, source line refs).
- `PoolPublicationAttempt`:
  - попытки публикации по ИБ/пакетам с результатом, ошибками, временем и счётчиком попыток.

## Calculation Flows
### Top-down
1. Выбрать активную версию графа на период.
2. Пройти уровни сверху-вниз.
3. Для каждого ребра рассчитать долю по `weight` с учётом `min/max`.
4. Применить deterministic randomization по `seed`.
5. Остаток округления перенести на последнего child в пределах узла.
6. Сформировать пары продажа/покупка:
  - верхний уровень: только реализация,
  - промежуточные: пары реализация/покупка,
  - нижний: только покупка.

### Bottom-up
1. Импортировать файл (XLSX/JSON) по выбранному шаблону.
2. Валидировать строки по ИНН и активной версии графа.
3. Неизвестные ИНН фиксировать как диагностические ошибки строки, но run не останавливать автоматически.
4. Аггрегировать поток снизу-вверх до root.
5. Сравнить итоги и сформировать отчёт о разбеге/сходимости.
6. Перед публикацией предоставить пользователю решение (продолжить/остановить) при наличии диагностических ошибок.

## Publication Flow
1. Подготовить идемпотентный набор документов к публикации.
2. Для каждой ИБ выполнить OData upsert документов и запрос на проведение.
3. Логировать внешний идентификатор документа и результат проведения.
4. При ошибках применить ретраи по политике.
5. По завершении:
  - все успешны -> `published`,
  - часть успешна -> `partial_success`,
  - все критично провалены -> `failed`.
6. Повторная дозапись работает только по failed/subset целям текущего run.

## External API (High-level)
- `POST /api/v2/pools/runs` — создать/запустить run.
- `GET /api/v2/pools/runs/{run_id}` — получить статус и сводные метрики.
- `POST /api/v2/pools/runs/{run_id}/retry` — повторная дозапись failed-частей.
- `GET /api/v2/pools/runs/{run_id}/report` — сводный + детальный баланс-отчёт.
- `GET|POST /api/v2/pools/schema-templates` — список/создание шаблонов импорта.

## Audit and Retention
- Для каждого run сохраняются:
  - кто запустил, когда, режим, входной источник, `seed`, версия шаблона, итоги валидации, статусы публикации по ИБ.
- Политика хранения:
  - по умолчанию архивирование;
  - `hard delete` допускается отдельным управляемым процессом после ликвидации организации.

## Risks / Trade-offs
- Риск несовместимости способа внешней идентификации документов 1С через OData.
  - Mitigation: strategy-based resolver + обязательный compatibility profile (`openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.md`) как rollout-gate.
- Риск несходимости при ошибках входных данных (неизвестные ИНН).
  - Mitigation: явная диагностика на уровне строки и ручное подтверждение решения.
- Риск повторной записи в частично успешных run.
  - Mitigation: строгий idempotency key и upsert-поведение.

## Open Questions
- Нужен ли отдельный lightweight read-model для каталога организаций в UI до завершения unified runtime refactor.
