## 1. Metadata catalog UTF-8 auth path
- [ ] 1.1 Убрать pre-validation `latin-1` reject в `metadata_catalog` и перейти на явное формирование Basic header из `UTF-8(username:password)`.
- [ ] 1.2 Сохранить mapping-only поведение для metadata path (`InfobaseUserMapping` only, без fallback на `Database.username/password`).
- [ ] 1.3 Обновить error mapping для metadata fetch: non-latin credentials не должны возвращать локальную конфигурационную ошибку до запроса.

## 2. Publication transport UTF-8 consistency
- [ ] 2.1 Зафиксировать и проверить, что credentials из orchestrator transport доходят до worker без потери Unicode-символов.
- [ ] 2.2 Для worker OData client явно зафиксировать поведение Basic auth для UTF-8 credentials и отсутствие lossy normalization/transliteration.
- [ ] 2.3 Добавить тест-кейсы actor/service с кириллицей в `username/password` для publication path.

## 3. Tests and regression gates
- [ ] 3.1 Обновить backend API тесты metadata catalog: кириллица в mapping должна доходить до HTTP запроса, а не отклоняться на client-side encoding.
- [ ] 3.2 Добавить/обновить worker тесты на формирование Authorization header для Unicode credentials.
- [ ] 3.3 Добавить регрессионные тесты на ASCII/latin-1 credentials, чтобы подтвердить backward compatibility.

## 4. Contracts and rollout
- [ ] 4.1 Обновить OpenSpec-дельты и связанный rollout note (ограничения, security expectations, диагностика ошибок).
- [ ] 4.2 Прогнать целевые тесты orchestrator/worker и зафиксировать результаты.
- [ ] 4.3 Прогнать `openspec validate add-04-odata-utf8-credentials --strict --no-interactive`.
