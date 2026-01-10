import { describe, it, expect } from 'vitest'

import { clusterKey, databaseKey, loadMoreKey, parseKey } from '../clusterDatabaseTreeKeys'

describe('clusterDatabaseTreeKeys', () => {
  it('builds and parses cluster keys', () => {
    const key = clusterKey('cl-1')
    expect(key).toBe('cluster:cl-1')
    expect(parseKey(key)).toEqual({ type: 'cluster', id: 'cl-1' })
  })

  it('builds and parses database keys', () => {
    const key = databaseKey('db-1')
    expect(key).toBe('database:db-1')
    expect(parseKey(key)).toEqual({ type: 'database', id: 'db-1' })
  })

  it('builds and parses load-more keys', () => {
    const key = loadMoreKey('cl-2')
    expect(key).toBe('load-more:cl-2')
    expect(parseKey(key)).toEqual({ type: 'load-more', id: 'cl-2' })
  })

  it('returns null for unknown keys', () => {
    expect(parseKey('unknown')).toBeNull()
    expect(parseKey('cluster')).toBeNull()
    expect(parseKey('database')).toBeNull()
  })
})

