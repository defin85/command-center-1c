import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { afterAll, beforeAll, beforeEach, describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp, Form } from 'antd'
import type { FormInstance } from 'antd'
import { changeLanguage, ensureNamespaces } from '@/i18n/runtime'

import type { Database } from '../../../../api/generated/model/database'
import { DatabaseIbcmdConnectionProfileModal } from '../DatabaseIbcmdConnectionProfileModal'

let mockOfflineKeys: Record<string, unknown> = {}

vi.mock('../../../../api/queries/driverCommands', () => ({
  useDriverCommands: () => ({
    data: {
      catalog: {
        driver_schema: {
          connection: {
            offline: mockOfflineKeys,
          },
        },
      },
    },
    isLoading: false,
  }),
}))

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd')
  const { createDatabaseIbcmdConnectionProfileModalAntdTestDouble } = await import('./databaseIbcmdConnectionProfileModalAntdTestDouble')
  return createDatabaseIbcmdConnectionProfileModalAntdTestDouble(actual)
})

vi.mock('../../../../components/platform', () => ({
  ModalFormShell: ({
    children,
    forceRender,
    onSubmit,
    open,
    submitText,
    subtitle,
    title,
  }: {
    children?: ReactNode
    forceRender?: boolean
    onSubmit?: () => void
    open?: boolean
    submitText?: ReactNode
    subtitle?: ReactNode
    title?: ReactNode
  }) => (
    open || forceRender ? (
      <section role="dialog" hidden={!open}>
        {title ? <h2>{title}</h2> : null}
        {subtitle ? <p>{subtitle}</p> : null}
        {children}
        <button type="button" onClick={onSubmit}>{submitText ?? 'Save'}</button>
      </section>
    ) : null
  ),
}))

const makeDb = (overrides: Partial<Database> = {}): Database =>
  ({
    id: 'db1',
    name: 'db1',
    host: 'localhost',
    port: 80,
    odata_url: 'http://localhost/odata',
    username: 'u',
    password: 'p',
    password_configured: true,
    server_address: 'localhost',
    server_port: 1540,
    infobase_name: 'db1',
    status_display: 'Active',
    last_check: null,
    last_check_status: 'ok',
    consecutive_failures: 0,
    avg_response_time: null,
    cluster_id: null,
    is_healthy: true,
    sessions_deny: null,
    scheduled_jobs_deny: null,
    dbms: null,
    db_server: null,
    db_name: null,
    ibcmd_connection: null,
    denied_from: null,
    denied_to: null,
    denied_message: null,
    permission_code: null,
    denied_parameter: null,
    last_health_error: null,
    last_health_error_code: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }) as Database

function renderModal(database: Database) {
  let formRef: FormInstance | null = null
  const onCancel = vi.fn()
  const onReset = vi.fn()
  const onSave = vi.fn(() => formRef?.validateFields().catch(() => undefined))

  const Wrapper = () => {
    const [form] = Form.useForm()
    useEffect(() => {
      formRef = form
      form.setFieldsValue({ remote: '', pid: null, offline_entries: [] })
    }, [form])

    return (
      <AntApp>
        <DatabaseIbcmdConnectionProfileModal
          open
          database={database}
          form={form}
          saving={false}
          onCancel={onCancel}
          onSave={onSave}
          onReset={onReset}
        />
      </AntApp>
    )
  }

  render(<Wrapper />)
  return { onSave, onReset, getForm: () => formRef }
}

function requireForm(getForm: () => FormInstance | null): FormInstance {
  const form = getForm()
  if (!form) throw new Error('Form is not initialized')
  return form
}

describe('DatabaseIbcmdConnectionProfileModal', () => {
  beforeAll(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'databases')
  })

  beforeEach(() => {
    mockOfflineKeys = {}
  })

  afterAll(async () => {
    await ensureNamespaces('ru', 'databases')
    await changeLanguage('ru')
  })

  it('does not render default offline rows for empty profile', () => {
    renderModal(makeDb({ ibcmd_connection: {} }))
    expect(screen.queryByPlaceholderText('/path/to/value')).toBeNull()
  })

  it('disables Reset when no profile is configured', () => {
    renderModal(makeDb({ ibcmd_connection: null }))
    expect(screen.getByRole('button', { name: 'Reset' })).toBeDisabled()
  })

  it('adds offline key from driver schema', async () => {
    mockOfflineKeys = { db_name: {}, config: {} }
    const { getForm } = renderModal(makeDb({ ibcmd_connection: {} }))

    await waitFor(() => {
      expect(getForm()).not.toBeNull()
    })

    fireEvent.change(screen.getByTestId('ibcmd-profile-offline-schema-input'), { target: { value: 'db_name' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => {
      const form = requireForm(getForm)
      const entries = form.getFieldValue('offline_entries')
      expect(Array.isArray(entries) ? entries.length : 0).toBe(1)
      expect(entries?.[0]?.key).toBe('db_name')
    })
  })

  it('rejects offline key with -- prefix', async () => {
    mockOfflineKeys = { db_name: {} }
    renderModal(makeDb({ ibcmd_connection: {} }))

    fireEvent.change(screen.getByTestId('ibcmd-profile-offline-schema-input'), { target: { value: 'db_name' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    fireEvent.change(screen.getByPlaceholderText('config'), { target: { value: '--db-name' } })
    fireEvent.change(screen.getByPlaceholderText('/path/to/value'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(screen.getByText(/without the -- prefix/i)).toBeInTheDocument()
    })
  })

  it('shows validation error for non-ssh remote', async () => {
    renderModal(makeDb({ ibcmd_connection: {} }))

    fireEvent.change(screen.getByPlaceholderText('ssh://host:port'), { target: { value: 'http://host:1545' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(screen.getByText(/must start with ssh:\/\//i)).toBeInTheDocument()
    })
  })

  it('enables Reset when profile exists', () => {
    renderModal(makeDb({ ibcmd_connection: {} }))
    expect(screen.getByRole('button', { name: 'Reset' })).not.toBeDisabled()
  })
})
