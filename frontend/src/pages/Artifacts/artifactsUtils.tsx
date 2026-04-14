import { Space, Tag, Typography } from 'antd'
import type { MenuProps } from 'antd'

import type { Artifact, ArtifactAlias, ArtifactKind, ArtifactPurgeBlocker, ArtifactVersion } from '../../api/artifacts'

const { Text } = Typography

export const EMPTY_VERSIONS: ArtifactVersion[] = []
export const EMPTY_ALIASES: ArtifactAlias[] = []

export type ArtifactKindLabels = Record<ArtifactKind, string>

type LocaleDateTimeFormatter = (
  value: string | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions & { fallback?: string },
) => string

type ArtifactHelperLabels = {
  unavailable: string
  blocked: string
  blockersCount: (count: number) => string
  retryAfter: (value: string) => string
  operation: string
  workflow: string
  more: (count: number) => string
  inDays: (count: number) => string
  overdue: string
}

export const getArtifactKindLabel = (kind: ArtifactKind, labels: ArtifactKindLabels) => labels[kind] ?? kind

export const formatBytes = (value: number) => {
  if (!Number.isFinite(value)) return '-'
  if (value < 1024) return `${value} B`
  const kb = value / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  const gb = mb / 1024
  return `${gb.toFixed(1)} GB`
}

export const formatSpeed = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) return '-'
  return `${formatBytes(value)}/s`
}

export const formatDuration = (seconds: number | null) => {
  if (!Number.isFinite(seconds) || seconds === null) return '-'
  const value = Math.max(0, Math.round(seconds))
  const mins = Math.floor(value / 60)
  const secs = value % 60
  if (mins === 0) return `${secs}s`
  return `${mins}m ${secs}s`
}

export const formatPurgeAfter = (
  value: string | null | undefined,
  dateTime: LocaleDateTimeFormatter,
  labels: Pick<ArtifactHelperLabels, 'inDays' | 'overdue' | 'unavailable'>,
) => {
  if (!value) return labels.unavailable
  const target = new Date(value).getTime()
  if (!Number.isFinite(target)) return labels.unavailable
  const days = Math.ceil((target - Date.now()) / (1000 * 60 * 60 * 24))
  if (days > 0) {
    return `${dateTime(value, { fallback: labels.unavailable })} (${labels.inDays(days)})`
  }
  return `${dateTime(value, { fallback: labels.unavailable })} (${labels.overdue})`
}

export const renderPurgeBlockers = (
  blockers: ArtifactPurgeBlocker[] | undefined,
  labels: Pick<ArtifactHelperLabels, 'operation' | 'workflow' | 'more' | 'unavailable'>,
) => {
  const items = blockers ?? []
  if (items.length === 0) {
    return <Text type="secondary">{labels.unavailable}</Text>
  }

  return (
    <Space direction="vertical" size={0}>
      {items.slice(0, 10).map((blocker) => {
        const label = blocker.type === 'batch_operation' ? labels.operation : labels.workflow
        const title = blocker.name ? `${label}: ${blocker.name}` : `${label}: ${blocker.id}`
        return (
          <Text key={`${blocker.type}:${blocker.id}`}>
            {title} ({blocker.status})
          </Text>
        )
      })}
      {items.length > 10 && (
        <Text type="secondary">{labels.more(items.length - 10)}</Text>
      )}
    </Space>
  )
}

export const renderAutoPurge = (
  artifact: Artifact,
  dateTime: LocaleDateTimeFormatter,
  labels: ArtifactHelperLabels,
) => {
  if (!artifact.purge_after) return labels.unavailable

  if (artifact.purge_state !== 'blocked') {
    return formatPurgeAfter(artifact.purge_after, dateTime, labels)
  }

  const blockersCount = artifact.purge_blockers?.length ?? 0
  const retryAt = dateTime(artifact.purge_blocked_until, { fallback: labels.unavailable })

  return (
    <Space direction="vertical" size={0}>
      <Space size={8} wrap>
        <Tag color="orange">{labels.blocked}</Tag>
        {blockersCount > 0 && <Text type="secondary">{labels.blockersCount(blockersCount)}</Text>}
      </Space>
      <Text type="secondary">{formatPurgeAfter(artifact.purge_after, dateTime, labels)}</Text>
      <Text type="secondary">{labels.retryAfter(retryAt)}</Text>
    </Space>
  )
}

const stripExtension = (name: string) => name.replace(/\\.[^/.]+$/, '')

export const buildVersion = (fileName?: string) => {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const base = fileName ? stripExtension(fileName) : ''
  return base ? `${base}-${stamp}` : stamp
}

export const buildMetadataTemplate = (payload: {
  name?: string
  kind?: ArtifactKind
  tags?: string[]
  version?: string
  filename?: string
}) => ({
  schema_version: '1',
  source: 'ui',
  labels: [],
  notes: '',
  artifact: {
    name: payload.name || '',
    kind: payload.kind || '',
    tags: payload.tags || [],
  },
  build: {
    version: payload.version || '',
    filename: payload.filename || '',
  },
  created_at: new Date().toISOString(),
})

export const createAliasMenuItems = (labels: {
  latest: string
  approved: string
  stable: string
}): MenuProps['items'] => [
  { key: 'latest', label: labels.latest },
  { key: 'approved', label: labels.approved },
  { key: 'stable', label: labels.stable },
]

export const MAX_PREVIEW_BYTES = 1024 * 1024

export type DiffLine = {
  type: 'equal' | 'insert' | 'delete'
  text: string
}

export const diffLines = (before: string[], after: string[]): DiffLine[] => {
  const n = before.length
  const m = after.length
  const max = n + m
  let v = new Map<number, number>()
  v.set(1, 0)
  const trace: Array<Map<number, number>> = []

  const getV = (map: Map<number, number>, key: number) => map.get(key) ?? -1

  for (let d = 0; d <= max; d += 1) {
    const snapshot = new Map(v)
    for (let k = -d; k <= d; k += 2) {
      let x: number
      if (k === -d || (k !== d && getV(snapshot, k - 1) < getV(snapshot, k + 1))) {
        x = getV(snapshot, k + 1)
      } else {
        x = getV(snapshot, k - 1) + 1
      }
      let y = x - k
      while (x < n && y < m && before[x] === after[y]) {
        x += 1
        y += 1
      }
      snapshot.set(k, x)
      if (x >= n && y >= m) {
        trace.push(snapshot)
        d = max
        break
      }
    }
    trace.push(snapshot)
    v = snapshot
  }

  const result: DiffLine[] = []
  let x = n
  let y = m

  for (let d = trace.length - 1; d >= 0; d -= 1) {
    const snapshot = trace[d]
    const k = x - y
    let prevK: number
    if (k === -d || (k !== d && getV(snapshot, k - 1) < getV(snapshot, k + 1))) {
      prevK = k + 1
    } else {
      prevK = k - 1
    }
    const prevX = getV(snapshot, prevK)
    const prevY = prevX - prevK

    while (x > prevX && y > prevY) {
      result.push({ type: 'equal', text: before[x - 1] })
      x -= 1
      y -= 1
    }

    if (d === 0) {
      break
    }

    if (x === prevX) {
      result.push({ type: 'insert', text: after[y - 1] })
      y -= 1
    } else {
      result.push({ type: 'delete', text: before[x - 1] })
      x -= 1
    }
  }

  return result.reverse()
}
