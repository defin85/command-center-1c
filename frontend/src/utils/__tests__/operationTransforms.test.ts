import { describe, expect, it } from 'vitest'

import type { BatchOperation } from '../../api/generated/model'
import { transformBatchOperation } from '../operationTransforms'

const baseOperation: BatchOperation = {
  id: 'op-1',
  name: 'test operation',
  operation_type: 'query',
  target_entity: 'Workflow',
  status: 'completed',
  progress: 100,
  total_tasks: 1,
  completed_tasks: 1,
  failed_tasks: 0,
  duration_seconds: null,
  success_rate: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  workflow_execution_id: null,
  node_id: null,
  root_operation_id: 'op-1',
  execution_consumer: 'operations',
  lane: 'operations',
  priority: null,
  role: null,
  server_affinity: null,
  deadline_at: null,
  database_names: [],
  tasks: [],
}

describe('transformBatchOperation observability fields', () => {
  it('prefers top-level observability fields over metadata', () => {
    const transformed = transformBatchOperation({
      ...baseOperation,
      workflow_execution_id: 'wf-top',
      node_id: 'node-top',
      root_operation_id: 'root-top',
      execution_consumer: 'top-consumer',
      lane: 'top-lane',
      metadata: {
        workflow_execution_id: 'wf-meta',
        node_id: 'node-meta',
        root_operation_id: 'root-meta',
        execution_consumer: 'meta-consumer',
        lane: 'meta-lane',
      },
    })

    expect(transformed.workflow_execution_id).toBe('wf-top')
    expect(transformed.node_id).toBe('node-top')
    expect(transformed.root_operation_id).toBe('root-top')
    expect(transformed.execution_consumer).toBe('top-consumer')
    expect(transformed.lane).toBe('top-lane')
  })

  it('applies defaults when observability fields are missing', () => {
    const transformed = transformBatchOperation({
      ...baseOperation,
      id: 'op-2',
      root_operation_id: '',
      execution_consumer: '',
      lane: '',
      metadata: {},
    })

    expect(transformed.root_operation_id).toBe('op-2')
    expect(transformed.execution_consumer).toBe('operations')
    expect(transformed.lane).toBe('operations')
  })
})
