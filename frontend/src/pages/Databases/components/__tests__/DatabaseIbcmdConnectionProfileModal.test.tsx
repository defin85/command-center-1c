import { useEffect } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App as AntApp, Form } from 'antd'
import type { FormInstance } from 'antd'

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
  const user = userEvent.setup()
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
  return { user, onSave, onReset, getForm: () => formRef }
}

function requireForm(getForm: () => FormInstance | null): FormInstance {
  const form = getForm()
  if (!form) throw new Error('Form is not initialized')
  return form
}

describe('DatabaseIbcmdConnectionProfileModal', () => {
  beforeEach(() => {
    mockOfflineKeys = {}
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
    const { user, getForm } = renderModal(makeDb({ ibcmd_connection: {} }))

    await waitFor(() => {
      expect(getForm()).not.toBeNull()
    })

    await user.type(screen.getByTestId('ibcmd-profile-offline-schema-input'), 'db_name')
    await user.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => {
      const form = requireForm(getForm)
      const entries = form.getFieldValue('offline_entries')
      expect(Array.isArray(entries) ? entries.length : 0).toBe(1)
      expect(entries?.[0]?.key).toBe('db_name')
    })
  })

  it('rejects offline key with -- prefix', async () => {
    const { getForm } = renderModal(makeDb({ ibcmd_connection: {} }))

    await waitFor(() => {
      expect(getForm()).not.toBeNull()
    })

    const form = requireForm(getForm)
    await act(async () => {
      form.setFieldsValue({ offline_entries: [{ key: '--db-name', value: 'x' }] })
    })
    await waitFor(() => {
      expect(screen.getByPlaceholderText('/path/to/value')).toBeInTheDocument()
    })
    await act(async () => {
      await form.validateFields().catch(() => undefined)
    })

    await waitFor(() => {
      expect(screen.getByText(/без префикса/i)).toBeInTheDocument()
    })
  })

  it('shows validation error for non-ssh remote', async () => {
    const { getForm } = renderModal(makeDb({ ibcmd_connection: {} }))

    await waitFor(() => {
      expect(getForm()).not.toBeNull()
    })

    const form = requireForm(getForm)
    await act(async () => {
      form.setFieldValue('remote', 'http://host:1545')
      await form.validateFields().catch(() => undefined)
    })

    await waitFor(() => {
      expect(screen.getByText(/ssh:\/\//i)).toBeInTheDocument()
    })
  })

  it('enables Reset when profile exists', () => {
    renderModal(makeDb({ ibcmd_connection: {} }))
    expect(screen.getByRole('button', { name: 'Reset' })).not.toBeDisabled()
  })
})
