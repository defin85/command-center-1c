## 1. Контракт полноты и readiness
- [ ] 1.1 Зафиксировать completeness matrix для целевых document entity (`обязательные header fields`, `обязательные табличные части`, `минимум 1 строка` где требуется).
- [ ] 1.2 Добавить machine-readable readiness checklist для run: master-data coverage, Organization->Party bindings, policy completeness, OData verify readiness.
- [ ] 1.3 Зафиксировать fail-closed коды ошибок и Problem Details для всех readiness блокеров.

## 2. Document policy и compile path
- [ ] 2.1 Добавить/обновить режим `minimal_documents_full_payload` в compile path.
- [ ] 2.2 Реализовать валидацию полноты policy mapping до publication шага (header + table parts).
- [ ] 2.3 Заблокировать publication transition при неполном profile/mapping (без silent fallback).

## 3. Master-data readiness
- [ ] 3.1 Реализовать проверку обязательного наличия canonical master-data и bindings по publish targets.
- [ ] 3.2 Обеспечить операторски читаемый список отсутствующих сущностей/связей для remediation.
- [ ] 3.3 Подготовить deterministic bootstrap sequence для dev, чтобы run можно было реально выполнить end-to-end.

## 4. Projection и отчётность
- [ ] 4.1 Исправить projection publication attempts: агрегировать все atomic `publication_odata` nodes из execution result.
- [ ] 4.2 Синхронизировать run report/read-model с агрегированными attempts и readiness/verification статусами.
- [ ] 4.3 Сохранить backward compatibility historical runs и fail-closed диагностику.

## 5. OData verification
- [ ] 5.1 Добавить verifier по published refs с UTF-8 Basic auth.
- [ ] 5.2 Проверять соответствие OData-документов completeness matrix (header fields + table parts).
- [ ] 5.3 Добавить детерминированный mismatch report для run inspection и тестов.

## 6. UI и прозрачный операторский процесс
- [ ] 6.1 Добавить в UI readiness checklist и явную индикацию блокеров до запуска.
- [ ] 6.2 Обеспечить live run flow (create/confirm/retry/report) через реальные API без моков для acceptance.
- [ ] 6.3 Отобразить verification summary и remediation hints в run inspection.

## 7. Верификация и качество
- [ ] 7.1 Написать red backend integration tests для полного цикла top-down run с проверкой read-model.
- [ ] 7.2 Написать red/green tests для OData verifier (UTF-8 auth + completeness checks).
- [ ] 7.3 Добавить live browser e2e тест для dev acceptance сценария через UI.
- [ ] 7.4 Прогнать релевантные тесты/линтеры и приложить матрицу `Requirement -> Code -> Test`.
