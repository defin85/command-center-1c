## frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx

  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:175 - Form control без доступного лейбла (placeholder не считается): добавь aria-label="Search operations" или видимый <label
  htmlFor=...>.
  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:177 - Placeholder должен заканчиваться на … (не пусто/не без многоточия): "Search operations…" (и аналогично ниже).
  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:183 - Form control без доступного лейбла: добавь aria-label="Filter by driver" или <label htmlFor=...>.
  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:185 - Placeholder должен заканчиваться на …: "Filter by driver…".
  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:200 - Loading-текст должен заканчиваться … (одним символом): заменить Loading operation catalog... → Loading operation catalog….
  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:246 - Clickable UI на основе non-interactive элемента: Card с onClick без keyboard-эквивалента. Нужен <button>/role="button" +
  tabIndex=0 + обработка Enter/Space (и корректный disabled).
  frontend/src/pages/Operations/components/NewOperationWizard/SelectTypeStep.tsx:253 - transition: all запрещён: перечисли конкретные свойства (например transition: border-color 0.2s, background-color 0.2s,
  color 0.2s).

  ## frontend/src/pages/Operations/components/NewOperationWizard/ConfigureStep.tsx

  frontend/src/pages/Operations/components/NewOperationWizard/ConfigureStep.tsx:79 - Дата/время захардкожены форматной строкой; по гайдам предпочтительнее Intl.DateTimeFormat (или единая локаль-ориентированная
  стратегия форматирования).
  frontend/src/pages/Operations/components/NewOperationWizard/ConfigureStep.tsx:95 - То же самое: фиксированный формат даты/времени.
  frontend/src/pages/Operations/components/NewOperationWizard/ConfigureStep.tsx:301 - В UI-тексте используются прямые кавычки "..."; по гайдам — типографские “...”, либо без кавычек.
  frontend/src/pages/Operations/components/NewOperationWizard/ConfigureStep.tsx:337 - Loading-текст должен заканчиваться …: заменить Loading template configuration... → Loading template configuration….
  frontend/src/pages/Operations/components/NewOperationWizard/ConfigureStep.tsx:495 - В UI-тексте прямые кавычки "${operationType}"; по гайдам — “${operationType}” или перефразировать без кавычек.

  ## frontend/src/pages/Operations/components/NewOperationWizard/ReviewStep.tsx
  формат.

  ## frontend/src/components/table/TableToolbar.tsx

  frontend/src/components/table/TableToolbar.tsx:33 - Search input без доступного лейбла (есть id, но нет <label>/aria-label): добавить aria-label={searchPlaceholder} или реальный <label htmlFor={searchId}>.
  frontend/src/components/table/TableToolbar.tsx:37 - Placeholder должен заканчиваться на … (например Search databases…).

  ## frontend/src/components/table/TableFiltersRow.tsx

  frontend/src/components/table/TableFiltersRow.tsx:61 - Фильтры таблицы: control-и имеют id, но нет доступного лейбла (placeholder не замена). Добавь aria-label={config.label} (или визуальные лейблы).
  frontend/src/components/table/TableFiltersRow.tsx:78 - То же для InputNumber: нужен aria-label.
  frontend/src/components/table/TableFiltersRow.tsx:99 - То же для DatePicker: нужен aria-label.
  frontend/src/components/table/TableFiltersRow.tsx:122 - То же для Select: нужен aria-label.
  frontend/src/components/table/TableFiltersRow.tsx:65 - Placeholder по гайдам должен оканчиваться … (сейчас берётся config.label без многоточия) — нормализовать при формировании placeholder.

  ## frontend/src/components/table/TableToolkit.tsx

  frontend/src/components/table/TableToolkit.tsx:42 - Icon-only Button (глазик toggle) без aria-label: добавить aria-label/title типа "Hide filter ${label}" / "Show filter ${label}".
  frontend/src/components/table/TablePreferencesModal.tsx:907 - Input “View name” без доступного лейбла: добавить aria-label="View name" (и placeholder с …).
  frontend/src/components/table/TablePreferencesModal.tsx:918 - Input “New view name” без доступного лейбла: добавить aria-label="New view name".

  frontend/src/components/driverCommands/DriverCommandBuilder.tsx:1026 - Input лог-пути без доступного лейбла (placeholder не замена): добавить aria-label="Log file path" или обернуть в Form.Item label.
  frontend/src/components/driverCommands/DriverCommandBuilder.tsx:1052 - Вложенный modal.confirm() поверх уже открытого wizard-modal (stacked modal) — плохая практика для UX/a11y; лучше inline-confirm в
  текущем модале или отдельный step Review.
  frontend/src/components/driverCommands/DriverCommandBuilder.tsx:1216 - Input “Shortcut title” в confirm-модале без доступного лейбла: добавить aria-label="Shortcut title"/Form.Item label.
  frontend/src/components/driverCommands/DriverCommandBuilder.tsx:1306 - Select “Load shortcut” без доступного лейбла: добавить aria-label="Load shortcut" (placeholder не замена).

  ## frontend/src/components/cli/DesignerCliBuilder.tsx

  frontend/src/components/cli/DesignerCliBuilder.tsx:483 - Input лог-пути без доступного лейбла: добавить aria-label="Log file path" или Form.Item label.