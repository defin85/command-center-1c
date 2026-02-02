import { describe, it, expect } from 'vitest'

import { buildIbcmdConnectionProfileUpdatePayload } from '../ibcmdConnectionProfile'

describe('buildIbcmdConnectionProfileUpdatePayload', () => {
  it('trims values and omits empty fields', () => {
    const payload = buildIbcmdConnectionProfileUpdatePayload('db1', {
      mode: 'remote',
      remote_url: '  http://127.0.0.1:1548  ',
      offline: {
        config: '',
        data: '   ',
        dbms: ' PostgreSQL ',
      },
    })

    expect(payload).toEqual({
      database_id: 'db1',
      mode: 'remote',
      remote_url: 'http://127.0.0.1:1548',
      offline: { dbms: 'PostgreSQL' },
    })
  })

  it('omits remote_url and offline when empty', () => {
    const payload = buildIbcmdConnectionProfileUpdatePayload('db1', { mode: 'auto', remote_url: ' ', offline: {} })
    expect(payload).toEqual({ database_id: 'db1', mode: 'auto' })
  })

  it('includes offline core paths when provided', () => {
    const payload = buildIbcmdConnectionProfileUpdatePayload('db1', {
      mode: 'offline',
      offline: {
        config: '/opt/1c/offline/config',
        data: '/opt/1c/offline/data',
        db_path: '/opt/1c/offline/db',
      },
    })
    expect(payload).toEqual({
      database_id: 'db1',
      mode: 'offline',
      offline: {
        config: '/opt/1c/offline/config',
        data: '/opt/1c/offline/data',
        db_path: '/opt/1c/offline/db',
      },
    })
  })
})

