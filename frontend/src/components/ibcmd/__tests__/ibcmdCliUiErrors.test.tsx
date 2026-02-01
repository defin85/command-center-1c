import { describe, it, expect, vi } from 'vitest'

import { parseIbcmdCliUiError, tryShowIbcmdCliUiError } from '../ibcmdCliUiErrors'

describe('ibcmdCliUiErrors', () => {
  it('parses OFFLINE_DB_METADATA_NOT_CONFIGURED and shows modal', () => {
    const error: any = {
      response: {
        data: {
          error: {
            code: 'OFFLINE_DB_METADATA_NOT_CONFIGURED',
            message: 'offline dbms metadata missing',
            details: {
              missing: [{ database_id: 'db-1', missing_keys: ['dbms'] }],
              missing_total: 1,
              omitted: 0,
            },
          },
        },
      },
    }

    const parsed = parseIbcmdCliUiError(error)
    expect(parsed?.code).toBe('OFFLINE_DB_METADATA_NOT_CONFIGURED')
    expect(parsed?.title).toMatch(/Offline DBMS metadata/i)

    const modal = { error: vi.fn() }
    const message = { error: vi.fn() }
    expect(tryShowIbcmdCliUiError(error, modal, message)).toBe(true)
    expect(modal.error).toHaveBeenCalledTimes(1)
  })
})

