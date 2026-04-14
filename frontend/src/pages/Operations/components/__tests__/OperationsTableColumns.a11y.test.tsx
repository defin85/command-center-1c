import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { buildOperationsColumns } from '../OperationsTableColumns'
import type { UIBatchOperation } from '../../types'
import { changeLanguage, ensureNamespaces, i18n } from '@/i18n/runtime'
import type { useOperationsTranslation } from '@/i18n'

describe('OperationsTableColumns a11y', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    await ensureNamespaces('en', 'operations')
  })

  it('adds aria-label for icon-only filter controls', () => {
    const columns = buildOperationsColumns({
      onViewDetails: vi.fn(),
      onCancel: vi.fn(),
      onFilterWorkflow: vi.fn(),
      onFilterNode: vi.fn(),
      formatDateTime: (value) => value,
      t: i18n.getFixedT('en', 'operations') as ReturnType<typeof useOperationsTranslation>['t'],
    })

    const workflowColumn = columns.find((col) => col.key === 'workflow_execution_id')
    expect(workflowColumn).toBeTruthy()

    const record = {
      id: 'op-1',
      name: 'Test operation',
      workflow_execution_id: 'wf-1234567890',
      node_id: 'node-1',
      operation_type: 'test',
      status: 'completed',
      progress: 100,
      completed_tasks: 1,
      total_tasks: 1,
      failed_tasks: 0,
      database_names: [],
      created_at: new Date().toISOString(),
      duration_seconds: 1,
    } as unknown as UIBatchOperation

    // Render the cell output to ensure the icon-only buttons have accessible names.
    render(<>{workflowColumn?.render?.(null, record, 0) as unknown}</>)

    expect(screen.getByLabelText('Filter by workflow')).toBeInTheDocument()
    expect(screen.getByLabelText('Filter by node')).toBeInTheDocument()
  })
})
