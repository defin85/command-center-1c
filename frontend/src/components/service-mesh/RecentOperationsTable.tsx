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
import { Tag, Tooltip, Button, Select } from 'antd'
import { ReloadOutlined, EyeOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ServiceOperation } from '../../types/serviceMesh'
import { getV2 } from '../../api/generated'
import { transformOperationListResponse } from '../../utils/serviceMeshTransforms'
import { getStatusColor } from '../../pages/Operations'
import { TableToolkit } from '../table/TableToolkit'
import { useTableToolkit } from '../table/hooks/useTableToolkit'
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

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'id', label: 'ID', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'service', label: 'Service', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'status', label: 'Status', sortable: true, groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'progress', label: 'Progress', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'durationSeconds', label: 'Duration', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'createdAt', label: 'Created', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const columns: ColumnsType<ServiceOperation> = useMemo(() => ([
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (id: string) => (
        <Tooltip title={id}>
          <span className="operation-id">{id.slice(0, 8)}…</span>
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
      render: (_value, record: ServiceOperation) => (
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
  ]), [onOperationClick])

  const table = useTableToolkit({
    tableId: 'operations_recent',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: DISPLAY_LIMIT,
  })

  // Client-side filtering with useMemo (single source of truth)
  const allFilteredOperations = useMemo(() => {
    const searchValue = table.search.trim().toLowerCase()
    return operations.filter((op) => {
      if (selectedService && op.service !== selectedService) {
        return false
      }
      if (statusFilter.length > 0 && !statusFilter.includes(op.status)) {
        return false
      }
      if (searchValue) {
        const matchesSearch = [
          op.id,
          op.name,
          op.service,
          op.status,
        ].some((value) => String(value || '').toLowerCase().includes(searchValue))
        if (!matchesSearch) return false
      }

      for (const [key, value] of Object.entries(table.filters)) {
        if (value === null || value === undefined || value === '') {
          continue
        }
        const recordValue = (() => {
          switch (key) {
            case 'id':
              return op.id
            case 'name':
              return op.name
            case 'service':
              return op.service
            case 'status':
              return op.status
            case 'progress':
              return `${op.completedTasks}/${op.totalTasks}`
            case 'durationSeconds':
              return op.durationSeconds
            case 'createdAt':
              return op.createdAt
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
  }, [operations, selectedService, statusFilter, table.filters, table.search])

  const sortedOperations = useMemo(() => {
    if (!table.sort.key || !table.sort.order) {
      return allFilteredOperations
    }
    const key = table.sort.key
    const direction = table.sort.order === 'asc' ? 1 : -1
    const getValue = (op: ServiceOperation) => {
      switch (key) {
        case 'id':
          return op.id
        case 'name':
          return op.name
        case 'service':
          return op.service
        case 'status':
          return op.status
        case 'progress':
          return op.completedTasks
        case 'durationSeconds':
          return op.durationSeconds ?? -1
        case 'createdAt':
          return op.createdAt ? Date.parse(op.createdAt) : -1
        default:
          return ''
      }
    }
    return [...allFilteredOperations].sort((a, b) => {
      const left = getValue(a)
      const right = getValue(b)
      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * direction
      }
      return String(left).localeCompare(String(right)) * direction
    })
  }, [allFilteredOperations, table.sort.key, table.sort.order])

  const pageStart = (table.pagination.page - 1) * table.pagination.pageSize
  const pageItems = sortedOperations.slice(pageStart, pageStart + table.pagination.pageSize)

  // Total count from filtered operations
  const displayTotal = allFilteredOperations.length

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
      </div>

      <TableToolkit
        table={table}
        data={pageItems}
        total={sortedOperations.length}
        loading={loading}
        rowKey="id"
        columns={columns}
        size="small"
        scroll={{ y: 240 }}
        searchPlaceholder="Search Operations"
        toolbarActions={(
          <>
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
          </>
        )}
        onRow={(record) => ({
          onClick: () => onOperationClick?.(record.id),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  )
}

export default RecentOperationsTable
