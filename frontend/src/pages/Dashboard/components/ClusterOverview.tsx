/**
 * Cluster overview component for Dashboard.
 *
 * Displays a compact table of clusters with health status.
 */

import { Card, Table, Tag, Progress, Empty, Skeleton } from 'antd'
import { ClusterOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import type { ClusterStats } from '../types'

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
const getStatusLabel = (status: ClusterStats['status']): string => {
  const labels: Record<ClusterStats['status'], string> = {
    healthy: 'Healthy',
    degraded: 'Degraded',
    critical: 'Critical',
  }
  return labels[status]
}

/**
 * ClusterOverview - Compact cluster health table
 */
export const ClusterOverview = ({
  clusters,
  loading = false,
}: ClusterOverviewProps) => {
  const navigate = useNavigate()

  const columns: ColumnsType<ClusterStats> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: 'Databases',
      key: 'databases',
      width: 150,
      render: (_, record) => {
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
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: ClusterStats['status']) => (
        <Tag color={getStatusColor(status)}>{getStatusLabel(status)}</Tag>
      ),
    },
  ]

  if (loading) {
    return (
      <Card
        title={
          <>
            <ClusterOutlined style={{ marginRight: 8 }} />
            Clusters Overview
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
          Clusters Overview
        </>
      }
      size="small"
    >
      {clusters.length === 0 ? (
        <Empty
          description="No clusters configured"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={clusters}
          rowKey="id"
          size="small"
          pagination={false}
          onRow={(record) => ({
            onClick: () => navigate(`/clusters?id=${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      )}
    </Card>
  )
}
