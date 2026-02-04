## Контекст и текущая проблема
Существующий `/extensions` строится по snapshot'ам расширений и показывает агрегаты `installed/active/inactive/missing/unknown`.
Это удобно для диагностики, но плохо ложится на задачу “управляемые флаги”:
- оператор хочет установить целевое (policy) состояние флагов и видеть дрейф;
- кроме `active` есть `safe_mode` и `unsafe_action_protection`, и их нужно агрегировать/показывать одинаково;
- управление должно идти через action catalog (preview/preflight + bulk tasks).

## Ключевое решение: Policy + Observed + Drift
Вводим 3 слоя данных:
1) **Observed** (snapshot): фактические значения флагов по каждой базе (best-effort).
2) **Policy** (tenant-scoped): желаемые значения флагов по `extension_name`.
3) **Drift** (derived): расхождение observed vs policy на множестве баз.

В `/extensions` показываем **policy** как основной булевый столбец и добавляем унифицированные индикаторы “mixed/unknown/drift”.
Drill-down показывает **observed** per database.

## Унификация агрегации флагов
Для каждого `extension_name` и каждого флага из множества `{active, safe_mode, unsafe_action_protection}` вычисляем агрегат одинаковым алгоритмом:
- Рассматриваем только базы, где snapshot “ok” и расширение присутствует (installed subset).
- observed counts:
  - `true_count`: количество баз, где флаг явно `true`
  - `false_count`: количество баз, где флаг явно `false`
  - `unknown_count`: количество баз, где расширение установлено, но флаг отсутствует/не распарсен
- observed state:
  - `on` если `true_count > 0` и `false_count == 0`
  - `off` если `false_count > 0` и `true_count == 0`
  - `mixed` если `true_count > 0` и `false_count > 0`
  - `unknown` если `true_count == 0` и `false_count == 0` (и installed subset не пуст)
  - (пустой installed subset — отражается через `installed_count=0`, отдельного state не требуется)
- drift:
  - если policy задана (`true|false`), считаем `drift_count = количество баз с известным observed (true/false), где observed != policy`
  - `unknown_drift_count = количество баз, где observed неизвестен (unknown_count)`

Это позволяет UI одинаково отображать и фильтровать все три флага.

## Staff cross-tenant риск и guardrails
Staff без `X-CC1C-Tenant-ID` может видеть cross-tenant данные (read-only overview).
Но **policy и mutating операции** (изменение policy / apply flags) без tenant контекста неоднозначны.
Решение:
- Все mutating endpoints для policy и apply флагов MUST fail-closed для staff без `X-CC1C-Tenant-ID` (400/403 с явным error code).
- UI `/extensions` при отсутствии tenant контекста у staff:
  - показывает policy колонки как `—` и отключает mutating actions;
  - предлагает выбрать tenant (через существующий tenant picker/заголовок).

## Actions: Apply/Adopt
Нужны два user-facing потока:
- **Adopt from database**: взять observed значения флагов из snapshot выбранной базы и записать policy для extension_name.
- **Apply policy**: применить policy к набору баз (bulk), создавая per-db tasks.

Plan/apply должен:
- делать drift check (предусловия по snapshot hash),
- запускать executor через action catalog capability,
- обновлять snapshots по маркеру snapshot-producing (и тем самым закрывать риск stale UI),
- возвращать per-db результаты.

## Совместимость и миграция
Чтобы не ломать существующие клиенты, новые поля добавляются “рядом” (расширение контракта).
Deprecated/удаление старых `active_count/inactive_count` обсуждается отдельным change.

