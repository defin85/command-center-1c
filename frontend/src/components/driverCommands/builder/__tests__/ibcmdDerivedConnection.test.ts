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
  it('detects mixed mode and produces diffs for remote and offline.config', () => {
    const db1 = makeDb({
      id: 'db1',
      ibcmd_connection: { remote: 'ssh://a:1545' },
    })
    const db2 = makeDb({
      id: 'db2',
      ibcmd_connection: { remote: 'ssh://b:1545' },
    })
    const db3 = makeDb({
      id: 'db3',
      ibcmd_connection: { offline: { config: '/c1', data: '/d1' } },
    })
    const db4 = makeDb({
      id: 'db4',
      ibcmd_connection: { offline: { config: '/c2', data: '/d1' } },
    })

    const report = computeDerivedIbcmdConnectionReport([db1, db2, db3, db4], ['db1', 'db2', 'db3', 'db4'])
    expect(report.counts).toEqual({ remote: 2, offline: 2, unconfigured: 0 })
    expect(report.mixed_mode).toBe(true)

    const remoteKeys = report.diff.remote.map((d) => d.key)
    expect(remoteKeys).toContain('remote')
    const remoteDiff = report.diff.remote.find((d) => d.key === 'remote')
    expect(remoteDiff?.unique_values).toEqual(
      expect.arrayContaining([
        { value: 'ssh://a:1545', count: 1 },
        { value: 'ssh://b:1545', count: 1 },
      ])
    )

    const offlineKeys = report.diff.offline.map((d) => d.key)
    expect(offlineKeys).toContain('offline.config')
  })

  it('treats any non-empty offline dict as configured', () => {
    const db = makeDb({
      id: 'db1',
      ibcmd_connection: { offline: { config: '/c1' } },
    })
    const report = computeDerivedIbcmdConnectionReport([db], ['db1'])
    expect(report.counts).toEqual({ remote: 0, offline: 1, unconfigured: 0 })
  })

  it('does not mark remote as diff when remote URL is the same across selected databases', () => {
    const db1 = makeDb({
      id: 'db1',
      ibcmd_connection: { remote: 'ssh://same-host:1545' },
    })
    const db2 = makeDb({
      id: 'db2',
      ibcmd_connection: { remote: 'ssh://same-host:1545' },
    })

    const report = computeDerivedIbcmdConnectionReport([db1, db2], ['db1', 'db2'])
    expect(report.counts).toEqual({ remote: 2, offline: 0, unconfigured: 0 })
    expect(report.mixed_mode).toBe(false)
    expect(report.diff.remote.some((entry) => entry.key === 'remote')).toBe(false)
  })
})
