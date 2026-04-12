import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, App as AntApp, Button, Card, Descriptions, Empty, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useSearchParams } from 'react-router-dom'

import {
  applyPoolMasterDataDedupeReviewAction,
  getPoolMasterDataDedupeReviewItem,
  listPoolMasterDataDedupeReviewItems,
  listPoolTargetDatabases,
  type PoolMasterDataDedupeAffectedBinding,
  type PoolMasterDataDedupeReviewItem,
  type PoolMasterDataDedupeReviewStatus,
  type PoolMasterDataDedupeRuntimeBlocker,
  type PoolMasterDataRegistryEntry,
  type PoolMasterDataSourceRecord,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { JsonBlock } from '../../../components/platform'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { getDedupeEntityOptions, getRegistryEntityLabel } from './registry'

const { Text } = Typography

const REVIEW_STATUS_OPTIONS: Array<{ value: PoolMasterDataDedupeReviewStatus; label: string }> = [
  { value: 'pending_review', label: 'pending_review' },
  { value: 'resolved_auto', label: 'resolved_auto' },
  { value: 'resolved_manual', label: 'resolved_manual' },
  { value: 'superseded', label: 'superseded' },
]

const REVIEW_STATUS_COLORS: Record<PoolMasterDataDedupeReviewStatus, string> = {
  pending_review: 'warning',
  resolved_auto: 'success',
  resolved_manual: 'processing',
  superseded: 'default',
}

type DedupeReviewTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

const dedupeReviewActionLabels: Record<'accept_merge' | 'choose_survivor' | 'mark_distinct', string> = {
  accept_merge: 'accept merge',
  choose_survivor: 'choose survivor',
  mark_distinct: 'mark distinct',
}

export function DedupeReviewTab({ registryEntries }: DedupeReviewTabProps) {
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const [databases, setDatabases] = useState<SimpleDatabaseRef[]>([])
  const [databaseId, setDatabaseId] = useState<string | undefined>(searchParams.get('databaseId')?.trim() || undefined)
  const [entityType, setEntityType] = useState<string | undefined>(searchParams.get('entityType')?.trim() || undefined)
  const [status, setStatus] = useState<PoolMasterDataDedupeReviewStatus | undefined>(undefined)
  const [reasonCode, setReasonCode] = useState<string | undefined>(undefined)
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(searchParams.get('reviewItemId')?.trim() || null)
  const [reviewItems, setReviewItems] = useState<PoolMasterDataDedupeReviewItem[]>([])
  const [selectedReview, setSelectedReview] = useState<PoolMasterDataDedupeReviewItem | null>(null)
  const [selectedSourceRecordId, setSelectedSourceRecordId] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [actionName, setActionName] = useState<string | null>(null)

  const routeClusterId = searchParams.get('clusterId')?.trim() || undefined
  const reviewItemIdFromUrl = searchParams.get('reviewItemId')?.trim() || undefined
  const entityTypeOptions = useMemo(
    () => getDedupeEntityOptions(registryEntries),
    [registryEntries]
  )

  const databaseNameById = useMemo(() => {
    const lookup = new Map<string, string>()
    for (const database of databases) {
      lookup.set(database.id, database.name)
    }
    return lookup
  }, [databases])

  const selectedSourceRecord = useMemo(() => {
    if (!selectedReview) {
      return null
    }
    const records = selectedReview.source_records ?? []
    return (
      records.find((item) => item.id === selectedSourceRecordId)
      ?? records.find((item) => item.id === selectedReview.proposed_survivor_source_record_id)
      ?? records[0]
      ?? null
    )
  }, [selectedReview, selectedSourceRecordId])
  const selectedReviewDetailText = useMemo(() => {
    if (!selectedReview) {
      return ''
    }
    return typeof selectedReview.metadata.detail === 'string'
      ? selectedReview.metadata.detail
      : ''
  }, [selectedReview])

  const syncRouteContext = useMemo(() => {
    const next = new URLSearchParams(searchParams)
    if (databaseId) {
      next.set('databaseId', databaseId)
    } else {
      next.delete('databaseId')
    }
    if (entityType) {
      next.set('entityType', entityType)
    } else {
      next.delete('entityType')
    }
    if (selectedReviewId) {
      next.set('reviewItemId', selectedReviewId)
    } else {
      next.delete('reviewItemId')
    }
    const clusterId = selectedReview?.cluster_id || routeClusterId
    if (clusterId) {
      next.set('clusterId', clusterId)
    } else {
      next.delete('clusterId')
    }
    return next
  }, [databaseId, entityType, routeClusterId, searchParams, selectedReview?.cluster_id, selectedReviewId])

  useEffect(() => {
    if (syncRouteContext.toString() !== searchParams.toString()) {
      setSearchParams(syncRouteContext, { replace: true })
    }
  }, [searchParams, setSearchParams, syncRouteContext])

  useEffect(() => {
    if (reviewItemIdFromUrl && reviewItemIdFromUrl !== selectedReviewId) {
      setSelectedReviewId(reviewItemIdFromUrl)
    }
  }, [reviewItemIdFromUrl, selectedReviewId])

  const loadDatabases = useCallback(async () => {
    try {
      const rows = await listPoolTargetDatabases()
      setDatabases(rows)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить список баз для Dedupe Review.')
      message.error(resolved.message)
    }
  }, [message])

  const loadReviewItems = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listPoolMasterDataDedupeReviewItems({
        database_id: databaseId,
        entity_type: entityType,
        status,
        reason_code: reasonCode,
        cluster_id: routeClusterId,
        limit: 50,
        offset: 0,
      })
      setReviewItems(response.items)
      setSelectedReviewId((current) => {
        if (current) {
          return current
        }
        if (reviewItemIdFromUrl) {
          return reviewItemIdFromUrl
        }
        return response.items[0]?.id ?? null
      })
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить dedupe review queue.')
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [databaseId, entityType, message, reasonCode, reviewItemIdFromUrl, routeClusterId, status])

  const loadReviewDetail = useCallback(async (reviewItemId: string, silent = false) => {
    if (!silent) {
      setLoadingDetail(true)
    }
    try {
      const response = await getPoolMasterDataDedupeReviewItem(reviewItemId)
      setSelectedReview(response.review_item)
    } catch (error) {
      if (!silent) {
        const resolved = resolveApiError(error, 'Не удалось загрузить детали dedupe review item.')
        message.error(resolved.message)
      }
    } finally {
      if (!silent) {
        setLoadingDetail(false)
      }
    }
  }, [message])

  useEffect(() => {
    void loadDatabases()
  }, [loadDatabases])

  useEffect(() => {
    void loadReviewItems()
  }, [loadReviewItems])

  useEffect(() => {
    if (!selectedReviewId) {
      setSelectedReview(null)
      return
    }
    void loadReviewDetail(selectedReviewId)
  }, [loadReviewDetail, selectedReviewId])

  useEffect(() => {
    if (!selectedReviewId || !selectedReview || selectedReview.status !== 'pending_review') {
      return
    }
    const timer = window.setInterval(() => {
      void loadReviewDetail(selectedReviewId, true)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [loadReviewDetail, selectedReview, selectedReviewId])

  useEffect(() => {
    if (!selectedReview) {
      setSelectedSourceRecordId(undefined)
      return
    }
    const candidate =
      selectedReview.source_records.find((item) => item.id === selectedSourceRecordId)
      ?? selectedReview.source_records.find((item) => item.id === selectedReview.proposed_survivor_source_record_id)
      ?? selectedReview.source_records[0]
      ?? null
    setSelectedSourceRecordId(candidate?.id)
  }, [selectedReview, selectedSourceRecordId])

  const runAction = useCallback(async (action: 'accept_merge' | 'choose_survivor' | 'mark_distinct') => {
    if (!selectedReview) {
      return
    }
    if (action === 'choose_survivor' && !selectedSourceRecordId) {
      message.error('Выберите source record для survivor resolution.')
      return
    }
    setActionName(action)
    try {
      const response = await applyPoolMasterDataDedupeReviewAction(selectedReview.id, {
        action,
        source_record_id: action === 'choose_survivor' ? selectedSourceRecordId : undefined,
        note: `Manual ${dedupeReviewActionLabels[action]} from Dedupe Review UI`,
        metadata: { source: 'ui' },
      })
      setSelectedReview(response.review_item)
      message.success(`Action ${dedupeReviewActionLabels[action]} выполнен.`)
      await loadReviewItems()
      await loadReviewDetail(selectedReview.id, true)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось выполнить dedupe review action.')
      message.error(resolved.message)
    } finally {
      setActionName(null)
    }
  }, [loadReviewDetail, loadReviewItems, message, selectedReview, selectedSourceRecordId])

  const queueColumns: ColumnsType<PoolMasterDataDedupeReviewItem> = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: PoolMasterDataDedupeReviewStatus) => (
        <Tag color={REVIEW_STATUS_COLORS[value] || 'default'}>{value}</Tag>
      ),
    },
    {
      title: 'Entity',
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 160,
      render: (value: string) => getRegistryEntityLabel(registryEntries, value),
    },
    {
      title: 'Databases',
      key: 'databases',
      width: 260,
      render: (_value, row) => {
        const names = [...new Set(
          row.source_records
            .map((item) => item.source_database_name || databaseNameById.get(item.source_database_id || '') || '')
            .filter((item) => item.length > 0)
        )]
        return names.length > 0 ? names.join(', ') : '-'
      },
    },
    {
      title: 'Reason',
      dataIndex: 'reason_code',
      key: 'reason_code',
      width: 220,
      render: (value: string) => <Tag color="gold">{value}</Tag>,
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
  ]

  const sourceColumns: ColumnsType<PoolMasterDataSourceRecord> = [
    {
      title: 'Survivor',
      key: 'survivor',
      width: 90,
      render: (_value, row) => (
        <input
          type="radio"
          name="dedupe-survivor"
          checked={selectedSourceRecordId === row.id}
          onChange={() => setSelectedSourceRecordId(row.id)}
          aria-label={`Use ${row.source_ref} as survivor`}
        />
      ),
    },
    {
      title: 'Database',
      key: 'source_database_name',
      width: 220,
      render: (_value, row) => row.source_database_name || databaseNameById.get(row.source_database_id || '') || '-',
    },
    { title: 'Source Ref', dataIndex: 'source_ref', key: 'source_ref', width: 200 },
    { title: 'Source Canonical ID', dataIndex: 'source_canonical_id', key: 'source_canonical_id', width: 180 },
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 180 },
    {
      title: 'Resolution',
      dataIndex: 'resolution_status',
      key: 'resolution_status',
      width: 160,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: 'Origin',
      key: 'origin',
      width: 220,
      render: (_value, row) => `${row.origin_kind || '-'}:${row.origin_ref || '-'}`,
    },
  ]
  const bindingColumns: ColumnsType<PoolMasterDataDedupeAffectedBinding> = [
    { title: 'Database', dataIndex: 'database_name', key: 'database_name', width: 220 },
    { title: 'IB Ref', dataIndex: 'ib_ref_key', key: 'ib_ref_key', width: 200 },
    {
      title: 'Scope',
      key: 'scope',
      width: 280,
      render: (_value, row) => {
        if (row.ib_catalog_kind) {
          return row.ib_catalog_kind
        }
        if (row.owner_counterparty_canonical_id) {
          return row.owner_counterparty_canonical_id
        }
        if (row.chart_identity) {
          return row.chart_identity
        }
        return '-'
      },
    },
    {
      title: 'Sync Status',
      dataIndex: 'sync_status',
      key: 'sync_status',
      width: 140,
      render: (value: string) => <Tag>{value || '-'}</Tag>,
    },
  ]
  const runtimeBlockerColumns: ColumnsType<PoolMasterDataDedupeRuntimeBlocker> = [
    {
      title: 'Blocker',
      dataIndex: 'label',
      key: 'label',
      width: 220,
      render: (value: string, row) => <Tag color="warning">{value || row.code}</Tag>,
    },
    { title: 'Detail', dataIndex: 'detail', key: 'detail' },
  ]

  const detailExtra = selectedReview ? (
    <Space>
      <Button
        onClick={() => void runAction('accept_merge')}
        loading={actionName === 'accept_merge'}
        disabled={selectedReview.status !== 'pending_review'}
      >
        Accept Merge
      </Button>
      <Button
        onClick={() => void runAction('choose_survivor')}
        loading={actionName === 'choose_survivor'}
        disabled={selectedReview.status !== 'pending_review' || !selectedSourceRecordId}
      >
        Choose Survivor
      </Button>
      <Button
        danger
        onClick={() => void runAction('mark_distinct')}
        loading={actionName === 'mark_distinct'}
        disabled={selectedReview.status !== 'pending_review'}
      >
        Mark Distinct
      </Button>
    </Space>
  ) : null

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="Database"
            data-testid="dedupe-review-database-filter"
            value={databaseId}
            options={databases.map((database) => ({ value: database.id, label: database.name }))}
            onChange={(value) => setDatabaseId(value)}
            style={{ width: 260 }}
          />
          <Select
            allowClear
            placeholder="Entity type"
            data-testid="dedupe-review-entity-filter"
            value={entityType}
            options={entityTypeOptions}
            onChange={(value) => setEntityType(value)}
            style={{ width: 180 }}
          />
          <Select
            allowClear
            placeholder="Status"
            data-testid="dedupe-review-status-filter"
            value={status}
            options={REVIEW_STATUS_OPTIONS}
            onChange={(value) => setStatus(value)}
            style={{ width: 180 }}
          />
          <Input
            allowClear
            placeholder="Reason code"
            data-testid="dedupe-review-reason-filter"
            value={reasonCode}
            onChange={(event) => {
              const value = event.target.value.trim()
              setReasonCode(value || undefined)
            }}
            style={{ width: 220 }}
          />
          <Button onClick={() => void loadReviewItems()} loading={loading}>
            Refresh
          </Button>
        </Space>
        <Text type="secondary">
          Review unresolved cross-infobase matches, inspect provenance, and resolve canonical survivor decisions without leaving the master-data workspace.
        </Text>
      </Card>

      <Card title="Review Queue">
        <Table
          rowKey="id"
          loading={loading}
          columns={queueColumns}
          dataSource={reviewItems}
          pagination={false}
          size="small"
          scroll={{ x: 1000 }}
          onRow={(record) => ({
            onClick: () => setSelectedReviewId(record.id),
          })}
        />
      </Card>

      <Card title="Review Detail" extra={detailExtra}>
        {!selectedReview ? (
          <Empty description="No dedupe review item selected." />
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {selectedReview.status === 'pending_review' ? (
              <Alert
                type="warning"
                showIcon
                message="Rollout and publication are blocked until this review is resolved."
                description={selectedReview.cluster.reason_detail || selectedReviewDetailText || 'Operator review is required.'}
              />
            ) : null}

            <Descriptions size="small" bordered column={3}>
              <Descriptions.Item label="Entity">
                {getRegistryEntityLabel(registryEntries, selectedReview.entity_type)}
              </Descriptions.Item>
              <Descriptions.Item label="Review Status">
                <Tag color={REVIEW_STATUS_COLORS[selectedReview.status] || 'default'}>{selectedReview.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Cluster Status">
                <Tag>{selectedReview.cluster.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Canonical ID">
                {selectedReview.cluster.canonical_id || <Text type="secondary">-</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="Reason Code">
                <Text code>{selectedReview.reason_code}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Conflicting Fields">
                {selectedReview.conflicting_fields.length > 0
                  ? selectedReview.conflicting_fields.join(', ')
                  : <Text type="secondary">-</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="Review Item ID">{selectedReview.id}</Descriptions.Item>
              <Descriptions.Item label="Cluster ID">{selectedReview.cluster_id}</Descriptions.Item>
              <Descriptions.Item label="Resolved At">{formatDateTime(selectedReview.resolved_at)}</Descriptions.Item>
            </Descriptions>

            <Table
              rowKey="id"
              loading={loadingDetail}
              size="small"
              pagination={false}
              columns={sourceColumns}
              dataSource={selectedReview.source_records}
              scroll={{ x: 1250 }}
              onRow={(record) => ({
                onClick: () => setSelectedSourceRecordId(record.id),
              })}
            />

            <Card title="Affected Bindings" size="small">
              <Table
                rowKey="id"
                size="small"
                pagination={false}
                columns={bindingColumns}
                dataSource={selectedReview.affected_bindings ?? []}
                locale={{ emptyText: 'No affected bindings.' }}
                scroll={{ x: 900 }}
              />
            </Card>

            <Card title="Runtime Blockers" size="small">
              <Table
                rowKey="code"
                size="small"
                pagination={false}
                columns={runtimeBlockerColumns}
                dataSource={selectedReview.runtime_blockers ?? []}
                locale={{ emptyText: 'No runtime blockers.' }}
              />
            </Card>

            <JsonBlock title="Cluster Signals" value={selectedReview.cluster.normalized_signals ?? {}} />
            <JsonBlock title="Review Metadata" value={selectedReview.metadata ?? {}} />
            <JsonBlock
              title="Selected Source Signals"
              value={selectedSourceRecord?.normalized_signals ?? {}}
            />
            <JsonBlock
              title="Selected Source Payload"
              value={selectedSourceRecord?.payload_snapshot ?? {}}
            />
          </Space>
        )}
      </Card>
    </Space>
  )
}
