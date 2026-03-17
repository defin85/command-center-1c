## Context

В проекте уже есть reusable reference data и selector-паттерны для workflow/decision authoring, но они используются неравномерно:
- `/workflows` умеет загружать workflow revisions и decision revisions как first-class reference catalogs;
- `/pools/catalog` для attachment selection уже использует structured selection;
- `/pools/binding-profiles` всё ещё опирается на ручной ввод workflow ids и raw JSON;
- `/decisions` реализует корректную доменную семантику, но страница перегружена orchestration-кодом и плохо подходит для дальнейшего расширения.

Проблема не в отсутствии backend контрактов, а в отсутствии общего frontend boundary для versioned authoring references.

## Goals / Non-Goals

- Goals:
  - убрать copy-paste opaque ids из default authoring path;
  - переиспользовать один reference-loading слой и один набор picker primitives;
  - уменьшить связность `DecisionsPage` без изменения runtime semantics;
  - выровнять UX `Decisions` и `binding-profiles` как versioned authoring surfaces.
- Non-Goals:
  - не менять runtime resolution, attachment semantics или backend contracts;
  - не строить один универсальный editor для всех versioned ресурсов;
  - не удалять raw/compatibility paths полностью, если они нужны для migration/debugging.

## Decisions

### Decision: Ввести общий authoring-reference boundary

Будет выделен shared слой уровня frontend query + normalization:
- загрузка workflow revisions из workflow library;
- загрузка decision revisions из `/decisions`;
- нормализация в единые option models;
- единые label/inactive/drift markers.

Этот слой должен стать единственным default источником данных для selectors в `/workflows`, `/decisions` и `/pools/binding-profiles`.

### Decision: Refactor `binding-profiles` начать с UX, а не с backend

Самая заметная пользовательская проблема сейчас сосредоточена в `binding-profiles`, поэтому первый практический этап:
- workflow revision picker;
- slot-oriented decision refs editor;
- advanced mode для raw payload.

Это закрывает copy-paste сценарий без риска затронуть runtime path.

### Decision: `DecisionsPage` разрезать по доменным подсистемам

`/decisions` будет разделён минимум на четыре зоны ответственности:
- catalog/detail loading;
- metadata context / fallback gating;
- editor state and save/deactivate flows;
- legacy import flow.

Распил должен сохранить текущий fail-closed UX и не менять acceptance semantics.

### Decision: Не строить generic mega-editor

Общий слой ограничивается reference loaders, selectors и shell-level patterns.

`Decisions` и `binding-profiles` остаются разными доменными surfaces:
- у `Decisions` есть metadata-aware rollover и `/databases` handoff;
- у `binding-profiles` есть immutable revisions, usage table и pool attachment handoff.

Попытка объединить их в один generic editor добавит больше связности, чем снимет.

## Risks / Trade-offs

- Пока `add-binding-profiles-and-pool-attachments` не заархивирован, новая proposal зависит от pending capability `pool-binding-profiles`; реализацию нужно вести согласованно с этой базой.
- При переносе shared reference logic есть риск дублировать типы между `WorkflowDesigner`, `PropertyEditor` и новым shared hook, если не выделить один canonical model.
- Распил `DecisionsPage` легко превращается в "большой рефакторинг без UX выигрыша", если не сохранить focus на default authoring flow и tests.

## Migration Plan

1. Выделить shared reference loading и option helpers без изменения поведения страниц.
2. Перевести `binding-profiles` на structured authoring path.
3. Разрезать `/decisions` на hooks/panels с сохранением текущих тестов и semantics.
4. Дочистить navigation/handoff между `/workflows`, `/decisions` и `/pools/binding-profiles`.
