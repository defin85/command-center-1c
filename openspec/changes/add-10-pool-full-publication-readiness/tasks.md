## Текущий статус на `2026-03-07`
- Baseline `stroygrupp -> Document_РеализацияТоваровУслуг -> Услуги` подтверждён end-to-end.
- Уже закрыто:
  - deterministic bootstrap для dev;
  - `minimal_documents_full_payload` + fail-closed completeness validation;
  - projection publication attempts + verification status в read-model;
  - OData verifier;
  - backend integration proof;
  - live UI/browser smoke proof.
- Следующая итерация:
  - добить backward compatibility / fail-closed diagnostics для historical runs.
- За пределами текущего baseline, отдельно на следующий scope:
  - variant-aware policy (`entity + ВидОперации`);
  - arithmetic/value-derivation для BP 3.0 derived fields.

## 1. Контракт полноты и readiness
- [x] 1.1 Зафиксировать completeness matrix для целевых document entity (`обязательные header fields`, `обязательные табличные части`, `минимум 1 строка` где требуется).
- [x] 1.2 Добавить machine-readable readiness checklist для run: master-data coverage, Organization->Party bindings, policy completeness, OData verify readiness.
  Подтверждено единым `readiness_checklist` contract в run/report + UI, с fallback для historical payload без silent omission.
- [x] 1.3 Зафиксировать fail-closed коды ошибок и Problem Details для всех readiness блокеров.
  Подтверждено `POOL_RUN_READINESS_BLOCKED` + стабильными blocker codes в `application/problem+json`, read-model и UI.

## 2. Document policy и compile path
- [x] 2.1 Добавить/обновить режим `minimal_documents_full_payload` в compile path.
- [x] 2.2 Реализовать валидацию полноты policy mapping до publication шага (header + table parts).
- [x] 2.3 Заблокировать publication transition при неполном profile/mapping (без silent fallback).

## 3. Master-data readiness
- [x] 3.1 Реализовать проверку обязательного наличия canonical master-data и bindings по publish targets.
  Подтверждено generic runtime guard по publish targets с fail-closed blockers до publication side effects.
- [x] 3.2 Обеспечить операторски читаемый список отсутствующих сущностей/связей для remediation.
  Подтверждено структурированным remediation list для `party/contract/item/binding` в diagnostics/readiness/UI.
- [x] 3.3 Подготовить deterministic bootstrap sequence для dev, чтобы run можно было реально выполнить end-to-end.
  Подтверждено на `default / stroygrupp_7751284461`: bootstrap applied, actor/service mappings валидны, run readiness = `ready_for_ui_run`.

## 4. Projection и отчётность
- [x] 4.1 Исправить projection publication attempts: агрегировать все atomic `publication_odata` nodes из execution result.
- [x] 4.2 Синхронизировать run report/read-model с агрегированными attempts и readiness/verification статусами.
- [ ] 4.3 Сохранить backward compatibility historical runs и fail-closed диагностику.
  Следующий шаг: отдельно добрать historical/legacy payload cases и зафиксировать для них ожидаемую деградацию без silent fallback.

## 5. OData verification
- [x] 5.1 Добавить verifier по published refs с UTF-8 Basic auth.
- [x] 5.2 Проверять соответствие OData-документов completeness matrix (header fields + table parts).
- [x] 5.3 Добавить детерминированный mismatch report для run inspection и тестов.

## 6. UI и прозрачный операторский процесс
- [x] 6.1 Добавить в UI readiness checklist и явную индикацию блокеров до запуска.
- [x] 6.2 Обеспечить live run flow (create/confirm/retry/report) через реальные API без моков для acceptance.
  Подтверждено run `ca4f7da6-298a-4536-bbdd-278102162f3d` + execution `b1c67191-71d9-4c96-8c8d-f50f3c0f297c`; details в `artifacts/stroygrupp-ui-run-verified-2026-03-06.md`.
- [x] 6.3 Отобразить verification summary и remediation hints в run inspection.

## 7. Верификация и качество
- [x] 7.1 Написать red backend integration tests для полного цикла top-down run с проверкой read-model.
  Подтверждено тестом `apps/api_v2/tests/test_intercompany_pool_runs.py::test_top_down_pool_run_read_model_projects_publication_attempts_and_verification_after_internal_completion`.
- [x] 7.2 Написать red/green tests для OData verifier (UTF-8 auth + completeness checks).
- [x] 7.3 Добавить live browser e2e тест для dev acceptance сценария через UI.
  Подтверждено env-gated Playwright spec `frontend/tests/browser/pools-live-publication-smoke.spec.ts`.
- [x] 7.4 Прогнать релевантные тесты/линтеры и приложить матрицу `Requirement -> Code -> Test`.
  Подтверждено командами:
  - `./scripts/dev/pytest.sh -q apps/api_v2/tests/test_intercompany_pool_runs.py -k top_down_pool_run_read_model_projects_publication_attempts_and_verification_after_internal_completion`
  - `cd frontend && npm test -- --run src/pages/Pools/__tests__/PoolRunsPage.test.tsx`
  - `cd frontend && CC1C_POOLS_LIVE=1 CC1C_POOLS_LIVE_USERNAME=admin CC1C_POOLS_LIVE_PASSWORD='p-123456' npm exec playwright test tests/browser/pools-live-publication-smoke.spec.ts`
  Матрица и live evidence сохранены в `artifacts/stroygrupp-live-smoke-2026-03-07.md`.
