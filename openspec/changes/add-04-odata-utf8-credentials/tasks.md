## 1. Metadata catalog UTF-8 auth path
- [x] 1.1 Убрать pre-validation `latin-1` reject в `metadata_catalog` и перейти на явное формирование Basic header из `UTF-8(username:password)`.
- [x] 1.2 Сохранить mapping-only поведение для metadata path (`InfobaseUserMapping` only, без fallback на `Database.username/password`).
- [x] 1.3 Обновить error mapping для metadata fetch: non-latin credentials не должны возвращать локальную конфигурационную ошибку до запроса.
- [x] 1.4 Явно зафиксировать и покрыть тестом классификацию metadata auth-ошибок: `401/403` от endpoint => `ODATA_MAPPING_NOT_CONFIGURED`.

## 2. Publication transport UTF-8 consistency
- [x] 2.1 Зафиксировать и проверить, что credentials из orchestrator transport доходят до worker без потери Unicode-символов.
- [x] 2.2 Для worker OData client явно зафиксировать поведение Basic auth для UTF-8 credentials и отсутствие lossy normalization/transliteration.
- [x] 2.3 Добавить тест-кейсы actor/service с кириллицей в `username/password` для publication path.

## 3. Tests and regression gates
- [x] 3.1 Обновить backend API тесты metadata catalog: кириллица в mapping должна доходить до HTTP запроса, а не отклоняться на client-side encoding; проверить `Authorization` как Base64 от UTF-8 `username:password`.
- [x] 3.2 Добавить/обновить worker тесты на формирование Authorization header для Unicode credentials (и отдельно для `actor`, и для `service` strategy).
- [x] 3.3 Добавить регрессионные тесты на ASCII/latin-1 credentials, чтобы подтвердить backward compatibility.

## 4. Contracts and rollout
- [x] 4.1 Обновить OpenSpec-дельты и связанный rollout note (ограничения, security expectations, диагностика ошибок, TLS-only no-go правило).
- [x] 4.2 Прогнать целевые тесты orchestrator/worker и зафиксировать результаты.
- [x] 4.3 Прогнать `openspec validate add-04-odata-utf8-credentials --strict --no-interactive`.
