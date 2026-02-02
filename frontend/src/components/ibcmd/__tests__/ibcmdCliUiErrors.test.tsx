import { describe, it, expect, vi } from 'vitest'

import { parseIbcmdCliUiError, tryShowIbcmdCliUiError } from '../ibcmdCliUiErrors'

describe('ibcmdCliUiErrors', () => {
  it('parses IBCMD_CONNECTION_PROFILE_INVALID and shows modal', () => {
    const error: any = {
      response: {
        data: {
          error: {
            code: 'IBCMD_CONNECTION_PROFILE_INVALID',
            message: 'profile missing',
            details: {
              missing: [{ database_id: 'db-1', missing_keys: ['ibcmd_connection'] }],
              missing_total: 1,
              omitted: 0,
            },
          },
        },
      },
    }

    const parsed = parseIbcmdCliUiError(error)
    expect(parsed?.code).toBe('IBCMD_CONNECTION_PROFILE_INVALID')
    expect(parsed?.title).toMatch(/IBCMD connection profile/i)

    const modal = { error: vi.fn() }
    const message = { error: vi.fn() }
    expect(tryShowIbcmdCliUiError(error, modal, message)).toBe(true)
    expect(modal.error).toHaveBeenCalledTimes(1)
  })
})
