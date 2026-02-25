## Context
В текущей реализации metadata catalog path есть искусственное ограничение на `latin-1`:
- `orchestrator/apps/intercompany_pools/metadata_catalog.py` делает `username.encode("latin-1")`/`password.encode("latin-1")` и отклоняет запрос до HTTP round-trip.
- API-тест `test_get_pool_odata_metadata_catalog_rejects_non_latin1_mapping_credentials` закрепляет это поведение как ожидаемое.

В то же время:
- 1C docs для web authentication указывают ожидание передачи username/password в UTF-8.
- RFC 7617 фиксирует, что default encoding исторически неоднозначен, но сервер может явно требовать UTF-8 через `charset="UTF-8"`.
- `requests` в `_basic_auth_str` кодирует строковые username/password через `latin1`, что и создаёт практический блок для кириллицы.

## Goals / Non-Goals
- Goals:
  - убрать искусственный запрет на кириллицу/Unicode credentials в OData metadata path;
  - зафиксировать сквозной UTF-8-safe контракт credentials transport + worker OData auth;
  - сохранить fail-closed semantics и mapping-only auth policy.
- Non-Goals:
  - не добавлять multi-encoding negotiation/fallback matrix (latin-1, cp1251 и т.д.);
  - не менять RBAC domain-модель credentials.

## Decisions
### Decision 1: Metadata path формирует Basic header явно из UTF-8
`metadata_catalog` не использует `requests`-auth tuple для credentials.
Вместо этого система формирует:
- `raw = f"{username}:{password}".encode("utf-8")`
- `Authorization = "Basic " + base64(raw)`

Это снимает зависимость от `requests` latin1 поведения и позволяет передавать кириллицу/Unicode credentials в endpoint.

### Decision 2: Publication path контракт фиксируется как UTF-8-safe
Для `pool.publication_odata` credentials из mapping (actor/service) должны сохраняться без потерь до HTTP-клиента worker.
Проверка делается тестами на реальный Authorization header, чтобы исключить:
- lossy normalization;
- transliteration;
- silent truncation.

### Decision 3: Backward compatibility = keep ASCII, remove false-negative non-latin reject
ASCII/latin-1 credentials продолжают работать без изменений.
Поведение, где non-latin credentials отклоняются локально до запроса, удаляется как false-negative.

### Decision 4: Failure semantics остаются fail-closed
Если OData endpoint отклоняет credentials (401/403), система продолжает возвращать fail-closed machine-readable ошибку (`ODATA_MAPPING_NOT_CONFIGURED` для metadata path), но без ложной причины "unsupported latin-1".

## Risks / Trade-offs
- Риск: часть старых HTTP intermediaries может иметь нестандартные ожидания по Basic auth байтам.
  - Mitigation: scoped rollout, staging checks на реальных 1C окружениях, явная диагностика `401/403`.
- Риск: неочевидная разница между endpoint reject и локальной encoding ошибкой может повлиять на операционные playbook.
  - Mitigation: обновить rollout note и troubleshooting (что проверять в `/rbac` и на стороне web server/1C publication).

## Migration and Rollout
1. Обновить metadata auth implementation на explicit UTF-8 Basic header.
2. Переписать тест, который сейчас проверяет reject non-latin1, на проверку корректной передачи UTF-8 Authorization.
3. Добавить worker тесты для actor/service Unicode credentials.
4. Выполнить staging прогон с кириллическим service user в metadata refresh и publication.
5. После подтверждения перевести change в implementation phase.

## References
- 1C Knowledge Base, Authentication (UTF-8 expectation for username/password):  
  https://kb.1ci.com/1C_Enterprise_Platform/Guides/Administrator_Guides/1C_Enterprise_8.3.22_Administrator_Guide/Chapter_8._Setting_up_web_services_for_1C_Enterprise/8.9._Safety_while_using_Internet_services/8.9.1._Authentication/
- RFC 7617, Basic HTTP Authentication (`charset`, UTF-8 considerations):  
  https://www.rfc-editor.org/rfc/rfc7617
- Requests source (`_basic_auth_str` uses `latin1` for str credentials):  
  https://raw.githubusercontent.com/psf/requests/main/src/requests/auth.py
