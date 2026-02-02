import type { Database } from '../../../api/generated/model/database'
import type { DatabaseIbcmdConnectionProfile } from '../../../api/generated/model/databaseIbcmdConnectionProfile'
import type { DatabaseIbcmdConnectionProfileOffline } from '../../../api/generated/model/databaseIbcmdConnectionProfileOffline'

export type DerivedIbcmdEffectiveMode = 'remote' | 'offline' | 'unconfigured'

export type DerivedIbcmdValue = string | null

export interface DerivedIbcmdDiffEntry {
  key: string
  unique_values: Array<{ value: DerivedIbcmdValue; count: number }>
}

export interface DerivedIbcmdConnectionReport {
  selected_total: number
  loaded_selected: number
  missing_selected_ids: string[]
  counts: {
    remote: number
    offline: number
    unconfigured: number
  }
  mixed_mode: boolean
  diff: {
    remote: DerivedIbcmdDiffEntry[]
    offline: DerivedIbcmdDiffEntry[]
  }
}

const normalizeString = (value: unknown): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

const normalizeOffline = (offline: DatabaseIbcmdConnectionProfileOffline | null | undefined): Record<string, string | null> => {
  const out: Record<string, string | null> = {}
  if (!offline || typeof offline !== 'object') return out
  const record = offline as Record<string, unknown>
  for (const [key, raw] of Object.entries(record)) {
    out[key] = normalizeString(raw)
  }
  return out
}

export const computeDerivedIbcmdConnectionReport = (
  databases: Database[],
  selectedDatabaseIds: string[]
): DerivedIbcmdConnectionReport => {
  const selectedSet = new Set(selectedDatabaseIds)
  const selectedDatabases = databases.filter((db) => selectedSet.has(db.id))
  const foundIds = new Set(selectedDatabases.map((db) => db.id))
  const missingSelectedIds = selectedDatabaseIds.filter((id) => !foundIds.has(id))

  const remoteSnapshots: Array<Record<string, DerivedIbcmdValue>> = []
  const offlineSnapshots: Array<Record<string, DerivedIbcmdValue>> = []

  let remoteCount = 0
  let offlineCount = 0
  let unconfiguredCount = 0

  for (const db of selectedDatabases) {
    const profile: DatabaseIbcmdConnectionProfile | null | undefined = db.ibcmd_connection ?? null
    if (!profile || typeof profile !== 'object') {
      unconfiguredCount += 1
      continue
    }

    const modeRaw = normalizeString(profile.mode) ?? 'auto'
    const remoteUrl = normalizeString(profile.remote_url)
    const offlineRaw = normalizeOffline(profile.offline)

    const offlineHasCorePaths = Boolean(offlineRaw.config) && Boolean(offlineRaw.data)

    const resolveOffline = (): Record<string, DerivedIbcmdValue> => {
      const resolved: Record<string, DerivedIbcmdValue> = {}
      for (const [key, value] of Object.entries(offlineRaw)) {
        resolved[`offline.${key}`] = value
      }
      if (!('offline.dbms' in resolved)) resolved['offline.dbms'] = null
      if (!('offline.db_server' in resolved)) resolved['offline.db_server'] = null
      if (!('offline.db_name' in resolved)) resolved['offline.db_name'] = null

      if (!resolved['offline.dbms']) resolved['offline.dbms'] = normalizeString(db.dbms)
      if (!resolved['offline.db_server']) resolved['offline.db_server'] = normalizeString(db.db_server)
      if (!resolved['offline.db_name']) resolved['offline.db_name'] = normalizeString(db.db_name)
      return resolved
    }

    if (modeRaw === 'remote') {
      if (!remoteUrl) {
        unconfiguredCount += 1
        continue
      }
      remoteCount += 1
      remoteSnapshots.push({ remote_url: remoteUrl })
      continue
    }

    if (modeRaw === 'offline') {
      if (!offlineHasCorePaths) {
        unconfiguredCount += 1
        continue
      }
      offlineCount += 1
      offlineSnapshots.push(resolveOffline())
      continue
    }

    if (remoteUrl) {
      remoteCount += 1
      remoteSnapshots.push({ remote_url: remoteUrl })
      continue
    }

    if (offlineHasCorePaths) {
      offlineCount += 1
      offlineSnapshots.push(resolveOffline())
      continue
    }

    unconfiguredCount += 1
  }

  const diffFor = (snapshots: Array<Record<string, DerivedIbcmdValue>>): DerivedIbcmdDiffEntry[] => {
    const keys = new Set<string>()
    for (const snap of snapshots) {
      Object.keys(snap).forEach((k) => keys.add(k))
    }

    const entries: DerivedIbcmdDiffEntry[] = []
    for (const key of Array.from(keys).sort()) {
      const counts = new Map<DerivedIbcmdValue, number>()
      for (const snap of snapshots) {
        const v = key in snap ? snap[key] : null
        counts.set(v, (counts.get(v) ?? 0) + 1)
      }
      if (counts.size <= 1) continue

      const uniqueValues = Array.from(counts.entries())
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => {
          if (b.count !== a.count) return b.count - a.count
          const av = a.value ?? ''
          const bv = b.value ?? ''
          return av.localeCompare(bv)
        })
      entries.push({ key, unique_values: uniqueValues })
    }
    return entries
  }

  const diffRemote = diffFor(remoteSnapshots)
  const diffOffline = diffFor(offlineSnapshots)

  return {
    selected_total: selectedDatabaseIds.length,
    loaded_selected: selectedDatabases.length,
    missing_selected_ids: missingSelectedIds,
    counts: {
      remote: remoteCount,
      offline: offlineCount,
      unconfigured: unconfiguredCount,
    },
    mixed_mode: remoteCount > 0 && offlineCount > 0,
    diff: {
      remote: diffRemote,
      offline: diffOffline,
    },
  }
}
