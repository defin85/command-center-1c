/**
 * Recent operations table for service mesh.
 *
 * Displays:
 * - Operation ID, Service, Status, Duration
 * - Filtering by service when selected in diagram
 * - Click to view operation details
 *
 * Uses shared utilities from Operations page for consistency.
 */
import React, { useState, useEffect, useMemo, useRef } from 'react'
import { Table, Tag, Tooltip, Button, Empty, Select } from 'antd'
import { ReloadOutlined, EyeOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ServiceOperation } from '../../types/serviceMesh'
import { getV2 } from '../../api/generated'
import { transformOperationListResponse } from '../../utils/serviceMeshTransforms'
import { getStatusColor } from '../../pages/Operations'
import './RecentOperationsTable.css'

const api = getV2()

/** Maximum number of operations to display */
const DISPLAY_LIMIT = 20

/** Available status options for filtering */
const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'queued', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
]

interface RecentOperationsTableProps {
  selectedService: string | null
  onOperationClick?: (operationId: string) => void
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
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  // Request ID for race condition protection (requestId pattern)
  const requestIdRef = useRef(0)

  // Fetch operations with race condition protection
  const fetchOperations = async () => {
    const currentRequestId = ++requestIdRef.current
    setLoading(true)
    try {
      const rawResponse = await api.getOperationsListOperations({ limit: 50 })
      // Ignore response if a newer request was started
      if (currentRequestId !== requestIdRef.current) {
        return
      }
      const response = transformOperationListResponse(rawResponse)
      setOperations(response.operations)
    } catch (error) {
      // Ignore if newer request started
      if (currentRequestId !== requestIdRef.current) {
        return
      }
      console.error('Failed to fetch operations:', error)
      setOperations([])
    } finally {
      // Only update loading if this is the latest request
      if (currentRequestId === requestIdRef.current) {
        setLoading(false)
      }
    }
  }

  // Fetch on mount
  useEffect(() => {
    fetchOperations()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Client-side filtering with useMemo (single source of truth)
  const allFilteredOperations = useMemo(() => {
    let result = operations
    if (selectedService) {
      result = result.filter(op => op.service === selectedService)
    }
    if (statusFilter.length > 0) {
      result = result.filter(op => statusFilter.includes(op.status))
    }
    return result
  }, [operations, selectedService, statusFilter])

  // Limited operations for display
  const filteredOperations = useMemo(
    () => allFilteredOperations.slice(0, DISPLAY_LIMIT),
    [allFilteredOperations]
  )

  // Total count from filtered operations
  const displayTotal = allFilteredOperations.length

  // Build empty message based on active filters
  const emptyMessage = useMemo(() => {
    if (!selectedService && statusFilter.length === 0) {
      return 'No recent operations'
    }
    // For multiple statuses, show count instead of listing all
    const statusText = statusFilter.length > 2
      ? `with ${statusFilter.length} selected statuses`
      : statusFilter.length > 0
        ? `with status: ${statusFilter.join(', ')}`
        : ''
    if (selectedService && statusFilter.length > 0) {
      return `No operations for ${selectedService} ${statusText}`
    }
    if (selectedService) {
      return `No operations for ${selectedService}`
    }
    return `No operations ${statusText}`
  }, [selectedService, statusFilter])

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
          <Select
            mode="multiple"
            placeholder="Filter by status"
            value={statusFilter}
            onChange={setStatusFilter}
            options={STATUS_OPTIONS}
            allowClear
            style={{ width: 200 }}
            size="small"
            maxTagCount="responsive"
          />
          <span className="recent-operations-table__total">
            {displayTotal} total
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
        dataSource={filteredOperations}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={false}
        scroll={{ y: 240 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={emptyMessage}
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
