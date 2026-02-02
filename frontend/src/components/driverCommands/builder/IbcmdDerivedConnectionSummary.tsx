import { useEffect, useMemo, useState } from 'react'
import { Alert, Collapse, Space, Spin, Typography } from 'antd'

import { getV2 } from '../../../api/generated'
import type { Database } from '../../../api/generated/model/database'
import { computeDerivedIbcmdConnectionReport } from './ibcmdDerivedConnection'

const { Text } = Typography

const api = getV2()

const MAX_PAGE_SIZE = 1000
const MAX_PAGES = 3

const MAX_SELECTED_FOR_DIFF = 200
const MAX_KEYS_PER_MODE = 12
const MAX_VALUES_PER_KEY = 5

const formatValue = (value: string | null) => {
  if (value === null) return '(missing)'
  return value
}

export function IbcmdDerivedConnectionSummary({ selectedDatabaseIds }: { selectedDatabaseIds: string[] }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [databases, setDatabases] = useState<Database[]>([])
  const selectedKey = useMemo(() => selectedDatabaseIds.join(','), [selectedDatabaseIds])

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setError(null)
      setDatabases([])

      if (selectedDatabaseIds.length === 0) {
        setLoading(false)
        return
      }

      setLoading(true)
      try {
        const selectedSet = new Set(selectedDatabaseIds)
        const remaining = new Set(selectedDatabaseIds)
        const collected: Database[] = []

        let offset = 0
        for (let page = 0; page < MAX_PAGES; page += 1) {
          const resp = await api.getDatabasesListDatabases({ limit: MAX_PAGE_SIZE, offset })
          const items = resp.databases ?? []
          for (const db of items) {
            if (!selectedSet.has(db.id)) continue
            if (!remaining.has(db.id)) continue
            remaining.delete(db.id)
            collected.push(db)
          }

          const total = typeof resp.total === 'number' ? resp.total : items.length
          offset += MAX_PAGE_SIZE
          if (remaining.size === 0) break
          if (offset >= total) break
        }

        if (cancelled) return
        setDatabases(collected)
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Failed to load databases')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    run()
    return () => { cancelled = true }
  }, [selectedDatabaseIds, selectedKey])

  const report = useMemo(() => computeDerivedIbcmdConnectionReport(databases, selectedDatabaseIds), [databases, selectedDatabaseIds])

  const diffHidden = report.selected_total > MAX_SELECTED_FOR_DIFF

  const renderDiff = (entries: ReturnType<typeof computeDerivedIbcmdConnectionReport>['diff']['remote']) => {
    const limited = entries.slice(0, MAX_KEYS_PER_MODE)
    return (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {limited.map((entry) => {
          const values = entry.unique_values
          const shown = values.slice(0, MAX_VALUES_PER_KEY)
          const omitted = values.length - shown.length
          return (
            <div key={entry.key}>
              <Text strong>{entry.key}</Text>
              <div style={{ marginTop: 4 }}>
                {shown.map((v) => (
                  <div key={`${entry.key}:${String(v.value)}`}>
                    <Text type="secondary">
                      {formatValue(v.value)}: {v.count}
                    </Text>
                  </div>
                ))}
                {omitted > 0 && (
                  <Text type="secondary">+{omitted} more</Text>
                )}
              </div>
            </div>
          )
        })}
      </Space>
    )
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Alert
        type="info"
        showIcon
        message="Connection will be derived from database profiles"
        description="For per_database scope, ibcmd connection is resolved per target database from its IBCMD connection profile. Mixed mode (remote/offline) is supported."
      />

      {loading && (
        <Space>
          <Spin size="small" />
          <Text type="secondary">Loading derived connection summary\u2026</Text>
        </Space>
      )}

      {error && (
        <Alert
          type="warning"
          showIcon
          message="Failed to load database profiles"
          description={error}
        />
      )}

      {!loading && !error && report.selected_total > 0 && (
        <>
          <Text type="secondary">
            Loaded {report.loaded_selected}/{report.selected_total} selected databases.
            {report.missing_selected_ids.length > 0 ? ` Missing: ${report.missing_selected_ids.length}.` : ''}
          </Text>

          <Space wrap>
            <Text>
              Remote: <Text strong>{report.counts.remote}</Text>
            </Text>
            <Text>
              Offline: <Text strong>{report.counts.offline}</Text>
            </Text>
            <Text>
              Unconfigured: <Text strong>{report.counts.unconfigured}</Text>
            </Text>
            {report.mixed_mode && <Text strong>Mixed mode</Text>}
          </Space>

          {report.counts.unconfigured > 0 && (
            <Alert
              type="warning"
              showIcon
              message="Some databases have missing or incomplete IBCMD connection profile"
              description="This operation will fail validation unless every selected database has a resolvable ibcmd connection profile (remote_url or offline)."
            />
          )}

          {!diffHidden && (report.diff.remote.length > 0 || report.diff.offline.length > 0) && (
            <Collapse
              size="small"
              items={[
                ...(report.diff.remote.length > 0 ? [{
                  key: 'diff-remote',
                  label: `Diff: remote targets (${report.counts.remote})`,
                  children: renderDiff(report.diff.remote),
                }] : []),
                ...(report.diff.offline.length > 0 ? [{
                  key: 'diff-offline',
                  label: `Diff: offline targets (${report.counts.offline})`,
                  children: renderDiff(report.diff.offline),
                }] : []),
              ]}
            />
          )}

          {diffHidden && (
            <Alert
              type="info"
              showIcon
              message="Diff is hidden for large selections"
              description={`Select up to ${MAX_SELECTED_FOR_DIFF} databases to view per-key diffs.`}
            />
          )}
        </>
      )}
    </Space>
  )
}
