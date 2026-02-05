import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import { useActionRunner } from '../../../../hooks/useActionRunner'

vi.mock('../../../../api/generated', () => ({
  getV2: () => ({
    postOperationsExecuteIbcmdCli: vi.fn().mockRejectedValue({
      response: {
        data: {
          error: {
            code: 'IBCMD_CONNECTION_PROFILE_INVALID',
            message: 'profile missing',
            details: { missing: [{ database_id: 'db-1', missing_keys: ['ibcmd_connection'] }] },
          },
        },
      },
    }),
    postOperationsExecute: vi.fn(),
    postWorkflowsExecuteWorkflow: vi.fn(),
  }),
}))

vi.mock('../../../../api/client', () => ({
  apiClient: { post: vi.fn() },
}))

describe('useActionRunner: ibcmd_cli error handling', () => {
  it('shows actionable modal for IBCMD_CONNECTION_PROFILE_INVALID', async () => {
    const message = { success: vi.fn(), error: vi.fn(), info: vi.fn() }
    const modal = { confirm: vi.fn(), error: vi.fn() }
    const navigate = vi.fn()

    const { result } = renderHook(() => useActionRunner({ isStaff: false, message, modal, navigate }))

    const action: any = {
      id: 'extensions.list',
      label: 'List extensions',
      contexts: ['database_card'],
      executor: { kind: 'ibcmd_cli', driver: 'ibcmd', command_id: 'infobase.extension.list' },
    }

    await act(async () => {
      await result.current.runAction(action, ['db-1'])
    })

    expect(modal.error).toHaveBeenCalledTimes(1)
    expect(message.error).not.toHaveBeenCalled()
  })
})
