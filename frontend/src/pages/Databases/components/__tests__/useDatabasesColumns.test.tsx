import { isValidElement, type ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import type { Database } from '../../../../api/generated/model/database'
import { useDatabasesColumns } from '../useDatabasesColumns'

const makeDatabase = (): Database => ({
  id: 'db-1',
  name: 'Accounting DB',
  host: 'localhost',
  port: 1541,
  odata_url: 'http://localhost/odata',
  username: 'odata',
  password: '',
  password_configured: false,
  server_address: 'localhost',
  server_port: 1540,
  infobase_name: 'Accounting',
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
  created_at: '2026-03-13T00:00:00Z',
  updated_at: '2026-03-13T00:00:00Z',
})

const noopMessage = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}

const toReactNode = (value: unknown): ReactNode => {
  if (isValidElement(value) || value == null) {
    return value
  }
  if (typeof value === 'object' && 'children' in (value as Record<string, unknown>)) {
    return (value as { children?: ReactNode }).children ?? null
  }
  return value as ReactNode
}

function ActionsCell({ canView = true }: { canView?: boolean }) {
  const openMetadataManagementDrawer = vi.fn()
  const columns = useDatabasesColumns({
    canViewDatabase: () => canView,
    canOperateDatabase: () => true,
    canManageDatabase: () => true,
    openMetadataManagementDrawer,
    openCredentialsModal: vi.fn(),
    openDbmsMetadataModal: vi.fn(),
    openIbcmdProfileModal: vi.fn(),
    openExtensionsDrawer: vi.fn(),
    handleSingleAction: vi.fn(),
    healthCheckPendingIds: new Set<string>(),
    markHealthCheckPending: vi.fn(),
    healthCheck: { mutateAsync: vi.fn(async () => ({ operation_id: 'op-1' })) },
    runSetStatus: vi.fn(async () => undefined),
    getErrorStatus: vi.fn(() => undefined),
    getErrorMessage: vi.fn(() => 'error'),
    message: noopMessage,
  })
  const actionsColumn = columns.find((column) => column.key === 'actions')
  const content = actionsColumn?.render?.(undefined, makeDatabase(), 0)
  return <div>{toReactNode(content)}</div>
}

describe('useDatabasesColumns', () => {
  it('renders metadata management action for canonical /databases handoff', () => {
    render(<ActionsCell />)

    expect(screen.getByRole('button', { name: 'Metadata management' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Metadata management' })).not.toBeDisabled()
  })

  it('disables metadata management action without view access', () => {
    render(<ActionsCell canView={false} />)

    expect(screen.getByRole('button', { name: 'Metadata management' })).toBeDisabled()
  })
})
