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
import { useDashboardTranslation, useLocaleFormatters } from '../../i18n'
import './RecentOperationsTable.css'

const api = getV2()

/** Maximum number of operations to display */
const DISPLAY_LIMIT = 20

interface RecentOperationsTableProps {
  selectedService: string | null
  onOperationClick?: (operationId: string) => void
}

function formatDuration(
  seconds: number | null,
  formatters: ReturnType<typeof useLocaleFormatters>,
): string {
  if (seconds === null) return '-'
  if (seconds < 1) return `${formatters.number(seconds * 1000, { maximumFractionDigits: 0 })}ms`
  if (seconds < 60) {
    return `${formatters.number(seconds, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }
  return `${formatters.number(Math.floor(seconds / 60))}m ${formatters.number(Math.floor(seconds % 60))}s`
}

function formatTimestamp(
  timestamp: string | null,
  formatters: ReturnType<typeof useLocaleFormatters>,
): string {
  if (!timestamp) return '-'
  try {
    return formatters.dateTime(timestamp, {
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
  const { t } = useDashboardTranslation()
  const formatters = useLocaleFormatters()
  const [operations, setOperations] = useState<ServiceOperation[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  // Request ID for race condition protection (requestId pattern)
  const requestIdRef = useRef(0)

  const statusOptions = useMemo(() => ([
    { value: 'pending', label: t(($) => $.recentOperations.statusOptions.pending) },
    { value: 'queued', label: t(($) => $.recentOperations.statusOptions.queued) },
    { value: 'processing', label: t(($) => $.recentOperations.statusOptions.processing) },
    { value: 'completed', label: t(($) => $.recentOperations.statusOptions.completed) },
    { value: 'failed', label: t(($) => $.recentOperations.statusOptions.failed) },
    { value: 'cancelled', label: t(($) => $.recentOperations.statusOptions.cancelled) },
  ]), [t])

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
  }, [])

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'id', label: t(($) => $.recentOperations.columns.id), sortable: true, groupKey: 'core', groupLabel: t(($) => $.clusterOverview.groups.core) },
    { key: 'name', label: t(($) => $.recentOperations.columns.name), sortable: true, groupKey: 'core', groupLabel: t(($) => $.clusterOverview.groups.core) },
    { key: 'service', label: t(($) => $.recentOperations.columns.service), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.recentOperations.columns.service) },
    { key: 'status', label: t(($) => $.recentOperations.columns.status), sortable: true, groupKey: 'meta', groupLabel: t(($) => $.recentOperations.columns.status) },
    { key: 'progress', label: t(($) => $.recentOperations.columns.progress), groupKey: 'meta', groupLabel: t(($) => $.recentOperations.columns.progress) },
    { key: 'durationSeconds', label: t(($) => $.recentOperations.columns.duration), sortable: true, groupKey: 'time', groupLabel: t(($) => $.recentOperations.columns.duration) },
    { key: 'createdAt', label: t(($) => $.recentOperations.columns.created), sortable: true, groupKey: 'time', groupLabel: t(($) => $.recentOperations.columns.created) },
    { key: 'actions', label: t(($) => $.recentOperations.viewDetails), groupKey: 'actions', groupLabel: t(($) => $.recentOperations.viewDetails) },
  ], [t])

  const columns: ColumnsType<ServiceOperation> = useMemo(() => ([
    {
      title: t(($) => $.recentOperations.columns.id),
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
      title: t(($) => $.recentOperations.columns.name),
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
      title: t(($) => $.recentOperations.columns.service),
      dataIndex: 'service',
      key: 'service',
      width: 100,
      render: (service: string) => (
        <Tag>{service}</Tag>
      ),
    },
    {
      title: t(($) => $.recentOperations.columns.status),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {statusOptions.find((option) => option.value === status)?.label ?? status}
        </Tag>
      ),
    },
    {
      title: t(($) => $.recentOperations.columns.progress),
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
      title: t(($) => $.recentOperations.columns.duration),
      dataIndex: 'durationSeconds',
      key: 'durationSeconds',
      width: 90,
      render: (duration: number | null) => formatDuration(duration, formatters),
    },
    {
      title: t(($) => $.recentOperations.columns.created),
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 130,
      render: (timestamp: string | null) => formatTimestamp(timestamp, formatters),
    },
    {
      title: '',
      key: 'actions',
      width: 40,
      render: (_value, record: ServiceOperation) => (
        <Tooltip title={t(($) => $.recentOperations.viewDetails)}>
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onOperationClick?.(record.id)}
          />
        </Tooltip>
      ),
    },
  ]), [formatters, onOperationClick, statusOptions, t])

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
          {t(($) => $.recentOperations.title)}
          {selectedService && (
            <Tag style={{ marginLeft: 8 }}>
              {t(($) => $.recentOperations.filtered, { service: selectedService })}
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
        searchPlaceholder={t(($) => $.recentOperations.searchPlaceholder)}
        toolbarActions={(
          <>
            <Select
              mode="multiple"
              placeholder={t(($) => $.recentOperations.filterByStatus)}
              value={statusFilter}
              onChange={setStatusFilter}
              options={statusOptions}
              allowClear
              style={{ width: 200 }}
              size="small"
              maxTagCount="responsive"
            />
            <span className="recent-operations-table__total">
              {t(($) => $.recentOperations.total, { count: displayTotal })}
            </span>
            <Button
              type="text"
              size="small"
              icon={<ReloadOutlined />}
              onClick={fetchOperations}
              loading={loading}
            >
              {t(($) => $.recentOperations.refresh)}
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
