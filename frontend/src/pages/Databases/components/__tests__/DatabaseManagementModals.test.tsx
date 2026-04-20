import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App as AntApp, Form } from 'antd'
import { render, screen } from '@testing-library/react'
import { changeLanguage, ensureNamespaces } from '@/i18n/runtime'

import type { Database } from '../../../../api/generated/model/database'
import { DatabaseCredentialsModal } from '../DatabaseCredentialsModal'
import { DatabaseDbmsMetadataModal } from '../DatabaseDbmsMetadataModal'

vi.mock('../../../../components/platform', () => ({
  ModalFormShell: ({
    open,
    forceRender,
    title,
    subtitle,
    submitText,
    children,
  }: {
    open?: boolean
    forceRender?: boolean
    title?: ReactNode
    subtitle?: ReactNode
    submitText?: ReactNode
    children?: ReactNode
  }) => (
    open || forceRender ? (
      <section role="dialog" hidden={!open}>
        {title ? <h2>{title}</h2> : null}
        {subtitle ? <p>{subtitle}</p> : null}
        {children}
        <button type="button">{submitText ?? 'Save'}</button>
      </section>
    ) : null
  ),
}))

const makeDatabase = (overrides: Partial<Database> = {}): Database => ({
  id: 'db-1',
  name: 'Accounting DB',
  host: 'localhost',
  port: 1541,
  odata_url: 'http://localhost/odata',
  username: 'odata',
  password: '',
  password_configured: true,
  server_address: 'localhost',
  server_port: 1540,
  infobase_name: 'Accounting',
  status_display: 'Active',
  last_check: null,
  last_check_status: 'ok',
  consecutive_failures: 0,
  avg_response_time: null,
  cluster_id: 'cluster-1',
  is_healthy: true,
  sessions_deny: false,
  scheduled_jobs_deny: false,
  dbms: 'PostgreSQL',
  db_server: 'pg-db',
  db_name: 'accounting',
  ibcmd_connection: null,
  denied_from: null,
  denied_to: null,
  denied_message: null,
  permission_code: null,
  denied_parameter: null,
  last_health_error: null,
  last_health_error_code: null,
  created_at: '2026-03-13T00:00:00Z',
  updated_at: '2026-03-13T00:00:00Z',
  ...overrides,
})

function renderCredentialsModal(database: Database | null) {
  function Harness() {
    const [form] = Form.useForm()
    return (
      <AntApp>
        <DatabaseCredentialsModal
          open
          database={database}
          form={form}
          saving={false}
          onCancel={vi.fn()}
          onSave={vi.fn()}
          onReset={vi.fn()}
        />
      </AntApp>
    )
  }

  render(<Harness />)
}

function renderDbmsModal(database: Database | null) {
  function Harness() {
    const [form] = Form.useForm()
    return (
      <AntApp>
        <DatabaseDbmsMetadataModal
          open
          database={database}
          form={form}
          saving={false}
          onCancel={vi.fn()}
          onSave={vi.fn()}
          onReset={vi.fn()}
        />
      </AntApp>
    )
  }

  render(<Harness />)
}

describe('database management modal shells', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'databases')
  })

  afterEach(async () => {
    await ensureNamespaces('ru', 'databases')
    await changeLanguage('ru')
  })

  it('renders credentials flow inside the canonical modal shell', () => {
    renderCredentialsModal(makeDatabase())

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Credentials: Accounting DB')).toBeInTheDocument()
    expect(screen.getByText('Legacy OData credential override')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reset' })).not.toBeDisabled()
  })

  it('keeps DBMS reset action disabled when no DBMS identity is stored', () => {
    renderDbmsModal(makeDatabase({ dbms: null, db_server: null, db_name: null }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('DBMS metadata: Accounting DB')).toBeInTheDocument()
    expect(screen.getByText('Database-scoped DBMS identity override')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reset' })).toBeDisabled()
  })
})
