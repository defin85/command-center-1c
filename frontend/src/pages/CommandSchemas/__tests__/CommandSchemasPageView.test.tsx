import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { App as AntApp } from 'antd'
import type { ReactNode } from 'react'
import { changeLanguage } from '@/i18n/runtime'

import { CommandSchemasPageView } from '../CommandSchemasPageView'
import type { CommandSchemasPageModel } from '../useCommandSchemasPageModel'

vi.mock('../../../components/platform', () => ({
  WorkspacePage: ({ header, children }: { header?: ReactNode; children: ReactNode }) => (
    <div>
      {header}
      {children}
    </div>
  ),
  PageHeader: ({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) => (
    <div>
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
      {actions}
    </div>
  ),
  MasterDetailShell: ({ list, detail }: { list: ReactNode; detail: ReactNode }) => (
    <div>
      <section>{list}</section>
      <section>{detail}</section>
    </div>
  ),
  EntityDetails: ({
    title,
    children,
    empty,
    emptyDescription,
  }: {
    title: ReactNode
    children?: ReactNode
    empty?: boolean
    emptyDescription?: ReactNode
  }) => (
    <div>
      <h3>{title}</h3>
      {empty ? <div>{emptyDescription}</div> : children}
    </div>
  ),
}))

vi.mock('../components/CommandSchemasHeader', () => ({
  CommandSchemasHeader: () => <div data-testid="command-schemas-header-stub" />,
}))

vi.mock('../components/CommandSchemasCommandList', () => ({
  CommandSchemasCommandList: () => <div data-testid="command-schemas-list-stub" />,
}))

vi.mock('../components/CommandSchemasEditorTabs', () => ({
  CommandSchemasEditorTabs: () => <div data-testid="command-schemas-editor-tabs-stub" />,
}))

vi.mock('../components/CommandSchemasSidePanel', () => ({
  CommandSchemasSidePanel: () => <div data-testid="command-schemas-side-panel-stub" />,
}))

vi.mock('../components/CommandSchemasUnsavedBanner', () => ({
  CommandSchemasUnsavedBanner: () => <div data-testid="command-schemas-unsaved-banner-stub" />,
}))

vi.mock('../components/CommandSchemasVersionsAlert', () => ({
  CommandSchemasVersionsAlert: () => <div data-testid="command-schemas-versions-stub" />,
}))

vi.mock('../components/modals/CommandSchemasImportItsModal', () => ({
  CommandSchemasImportItsModal: () => null,
}))

vi.mock('../components/modals/CommandSchemasPromoteModal', () => ({
  CommandSchemasPromoteModal: () => null,
}))

vi.mock('../components/modals/CommandSchemasRollbackModal', () => ({
  CommandSchemasRollbackModal: () => null,
}))

vi.mock('../components/modals/CommandSchemasSaveModal', () => ({
  CommandSchemasSaveModal: () => null,
}))

vi.mock('../CommandSchemasRawEditor', () => ({
  CommandSchemasRawEditor: () => <div data-testid="command-schemas-raw-editor-stub" />,
}))

const buildModel = (overrides: Partial<Record<string, unknown>> = {}) => ({
  activeDriver: 'ibcmd',
  requestDriverChange: vi.fn(),
  mode: 'guided',
  setMode: vi.fn(),
  loading: false,
  view: null,
  dirty: false,
  saving: false,
  rollbackLoading: false,
  rollingBack: false,
  importingIts: false,
  promoting: false,
  canPromoteLatest: false,
  requestRefreshView: vi.fn(),
  openImportIts: vi.fn(),
  openRollback: vi.fn(),
  openPromote: vi.fn(),
  openSave: vi.fn(),
  overridesCounts: { commands: 1, params: 2, permissions: 3, driver_schema: 1 },
  discardChanges: vi.fn(),
  error: null,
  commands: [{ id: 'catalog.sync' }],
  groupedCommands: { keys: [], groups: {} },
  search: '',
  setSearch: vi.fn(),
  riskFilter: 'any',
  setRiskFilter: vi.fn(),
  scopeFilter: 'any',
  setScopeFilter: vi.fn(),
  onlyModified: false,
  setOnlyModified: vi.fn(),
  hideDisabled: false,
  setHideDisabled: vi.fn(),
  selectedCommandId: '',
  selectCommand: vi.fn(),
  fetchView: vi.fn(),
  setRawDirty: vi.fn(),
  ...overrides,
}) as unknown as CommandSchemasPageModel

describe('CommandSchemasPageView i18n', () => {
  beforeEach(async () => {
    await changeLanguage('ru')
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('renders guided workspace copy from the adminSupport catalog', () => {
    render(
      <AntApp>
        <CommandSchemasPageView model={buildModel({ dirty: true, selectedCommandId: 'catalog.sync' })} />
      </AntApp>,
    )

    expect(screen.getByRole('heading', { name: 'Схемы команд' })).toBeInTheDocument()
    expect(
      screen.getByText('Рабочее место command schemas с route-addressable driver, mode и выбранной командой.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Команды (1)' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Редактор: catalog.sync' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Preview / Diff / Validate' })).toBeInTheDocument()
    expect(screen.getByTestId('command-schemas-unsaved-banner-stub')).toBeInTheDocument()
  })

  it('renders raw-mode shell labels and latest-version note from localized copy', () => {
    render(
      <AntApp>
        <CommandSchemasPageView
          model={buildModel({
            mode: 'raw',
            activeDriver: 'cli',
            view: { etag: 'etag-1' },
            canPromoteLatest: true,
          })}
        />
      </AntApp>,
    )

    expect(screen.getByRole('heading', { name: 'Raw editor: CLI' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'Примечание: base latest отличается от approved. Переключитесь в Guided mode, чтобы редактировать overrides относительно approved base.',
      ),
    ).toBeInTheDocument()
  })
})
