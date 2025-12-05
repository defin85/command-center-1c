/**
 * Recent operations table for service mesh.
 *
 * Displays:
 * - Operation ID, Service, Status, Duration
 * - Filtering by service when selected in diagram
 * - Click to view operation details
 */
import React, { useState, useEffect } from 'react'
import { Table, Tag, Tooltip, Button, Empty } from 'antd'
import { ReloadOutlined, EyeOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ServiceOperation } from '../../types/serviceMesh'
import { getV2 } from '../../api/generated'
import { transformOperationListResponse } from '../../utils/serviceMeshTransforms'
import './RecentOperationsTable.css'

const api = getV2()

interface RecentOperationsTableProps {
  selectedService: string | null
  onOperationClick?: (operationId: string) => void
}

/**
 * Get status tag color
 */
function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'completed':
      return 'success'
    case 'processing':
    case 'queued':
      return 'processing'
    case 'pending':
      return 'default'
    case 'failed':
      return 'error'
    case 'cancelled':
      return 'warning'
    default:
      return 'default'
  }
}

/**
 * Format duration
 */
function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`
}

/**
 * Format timestamp
 */
function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return '-'
  try {
    const date = new Date(timestamp)
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '-'
  }
}

const RecentOperationsTable: React.FC<RecentOperationsTableProps> = ({
  selectedService,
  onOperationClick,
}) => {
  const [operations, setOperations] = useState<ServiceOperation[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // Fetch operations
  const fetchOperations = async () => {
    setLoading(true)
    try {
      const rawResponse = await api.getOperationsListOperations({ limit: 50 })
      const response = transformOperationListResponse(rawResponse)
      // Apply client-side service filter if selected
      const filtered = selectedService
        ? response.operations.filter(op => op.service === selectedService)
        : response.operations
      setOperations(filtered.slice(0, 20))
      setTotal(selectedService ? filtered.length : response.total)
    } catch (error) {
      console.error('Failed to fetch operations:', error)
      setOperations([])
    } finally {
      setLoading(false)
    }
  }

  // Fetch on mount and when service filter changes
  useEffect(() => {
    fetchOperations()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedService])

  // Table columns
  const columns: ColumnsType<ServiceOperation> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (id: string) => (
        <Tooltip title={id}>
          <span className="operation-id">{id.slice(0, 8)}...</span>
        </Tooltip>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      render: (name: string) => (
        <Tooltip title={name}>
          <span>{name}</span>
        </Tooltip>
      ),
    },
    {
      title: 'Service',
      dataIndex: 'service',
      key: 'service',
      width: 100,
      render: (service: string) => (
        <Tag>{service}</Tag>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{status}</Tag>
      ),
    },
    {
      title: 'Progress',
      dataIndex: 'progress',
      key: 'progress',
      width: 80,
      render: (_: number, record: ServiceOperation) => (
        <span>
          {record.completedTasks}/{record.totalTasks}
        </span>
      ),
    },
    {
      title: 'Duration',
      dataIndex: 'durationSeconds',
      key: 'durationSeconds',
      width: 90,
      render: (duration: number | null) => formatDuration(duration),
    },
    {
      title: 'Created',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 130,
      render: (timestamp: string | null) => formatTimestamp(timestamp),
    },
    {
      title: '',
      key: 'actions',
      width: 40,
      render: (_, record: ServiceOperation) => (
        <Tooltip title="View details">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onOperationClick?.(record.id)}
          />
        </Tooltip>
      ),
    },
  ]

  return (
    <div className="recent-operations-table">
      <div className="recent-operations-table__header">
        <div className="recent-operations-table__title">
          Recent Operations
          {selectedService && (
            <Tag style={{ marginLeft: 8 }}>
              Filtered: {selectedService}
            </Tag>
          )}
        </div>
        <div className="recent-operations-table__actions">
          <span className="recent-operations-table__total">
            {total} total
          </span>
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            onClick={fetchOperations}
            loading={loading}
          >
            Refresh
          </Button>
        </div>
      </div>

      <Table
        columns={columns}
        dataSource={operations}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={false}
        scroll={{ y: 240 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                selectedService
                  ? `No operations for ${selectedService}`
                  : 'No recent operations'
              }
            />
          ),
        }}
        onRow={(record) => ({
          onClick: () => onOperationClick?.(record.id),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  )
}

export default RecentOperationsTable
