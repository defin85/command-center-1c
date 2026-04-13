/**
 * Cluster overview component for Dashboard.
 *
 * Displays a compact table of clusters with health status.
 */

import { Card, Tag, Progress, Skeleton } from 'antd'
import { ClusterOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import type { ClusterStats } from '../types'
import { TableToolkit } from '../../../components/table/TableToolkit'
import { useTableToolkit } from '../../../components/table/hooks/useTableToolkit'
import { useMemo } from 'react'
import { useDashboardTranslation } from '../../../i18n'

export interface ClusterOverviewProps {
  /** Cluster statistics */
  clusters: ClusterStats[]
  /** Loading state */
  loading?: boolean
}

/**
 * Get tag color for cluster status
 */
const getStatusColor = (status: ClusterStats['status']): string => {
  const colors: Record<ClusterStats['status'], string> = {
    healthy: 'green',
    degraded: 'orange',
    critical: 'red',
  }
  return colors[status]
}

/**
 * Get status label
 */
export const ClusterOverview = ({
  clusters,
  loading = false,
}: ClusterOverviewProps) => {
  const navigate = useNavigate()
  const { t } = useDashboardTranslation()

  const fallbackColumnConfigs = useMemo(() => [
    {
      key: 'name',
      label: t(($) => $.clusterOverview.columns.name),
      sortable: true,
      groupKey: 'core',
      groupLabel: t(($) => $.clusterOverview.groups.core),
    },
    {
      key: 'databases',
      label: t(($) => $.clusterOverview.columns.databases),
      groupKey: 'core',
      groupLabel: t(($) => $.clusterOverview.groups.core),
    },
    {
      key: 'status',
      label: t(($) => $.clusterOverview.columns.status),
      sortable: true,
      groupKey: 'status',
      groupLabel: t(($) => $.clusterOverview.groups.status),
    },
  ], [t])

  const columns: ColumnsType<ClusterStats> = useMemo(() => ([
    {
      title: t(($) => $.clusterOverview.columns.name),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: t(($) => $.clusterOverview.columns.databases),
      key: 'databases',
      width: 150,
      render: (_value, record) => {
        const percent = record.totalDatabases > 0
          ? Math.round((record.healthyDatabases / record.totalDatabases) * 100)
          : 0
        return (
          <Progress
            percent={percent}
            size="small"
            format={() => `${record.healthyDatabases}/${record.totalDatabases}`}
            status={record.status === 'critical' ? 'exception' : 'normal'}
          />
        )
      },
    },
    {
      title: t(($) => $.clusterOverview.columns.status),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: ClusterStats['status']) => (
        <Tag color={getStatusColor(status)}>{t(($) => $.clusterOverview.status[status])}</Tag>
      ),
    },
  ]), [t])

  const table = useTableToolkit({
    tableId: 'dashboard_clusters',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 5,
  })

  const filteredClusters = useMemo(() => {
    const searchValue = table.search.trim().toLowerCase()
    return clusters.filter((item) => {
      if (searchValue) {
        const matchesSearch = [
          item.name,
          item.status,
          String(item.totalDatabases),
          String(item.healthyDatabases),
        ].some((value) => String(value || '').toLowerCase().includes(searchValue))
        if (!matchesSearch) return false
      }

      for (const [key, value] of Object.entries(table.filters)) {
        if (value === null || value === undefined || value === '') {
          continue
        }
        const recordValue = (() => {
          switch (key) {
            case 'name':
              return item.name
            case 'status':
              return item.status
            case 'databases':
              return `${item.healthyDatabases}/${item.totalDatabases}`
            default:
              return null
          }
        })()

        if (Array.isArray(value)) {
          if (!value.map(String).includes(String(recordValue ?? ''))) {
            return false
          }
          continue
        }

        if (typeof value === 'boolean') {
          if (Boolean(recordValue) !== value) return false
          continue
        }

        if (typeof value === 'number') {
          if (Number(recordValue) !== value) return false
          continue
        }

        const needle = String(value).toLowerCase()
        const haystack = String(recordValue ?? '').toLowerCase()
        if (!haystack.includes(needle)) return false
      }

      return true
    })
  }, [clusters, table.filters, table.search])

  const sortedClusters = useMemo(() => {
    if (!table.sort.key || !table.sort.order) {
      return filteredClusters
    }
    const key = table.sort.key
    const direction = table.sort.order === 'asc' ? 1 : -1
    const getValue = (item: ClusterStats) => {
      switch (key) {
        case 'name':
          return item.name
        case 'status':
          return item.status
        case 'databases':
          return item.totalDatabases
        default:
          return ''
      }
    }
    return [...filteredClusters].sort((a, b) => {
      const left = getValue(a)
      const right = getValue(b)
      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * direction
      }
      return String(left).localeCompare(String(right)) * direction
    })
  }, [filteredClusters, table.sort.key, table.sort.order])

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const pageItems = sortedClusters.slice(pageStart, pageStart + table.pagination.pageSize)

  if (loading) {
    return (
      <Card
        title={
          <>
            <ClusterOutlined style={{ marginRight: 8 }} />
            {t(($) => $.clusterOverview.title)}
          </>
        }
        size="small"
      >
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    )
  }

  return (
    <Card
      title={
        <>
          <ClusterOutlined style={{ marginRight: 8 }} />
          {t(($) => $.clusterOverview.title)}
        </>
      }
      size="small"
    >
      <TableToolkit
        table={table}
        data={pageItems}
        total={sortedClusters.length}
        rowKey="id"
        columns={columns}
        size="small"
        searchPlaceholder={t(($) => $.clusterOverview.searchPlaceholder)}
        onRow={(record) => ({
          onClick: () => navigate(`/clusters?cluster=${record.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </Card>
  )
}
