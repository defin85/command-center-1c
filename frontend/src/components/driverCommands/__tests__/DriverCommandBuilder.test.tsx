import { useState } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp } from 'antd'

import type { DriverCommandsResponseV2 } from '../../../api/driverCommands'
import { DriverCommandBuilder, type DriverCommandOperationConfig } from '../DriverCommandBuilder'

vi.mock('../../../lib/monacoEnv', () => ({}))

vi.mock('../../../api/generated', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/generated')>()
  return {
    ...actual,
    getV2: () => ({
      getDatabasesListDatabases: async () => ({ databases: [], count: 0, total: 0 }),
    }),
  }
})

vi.mock('@monaco-editor/react', () => ({
  default: (props: { value?: string; onChange?: (next?: string) => void }) => (
    <textarea
      data-testid="monaco-editor"
      value={props.value ?? ''}
      onChange={(event) => props.onChange?.(event.target.value)}
    />
  ),
}))

const mockUseDriverCommands = vi.fn()
const mockUseMe = vi.fn()
const mockUseDriverCommandShortcuts = vi.fn()
const mockCreateShortcut = vi.fn()
const mockDeleteShortcut = vi.fn()

vi.mock('../../../api/queries', () => ({
  useDriverCommands: (driver: string) => mockUseDriverCommands(driver),
  useMe: () => mockUseMe(),
  useDriverCommandShortcuts: () => mockUseDriverCommandShortcuts(),
  useCreateDriverCommandShortcut: () => ({ mutateAsync: mockCreateShortcut, isPending: false }),
  useDeleteDriverCommandShortcut: () => ({ mutateAsync: mockDeleteShortcut, isPending: false }),
  useArtifacts: () => ({ data: { artifacts: [] }, isLoading: false, error: null }),
  useArtifactVersions: () => ({ data: { versions: [] }, isLoading: false, error: null }),
  useArtifactAliases: () => ({ data: { aliases: [] }, isLoading: false, error: null }),
}))

function renderBuilder({
  driver,
  initialConfig,
  availableDatabaseIds,
}: {
  driver: 'cli' | 'ibcmd'
  initialConfig: DriverCommandOperationConfig
  availableDatabaseIds?: string[]
}) {
  const Wrapper = () => {
    const [config, setConfig] = useState<DriverCommandOperationConfig>(initialConfig)
    return (
      <AntApp>
        <DriverCommandBuilder
          driver={driver}
          config={config}
          onChange={(updates) => setConfig((prev) => ({ ...prev, ...updates }))}
          availableDatabaseIds={availableDatabaseIds}
          databaseNamesById={availableDatabaseIds?.reduce<Record<string, string>>((acc, id) => {
            acc[id] = `db-${id}`
            return acc
          }, {})}
        />
      </AntApp>
    )
  }
  return render(<Wrapper />)
}

describe('DriverCommandBuilder (schema-driven driver options)', () => {
  beforeEach(() => {
    mockUseDriverCommands.mockReset()
    mockUseMe.mockReset()
    mockUseDriverCommandShortcuts.mockReset()
    mockCreateShortcut.mockReset()
    mockDeleteShortcut.mockReset()

    mockUseMe.mockReturnValue({ data: { id: 1, username: 'u1', is_staff: true }, isLoading: false, error: null })
    mockUseDriverCommandShortcuts.mockReturnValue({ data: { items: [] }, isLoading: false, isError: false, error: null })
  })

  it('renders CLI driver options from driver_schema and respects visible_when', async () => {
    const user = userEvent.setup()

    const cliCatalog: DriverCommandsResponseV2['catalog'] = {
      catalog_version: 2,
      driver: 'cli',
      driver_schema: {
        cli_options: {
          disable_startup_messages: { kind: 'bool', default: true, label: 'Disable startup messages', required: false },
          disable_startup_dialogs: { kind: 'bool', default: true, label: 'Disable startup dialogs', required: false },
          log_capture: { kind: 'bool', default: false, label: 'Capture 1C log (/Out)', required: false },
          log_path: {
            kind: 'string',
            label: 'Log file path',
            required: false,
            ui: { visible_when: { path: 'cli_options.log_capture', equals: true } },
          },
          log_no_truncate: {
            kind: 'bool',
            default: false,
            label: 'Append log (-NoTruncate)',
            required: false,
            ui: { visible_when: { path: 'cli_options.log_capture', equals: true } },
          },
        },
        ui: {
          version: 1,
          sections: [
            {
              id: 'cli.startup',
              title: 'Startup options',
              paths: ['cli_options.disable_startup_messages', 'cli_options.disable_startup_dialogs'],
            },
            {
              id: 'cli.logging',
              title: 'Logging',
              paths: ['cli_options.log_capture', 'cli_options.log_path', 'cli_options.log_no_truncate'],
            },
          ],
        },
      },
      commands_by_id: {
        Proxy: {
          label: 'Proxy',
          argv: ['/Proxy'],
          scope: 'per_database',
          risk_level: 'safe',
          params_by_name: {},
        },
      },
    }

    mockUseDriverCommands.mockReturnValue({
      isLoading: false,
      error: null,
      data: { catalog: cliCatalog },
    })

    renderBuilder({
      driver: 'cli',
      initialConfig: { driver: 'cli', mode: 'guided', command_id: 'Proxy', params: {} },
    })

    expect(screen.getByText('Driver options')).toBeInTheDocument()
    expect(screen.getByText('Startup options')).toBeInTheDocument()
    expect(screen.getByText('Logging')).toBeInTheDocument()
    expect(screen.queryByText('Log file path')).not.toBeInTheDocument()

    const captureLabel = screen.getByText('Capture 1C log (/Out)')
    const captureItem = captureLabel.closest('.ant-form-item')
    expect(captureItem).not.toBeNull()
    const captureSwitch = within(captureItem as HTMLElement).getByRole('switch')
    await user.click(captureSwitch)

    expect(screen.getByText('Log file path')).toBeInTheDocument()
    expect(screen.getByText('Append log (-NoTruncate)')).toBeInTheDocument()
  })

  it('renders ibcmd auth section only for global scope', () => {
    const ibcmdCatalog: DriverCommandsResponseV2['catalog'] = {
      catalog_version: 2,
      driver: 'ibcmd',
      driver_schema: {
        connection: {
          remote: { kind: 'flag', flag: '--remote', expects_value: true, required: false, label: 'Remote', value_type: 'string' },
          pid: { kind: 'flag', flag: '--pid', expects_value: true, required: false, label: 'PID', value_type: 'int' },
          offline: {
            config: { kind: 'flag', flag: '--config', expects_value: true, required: false, label: 'Config', value_type: 'string' },
          },
        },
        timeout_seconds: { kind: 'int', default: 900, min: 1, max: 3600, label: 'Timeout (seconds)', required: false },
        stdin: { kind: 'text', label: 'Stdin (optional)', required: false, ui: { rows: 4 } },
        auth_database_id: {
          kind: 'database_ref',
          label: 'Auth mapping infobase',
          required: false,
          ui: { required_when: { command_scope: 'global' } },
        },
        ui: {
          version: 1,
          sections: [
            { id: 'ibcmd.auth', title: 'Auth context', paths: ['auth_database_id'], when: { command_scope: 'global' } },
            { id: 'ibcmd.connection', title: 'Connection', paths: ['connection.remote', 'connection.pid', 'connection.offline.config'] },
            { id: 'ibcmd.execution', title: 'Execution', paths: ['timeout_seconds', 'stdin'] },
          ],
        },
      },
      commands_by_id: {
        'server.config.init': {
          label: 'Init server config',
          argv: ['server', 'config', 'init'],
          scope: 'global',
          risk_level: 'safe',
          params_by_name: {},
        },
        'infobase.extension.list': {
          label: 'List extensions',
          argv: ['infobase', 'extension', 'list'],
          scope: 'per_database',
          risk_level: 'safe',
          params_by_name: {},
        },
      },
    }

    mockUseDriverCommands.mockReturnValue({
      isLoading: false,
      error: null,
      data: { catalog: ibcmdCatalog },
    })

    const first = renderBuilder({
      driver: 'ibcmd',
      initialConfig: { driver: 'ibcmd', mode: 'guided', command_id: 'server.config.init', params: {} },
      availableDatabaseIds: ['db1'],
    })

    expect(screen.getByText('Auth context')).toBeInTheDocument()
    expect(screen.getByText('Auth mapping infobase')).toBeInTheDocument()

    first.unmount()

    // Per-database scope should not show auth section
    renderBuilder({
      driver: 'ibcmd',
      initialConfig: { driver: 'ibcmd', mode: 'guided', command_id: 'infobase.extension.list', params: {} },
      availableDatabaseIds: ['db1'],
    })
    expect(screen.queryByText('Auth context')).not.toBeInTheDocument()
  })

  it('includes ibcmd connection args in preview (remote)', async () => {
    const user = userEvent.setup()

    const ibcmdCatalog: DriverCommandsResponseV2['catalog'] = {
      catalog_version: 2,
      driver: 'ibcmd',
      driver_schema: {
        connection: {
          remote: { kind: 'flag', flag: '--remote', expects_value: true, required: false, label: 'Remote', value_type: 'string' },
          pid: { kind: 'flag', flag: '--pid', expects_value: true, required: false, label: 'PID', value_type: 'int' },
          offline: {
            config: { kind: 'flag', flag: '--config', expects_value: true, required: false, label: 'Config', value_type: 'string' },
          },
        },
        timeout_seconds: { kind: 'int', default: 900, min: 1, max: 3600, label: 'Timeout (seconds)', required: false },
        stdin: { kind: 'text', label: 'Stdin (optional)', required: false, ui: { rows: 4 } },
        auth_database_id: {
          kind: 'database_ref',
          label: 'Auth mapping infobase',
          required: false,
          ui: { required_when: { command_scope: 'global' } },
        },
        ui: {
          version: 1,
          sections: [
            { id: 'ibcmd.auth', title: 'Auth context', paths: ['auth_database_id'], when: { command_scope: 'global' } },
            { id: 'ibcmd.connection', title: 'Connection', paths: ['connection.remote', 'connection.pid', 'connection.offline.config'] },
            { id: 'ibcmd.execution', title: 'Execution', paths: ['timeout_seconds', 'stdin'] },
          ],
        },
      },
      commands_by_id: {
        'server.config.init': {
          label: 'Init server config',
          argv: ['server', 'config', 'init'],
          scope: 'global',
          risk_level: 'safe',
          params_by_name: {},
        },
      },
    }

    mockUseDriverCommands.mockReturnValue({
      isLoading: false,
      error: null,
      data: { catalog: ibcmdCatalog },
    })

    renderBuilder({
      driver: 'ibcmd',
      initialConfig: { driver: 'ibcmd', mode: 'guided', command_id: 'server.config.init', params: {}, connection: {} },
      availableDatabaseIds: ['db1'],
    })

    const remoteLabel = screen.getByText('Remote')
    const remoteItem = remoteLabel.closest('.ant-form-item')
    expect(remoteItem).not.toBeNull()
    const remoteInput = within(remoteItem as HTMLElement).getByRole('textbox')
    await user.type(remoteInput, 'http://host:1545')

    expect(screen.getByText(/--remote=http:\/\/host:1545/)).toBeInTheDocument()
  })

  it('hides ibcmd credential fields in driver options and uses Offline advanced collapse', async () => {
    const user = userEvent.setup()

    const ibcmdCatalog: DriverCommandsResponseV2['catalog'] = {
      catalog_version: 2,
      driver: 'ibcmd',
      driver_schema: {
        connection: {
          offline: {
            dbms: { kind: 'flag', flag: '--dbms', expects_value: true, required: false, label: 'DBMS', value_type: 'string' },
            db_server: { kind: 'flag', flag: '--db-server', expects_value: true, required: false, label: 'DB server', value_type: 'string' },
            db_name: { kind: 'flag', flag: '--db-name', expects_value: true, required: false, label: 'DB name', value_type: 'string' },
            db_user: {
              kind: 'flag',
              flag: '--db-user',
              expects_value: true,
              required: false,
              label: 'DB user',
              value_type: 'string',
              semantics: { credential_kind: 'db_user' },
            },
            db_pwd: {
              kind: 'flag',
              flag: '--db-pwd',
              expects_value: true,
              required: false,
              label: 'DB password',
              value_type: 'string',
              semantics: { credential_kind: 'db_password' },
            },
            log_data: { kind: 'flag', flag: '--log-data', expects_value: true, required: false, label: 'Log data', value_type: 'string' },
            hidden_example: { kind: 'flag', flag: '--x', expects_value: true, required: false, label: 'Hidden', ui: { hidden: true } },
          },
        },
        ui: {
          version: 1,
          sections: [
            {
              id: 'ibcmd.connection',
              title: 'Connection',
              paths: [
                'connection.offline.dbms',
                'connection.offline.db_server',
                'connection.offline.db_name',
                'connection.offline.db_user',
                'connection.offline.db_pwd',
                'connection.offline.log_data',
                'connection.offline.hidden_example',
              ],
            },
          ],
        },
      },
      commands_by_id: {
        'infobase.extension.list': {
          label: 'List extensions',
          argv: ['infobase', 'extension', 'list'],
          scope: 'per_database',
          risk_level: 'safe',
          params_by_name: {},
        },
      },
    }

    mockUseDriverCommands.mockReturnValue({
      isLoading: false,
      error: null,
      data: { catalog: ibcmdCatalog },
    })

    renderBuilder({
      driver: 'ibcmd',
      initialConfig: { driver: 'ibcmd', mode: 'guided', command_id: 'infobase.extension.list', params: {} },
      availableDatabaseIds: ['db1'],
    })

    // For per_database scope, connection is derived from database profiles by default.
    const overrideSwitch = within(screen.getByTestId('ibcmd-connection-override')).getByRole('switch')
    await user.click(overrideSwitch)

    expect(screen.getByText('Connection')).toBeInTheDocument()
    expect(screen.getByText('DBMS')).toBeInTheDocument()
    expect(screen.getByText('DB server')).toBeInTheDocument()
    expect(screen.getByText('DB name')).toBeInTheDocument()

    // Credential fields must not be rendered as inputs.
    expect(screen.queryByText('DB user')).not.toBeInTheDocument()
    expect(screen.queryByText('DB password')).not.toBeInTheDocument()
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument()

    // Non-core offline fields must be grouped under collapsible "Offline: advanced".
    expect(screen.getByText('Offline: advanced')).toBeInTheDocument()
  })

  it('saves ibcmd shortcuts with driver options (connection/timeout/auth) and no raw stdin', async () => {
    const user = userEvent.setup()

    const ibcmdCatalog: DriverCommandsResponseV2['catalog'] = {
      catalog_version: 2,
      driver: 'ibcmd',
      driver_schema: {
        connection: {
          remote: { kind: 'flag', flag: '--remote', expects_value: true, required: false, label: 'Remote', value_type: 'string' },
        },
        timeout_seconds: { kind: 'int', default: 900, min: 1, max: 3600, label: 'Timeout (seconds)', required: false },
        stdin: { kind: 'text', label: 'Stdin (optional)', required: false, ui: { rows: 4 } },
        auth_database_id: {
          kind: 'database_ref',
          label: 'Auth mapping infobase',
          required: false,
          ui: { required_when: { command_scope: 'global' } },
        },
        ui: {
          version: 1,
          sections: [
            { id: 'ibcmd.auth', title: 'Auth context', paths: ['auth_database_id'], when: { command_scope: 'global' } },
            { id: 'ibcmd.connection', title: 'Connection', paths: ['connection.remote'] },
            { id: 'ibcmd.execution', title: 'Execution', paths: ['timeout_seconds', 'stdin'] },
          ],
        },
      },
      commands_by_id: {
        'server.config.init': {
          label: 'Init server config',
          argv: ['server', 'config', 'init'],
          scope: 'global',
          risk_level: 'safe',
          params_by_name: {},
        },
      },
    }

    mockUseDriverCommands.mockReturnValue({
      isLoading: false,
      error: null,
      data: { catalog: ibcmdCatalog },
    })
    mockCreateShortcut.mockResolvedValue({ id: 'shortcut-1' })

    renderBuilder({
      driver: 'ibcmd',
      initialConfig: {
        driver: 'ibcmd',
        mode: 'guided',
        command_id: 'server.config.init',
        params: { x: 1 },
        args_text: '--foo=bar',
        connection: { remote: 'http://host:1545' },
        timeout_seconds: 321,
        auth_database_id: 'db1',
        ib_auth: { strategy: 'none' },
        dbms_auth: { strategy: 'actor' },
        stdin: 'SHOULD_NOT_BE_STORED',
      },
      availableDatabaseIds: ['db1'],
    })

    await user.click(screen.getByRole('button', { name: 'Save shortcut' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    expect(mockCreateShortcut).toHaveBeenCalledTimes(1)
    const payload = mockCreateShortcut.mock.calls[0]?.[0]
    expect(payload).toMatchObject({
      driver: 'ibcmd',
      command_id: 'server.config.init',
      payload: {
        version: 1,
        config: {
          mode: 'guided',
          params: { x: 1 },
          args_text: '--foo=bar',
          connection: { remote: 'http://host:1545' },
          timeout_seconds: 321,
          auth_database_id: 'db1',
          ib_auth: { strategy: 'none' },
          dbms_auth: { strategy: 'actor' },
        },
      },
    })
    expect(payload.payload.config).not.toHaveProperty('stdin')
  }, 15_000)

  it('shows dangerous confirm modal and updates confirm_dangerous only on confirm', async () => {
    const user = userEvent.setup()

    const cliCatalog: DriverCommandsResponseV2['catalog'] = {
      catalog_version: 2,
      driver: 'cli',
      driver_schema: {
        ui: { version: 1, sections: [] },
      },
      commands_by_id: {
        Drop: {
          label: 'Drop something',
          argv: ['/Drop'],
          scope: 'per_database',
          risk_level: 'dangerous',
          params_by_name: {},
        },
      },
    }

    mockUseDriverCommands.mockReturnValue({
      isLoading: false,
      error: null,
      data: { catalog: cliCatalog },
    })

    renderBuilder({
      driver: 'cli',
      initialConfig: { driver: 'cli', mode: 'guided', command_id: 'Drop', params: {} },
    })

    const getCheckbox = () => screen.getByRole('checkbox', { name: 'I confirm this dangerous command' })

    await user.click(getCheckbox())
    const dialog1 = await screen.findByRole('dialog')
    expect(within(dialog1).getByText('Confirm dangerous command')).toBeInTheDocument()

    await user.click(within(dialog1).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(getCheckbox()).not.toBeChecked()

    await user.click(getCheckbox())
    const dialog2 = await screen.findByRole('dialog')
    expect(within(dialog2).getByText('Confirm dangerous command')).toBeInTheDocument()

    await user.click(within(dialog2).getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(getCheckbox()).toBeChecked()
  }, 15_000)
})
