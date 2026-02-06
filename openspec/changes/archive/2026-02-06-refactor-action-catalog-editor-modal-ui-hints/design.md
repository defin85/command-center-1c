# Design: Action Catalog Editor Modal v2 + capability UI hints

## Goals
1) Улучшить UX модалки Add/Edit action (структура, управляемость больших params, меньше “простыни”).
2) Убрать рост хардкода capability‑специфичных полей на фронте: capability‑логика описывается backend’ом декларативно.

## Drivers
- Масштабируемость: новые reserved capabilities не должны требовать новых `if/else` блоков в UI.
- Детерминизм и безопасность: подсказки/поля должны соответствовать backend semantics, а не UI догадкам.
- Производительность: команды могут иметь десятки/сотни параметров.

## Proposed Architecture

### 1) Backend: Editor Hints API
Добавить staff-only endpoint, который возвращает registry hints.

**Response (пример):**
```json
{
  "hints_version": 1,
  "capabilities": {
    "extensions.set_flags": {
      "fixed_schema": { "...json-schema..." },
      "fixed_ui_schema": { "...uiSchema..." },
      "help": {
        "title": "Set flags presets",
        "description": "..."
      }
    }
  }
}
```

Минимально hints нужны только для capability‑специфичных секций, прежде всего `executor.fixed.*`.
UI hints НЕ являются runtime setting и не редактируются оператором — это кодовая “capability registry”.

### 2) Frontend: Modal v2 layout
Модалка разделяется на вкладки:
- Basics (id/label/capability/contexts)
- Executor (kind/driver/command/workflow/mode)
- Params (Guided/Raw + tooling)
- Safety & Fixed (confirm_dangerous/timeout + capability fixed form)
- Preview (для staff)

### 3) Frontend: capability fixed section via schema-form
Вместо хардкода:
- UI определяет effective `capability` (из формы),
- запрашивает hints,
- если hints для capability есть: рендерит fixed‑секцию через schema‑form (например `@rjsf/antd`).

**Почему `@rjsf/antd`**
- Нативная поддержка JSON Schema форм и `uiSchema`,
- совместимость с AntD.
Документация: `https://rjsf-team.github.io/react-jsonschema-form/` и `https://github.com/rjsf-team/react-jsonschema-form/tree/main/packages/antd`.

### 4) Fallback behaviour
Если hints для capability отсутствуют:
- fixed‑секция показывает только общие поля (confirm_dangerous/timeout) и Raw JSON (если мы решим добавить raw fixed),
- capability‑специфичных полей не показывать, чтобы не вводить в заблуждение.

## Migration / Incremental Plan
- Шаг 1: hints API + fixed.apply_mask для `extensions.set_flags`.
- Шаг 2: Modal v2 tabs + params UX.
- Шаг 3: перенос остальных capability fixed UI (если появятся) в registry.

