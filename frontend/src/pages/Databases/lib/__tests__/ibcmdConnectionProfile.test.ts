import { describe, it, expect } from 'vitest'

import { buildIbcmdConnectionProfileUpdatePayload } from '../ibcmdConnectionProfile'

describe('buildIbcmdConnectionProfileUpdatePayload', () => {
  it('trims values and omits empty fields', () => {
    const payload = buildIbcmdConnectionProfileUpdatePayload('db1', {
      remote: '  ssh://127.0.0.1:1548  ',
      pid: ' 123 ',
      offline_entries: [
        { key: 'config', value: ' ' },
        { key: 'dbms', value: ' PostgreSQL ' },
      ],
    })

    expect(payload).toEqual({
      database_id: 'db1',
      remote: 'ssh://127.0.0.1:1548',
      pid: 123,
      offline: { dbms: 'PostgreSQL' },
    })
  })

  it('omits remote/pid/offline when empty', () => {
    const payload = buildIbcmdConnectionProfileUpdatePayload('db1', { remote: ' ', pid: null, offline_entries: [] })
    expect(payload).toEqual({ database_id: 'db1' })
  })

  it('includes offline entries when provided', () => {
    const payload = buildIbcmdConnectionProfileUpdatePayload('db1', {
      offline_entries: [
        { key: 'config', value: '/opt/1c/offline/config' },
        { key: 'data', value: '/opt/1c/offline/data' },
        { key: 'db_path', value: '/opt/1c/offline/db' },
      ],
    })
    expect(payload).toEqual({
      database_id: 'db1',
      offline: {
        config: '/opt/1c/offline/config',
        data: '/opt/1c/offline/data',
        db_path: '/opt/1c/offline/db',
      },
    })
  })
})
