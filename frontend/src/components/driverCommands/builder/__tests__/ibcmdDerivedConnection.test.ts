import { describe, it, expect } from 'vitest'

import type { Database } from '../../../../api/generated/model/database'
import { computeDerivedIbcmdConnectionReport } from '../ibcmdDerivedConnection'

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

describe('computeDerivedIbcmdConnectionReport', () => {
  it('detects mixed mode and produces diffs for remote_url and offline.config', () => {
    const db1 = makeDb({
      id: 'db1',
      dbms: 'PostgreSQL',
      ibcmd_connection: { mode: 'remote', remote_url: 'http://a', offline: null },
    })
    const db2 = makeDb({
      id: 'db2',
      dbms: 'PostgreSQL',
      ibcmd_connection: { mode: 'remote', remote_url: 'http://b', offline: null },
    })
    const db3 = makeDb({
      id: 'db3',
      dbms: 'PostgreSQL',
      ibcmd_connection: { mode: 'offline', remote_url: null, offline: { config: '/c1', data: '/d1' } },
    })
    const db4 = makeDb({
      id: 'db4',
      dbms: 'MSSQL',
      ibcmd_connection: { mode: 'offline', remote_url: null, offline: { config: '/c2', data: '/d1' } },
    })

    const report = computeDerivedIbcmdConnectionReport([db1, db2, db3, db4], ['db1', 'db2', 'db3', 'db4'])
    expect(report.counts).toEqual({ remote: 2, offline: 2, unconfigured: 0 })
    expect(report.mixed_mode).toBe(true)

    const remoteKeys = report.diff.remote.map((d) => d.key)
    expect(remoteKeys).toContain('remote_url')
    const remoteUrlDiff = report.diff.remote.find((d) => d.key === 'remote_url')
    expect(remoteUrlDiff?.unique_values).toEqual(
      expect.arrayContaining([
        { value: 'http://a', count: 1 },
        { value: 'http://b', count: 1 },
      ])
    )

    const offlineKeys = report.diff.offline.map((d) => d.key)
    expect(offlineKeys).toContain('offline.config')
    expect(offlineKeys).toContain('offline.dbms') // derived from Database.dbms fallback
  })

  it('treats offline profile without config/data as unconfigured', () => {
    const db = makeDb({
      id: 'db1',
      ibcmd_connection: { mode: 'offline', remote_url: null, offline: { config: '/c1' } },
    })
    const report = computeDerivedIbcmdConnectionReport([db], ['db1'])
    expect(report.counts).toEqual({ remote: 0, offline: 0, unconfigured: 1 })
  })
})

