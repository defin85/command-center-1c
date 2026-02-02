import type { Database } from '../../../api/generated/model/database'

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

const normalizePid = (value: unknown): string | null => {
  if (typeof value !== 'number') return null
  if (!Number.isFinite(value) || value <= 0) return null
  return String(Math.trunc(value))
}

const normalizeOffline = (offline: unknown): Record<string, string | null> => {
  const out: Record<string, string | null> = {}
  if (!offline || typeof offline !== 'object' || Array.isArray(offline)) return out
  const record = offline as Record<string, unknown>
  for (const [key, raw] of Object.entries(record)) {
    if (key === 'db_user' || key === 'db_pwd' || key === 'db_password') continue
    out[key] = normalizeString(raw)
  }
  return out
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

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
    const profileRaw = (db as unknown as { ibcmd_connection?: unknown }).ibcmd_connection ?? null
    if (!isRecord(profileRaw)) {
      unconfiguredCount += 1
      continue
    }

    const remoteCandidate = normalizeString(profileRaw.remote ?? profileRaw.remote_url)
    const remote = remoteCandidate && remoteCandidate.toLowerCase().startsWith('ssh://') ? remoteCandidate : null
    const pid = normalizePid(profileRaw.pid)
    const offlineRaw = normalizeOffline(profileRaw.offline)

    const offlineSnapshot: Record<string, DerivedIbcmdValue> = {}
    offlineSnapshot.pid = pid
    for (const [key, value] of Object.entries(offlineRaw)) {
      if (value === null) continue
      offlineSnapshot[`offline.${key}`] = value
    }

    if (remote) {
      remoteCount += 1
      remoteSnapshots.push({ remote, pid })
      continue
    }

    if (pid || Object.keys(offlineSnapshot).length > 1) {
      offlineCount += 1
      offlineSnapshots.push(offlineSnapshot)
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

