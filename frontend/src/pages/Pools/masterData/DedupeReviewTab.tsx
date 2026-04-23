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
import { usePoolsTranslation } from '../../../i18n'
import { buildUiRouteParamDiff, queueUiRouteWrite } from '../../../observability/uiActionJournal'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { getDedupeEntityOptions, getRegistryEntityLabel } from './registry'

const { Text } = Typography

const REVIEW_STATUS_COLORS: Record<PoolMasterDataDedupeReviewStatus, string> = {
  pending_review: 'warning',
  resolved_auto: 'success',
  resolved_manual: 'processing',
  superseded: 'default',
}

type DedupeReviewTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

export function DedupeReviewTab({ registryEntries }: DedupeReviewTabProps) {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
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
  const reviewStatusOptions = useMemo<Array<{ value: PoolMasterDataDedupeReviewStatus; label: string }>>(
    () => [
      { value: 'pending_review', label: t('masterData.dedupeReviewTab.status.pendingReview') },
      { value: 'resolved_auto', label: t('masterData.dedupeReviewTab.status.resolvedAuto') },
      { value: 'resolved_manual', label: t('masterData.dedupeReviewTab.status.resolvedManual') },
      { value: 'superseded', label: t('masterData.dedupeReviewTab.status.superseded') },
    ],
    [t]
  )
  const dedupeReviewActionLabels = useMemo<Record<'accept_merge' | 'choose_survivor' | 'mark_distinct', string>>(
    () => ({
      accept_merge: t('masterData.dedupeReviewTab.actions.acceptMerge'),
      choose_survivor: t('masterData.dedupeReviewTab.actions.chooseSurvivor'),
      mark_distinct: t('masterData.dedupeReviewTab.actions.markDistinct'),
    }),
    [t]
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
      const paramDiff = buildUiRouteParamDiff(searchParams, syncRouteContext)
      const diffKeys = Object.keys(paramDiff)
      const writeReason = diffKeys.includes('reviewItemId')
        ? 'review_selection_sync'
        : diffKeys.includes('clusterId')
          ? 'cluster_context_sync'
          : diffKeys.includes('databaseId') || diffKeys.includes('entityType')
            ? 'dedupe_filter_sync'
            : 'dedupe_state_sync'
      queueUiRouteWrite({
        surfaceId: 'pool_master_data',
        routeWriterOwner: 'dedupe_review_tab',
        writeReason,
        navigationMode: 'replace',
        paramDiff,
      })
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
      const resolved = resolveApiError(error, t('masterData.dedupeReviewTab.messages.failedToLoadDatabases'))
      message.error(resolved.message)
    }
  }, [message, t])

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
      const resolved = resolveApiError(error, t('masterData.dedupeReviewTab.messages.failedToLoadQueue'))
      message.error(resolved.message)
    } finally {
      setLoading(false)
    }
  }, [databaseId, entityType, message, reasonCode, reviewItemIdFromUrl, routeClusterId, status, t])

  const loadReviewDetail = useCallback(async (reviewItemId: string, silent = false) => {
    if (!silent) {
      setLoadingDetail(true)
    }
    try {
      const response = await getPoolMasterDataDedupeReviewItem(reviewItemId)
      setSelectedReview(response.review_item)
    } catch (error) {
      if (!silent) {
        const resolved = resolveApiError(error, t('masterData.dedupeReviewTab.messages.failedToLoadDetail'))
        message.error(resolved.message)
      }
    } finally {
      if (!silent) {
        setLoadingDetail(false)
      }
    }
  }, [message, t])

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
      message.error(t('masterData.dedupeReviewTab.messages.selectSourceRecord'))
      return
    }
    setActionName(action)
    try {
      const response = await applyPoolMasterDataDedupeReviewAction(selectedReview.id, {
        action,
        source_record_id: action === 'choose_survivor' ? selectedSourceRecordId : undefined,
        note: t('masterData.dedupeReviewTab.messages.actionNote', { action: dedupeReviewActionLabels[action].toLowerCase() }),
        metadata: { source: 'ui' },
      })
      setSelectedReview(response.review_item)
      message.success(t('masterData.dedupeReviewTab.messages.actionCompleted', { action: dedupeReviewActionLabels[action] }))
      await loadReviewItems()
      await loadReviewDetail(selectedReview.id, true)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.dedupeReviewTab.messages.failedToRunAction'))
      message.error(resolved.message)
    } finally {
      setActionName(null)
    }
  }, [dedupeReviewActionLabels, loadReviewDetail, loadReviewItems, message, selectedReview, selectedSourceRecordId, t])

  const queueColumns: ColumnsType<PoolMasterDataDedupeReviewItem> = [
    {
      title: t('masterData.dedupeReviewTab.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: PoolMasterDataDedupeReviewStatus) => (
        <Tag color={REVIEW_STATUS_COLORS[value] || 'default'}>
          {reviewStatusOptions.find((option) => option.value === value)?.label || value}
        </Tag>
      ),
    },
    {
      title: t('masterData.dedupeReviewTab.columns.entity'),
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 160,
      render: (value: string) => getRegistryEntityLabel(registryEntries, value),
    },
    {
      title: t('masterData.dedupeReviewTab.columns.databases'),
      key: 'databases',
      width: 260,
      render: (_value, row) => {
        const names = [...new Set(
          row.source_records
            .map((item) => item.source_database_name || databaseNameById.get(item.source_database_id || '') || '')
            .filter((item) => item.length > 0)
        )]
        return names.length > 0 ? names.join(', ') : t('common.noValue')
      },
    },
    {
      title: t('masterData.dedupeReviewTab.columns.reason'),
      dataIndex: 'reason_code',
      key: 'reason_code',
      width: 220,
      render: (value: string) => <Tag color="gold">{value}</Tag>,
    },
    {
      title: t('masterData.dedupeReviewTab.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
  ]

  const sourceColumns: ColumnsType<PoolMasterDataSourceRecord> = [
    {
      title: t('masterData.dedupeReviewTab.columns.survivor'),
      key: 'survivor',
      width: 90,
      render: (_value, row) => (
        <input
          type="radio"
          name="dedupe-survivor"
          checked={selectedSourceRecordId === row.id}
          onChange={() => setSelectedSourceRecordId(row.id)}
          aria-label={t('masterData.dedupeReviewTab.actions.useSourceAsSurvivor', { sourceRef: row.source_ref })}
        />
      ),
    },
    {
      title: t('masterData.dedupeReviewTab.columns.database'),
      key: 'source_database_name',
      width: 220,
      render: (_value, row) => row.source_database_name || databaseNameById.get(row.source_database_id || '') || t('common.noValue'),
    },
    { title: t('masterData.dedupeReviewTab.columns.sourceRef'), dataIndex: 'source_ref', key: 'source_ref', width: 200 },
    { title: t('masterData.dedupeReviewTab.columns.sourceCanonicalId'), dataIndex: 'source_canonical_id', key: 'source_canonical_id', width: 180 },
    { title: t('masterData.dedupeReviewTab.columns.canonicalId'), dataIndex: 'canonical_id', key: 'canonical_id', width: 180 },
    {
      title: t('masterData.dedupeReviewTab.columns.resolution'),
      dataIndex: 'resolution_status',
      key: 'resolution_status',
      width: 160,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: t('masterData.dedupeReviewTab.columns.origin'),
      key: 'origin',
      width: 220,
      render: (_value, row) => `${row.origin_kind || t('common.noValue')}:${row.origin_ref || t('common.noValue')}`,
    },
  ]
  const bindingColumns: ColumnsType<PoolMasterDataDedupeAffectedBinding> = [
    { title: t('masterData.dedupeReviewTab.columns.database'), dataIndex: 'database_name', key: 'database_name', width: 220 },
    { title: t('masterData.dedupeReviewTab.columns.ibRef'), dataIndex: 'ib_ref_key', key: 'ib_ref_key', width: 200 },
    {
      title: t('masterData.dedupeReviewTab.columns.scope'),
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
        return t('common.noValue')
      },
    },
    {
      title: t('masterData.dedupeReviewTab.columns.syncStatus'),
      dataIndex: 'sync_status',
      key: 'sync_status',
      width: 140,
      render: (value: string) => <Tag>{value || t('common.noValue')}</Tag>,
    },
  ]
  const runtimeBlockerColumns: ColumnsType<PoolMasterDataDedupeRuntimeBlocker> = [
    {
      title: t('masterData.dedupeReviewTab.columns.blocker'),
      dataIndex: 'label',
      key: 'label',
      width: 220,
      render: (value: string, row) => <Tag color="warning">{value || row.code}</Tag>,
    },
    { title: t('masterData.dedupeReviewTab.columns.detail'), dataIndex: 'detail', key: 'detail' },
  ]

  const detailExtra = selectedReview ? (
    <Space>
      <Button
        onClick={() => void runAction('accept_merge')}
        loading={actionName === 'accept_merge'}
        disabled={selectedReview.status !== 'pending_review'}
      >
        {t('masterData.dedupeReviewTab.actions.acceptMerge')}
      </Button>
      <Button
        onClick={() => void runAction('choose_survivor')}
        loading={actionName === 'choose_survivor'}
        disabled={selectedReview.status !== 'pending_review' || !selectedSourceRecordId}
      >
        {t('masterData.dedupeReviewTab.actions.chooseSurvivor')}
      </Button>
      <Button
        danger
        onClick={() => void runAction('mark_distinct')}
        loading={actionName === 'mark_distinct'}
        disabled={selectedReview.status !== 'pending_review'}
      >
        {t('masterData.dedupeReviewTab.actions.markDistinct')}
      </Button>
    </Space>
  ) : null

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder={t('masterData.dedupeReviewTab.filters.databasePlaceholder')}
            data-testid="dedupe-review-database-filter"
            value={databaseId}
            options={databases.map((database) => ({ value: database.id, label: database.name }))}
            onChange={(value) => setDatabaseId(value)}
            style={{ width: 260 }}
          />
          <Select
            allowClear
            placeholder={t('masterData.dedupeReviewTab.filters.entityTypePlaceholder')}
            data-testid="dedupe-review-entity-filter"
            value={entityType}
            options={entityTypeOptions}
            onChange={(value) => setEntityType(value)}
            style={{ width: 180 }}
          />
          <Select
            allowClear
            placeholder={t('masterData.dedupeReviewTab.filters.statusPlaceholder')}
            data-testid="dedupe-review-status-filter"
            value={status}
            options={reviewStatusOptions}
            onChange={(value) => setStatus(value)}
            style={{ width: 180 }}
          />
          <Input
            allowClear
            placeholder={t('masterData.dedupeReviewTab.filters.reasonCodePlaceholder')}
            data-testid="dedupe-review-reason-filter"
            value={reasonCode}
            onChange={(event) => {
              const value = event.target.value.trim()
              setReasonCode(value || undefined)
            }}
            style={{ width: 220 }}
          />
          <Button onClick={() => void loadReviewItems()} loading={loading}>
            {t('catalog.actions.refresh')}
          </Button>
        </Space>
        <Text type="secondary">
          {t('masterData.dedupeReviewTab.page.subtitle')}
        </Text>
      </Card>

      <Card title={t('masterData.dedupeReviewTab.page.queueTitle')}>
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

      <Card title={t('masterData.dedupeReviewTab.page.detailTitle')} extra={detailExtra}>
        {!selectedReview ? (
          <Empty description={t('masterData.dedupeReviewTab.page.emptyDescription')} />
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {selectedReview.status === 'pending_review' ? (
              <Alert
                type="warning"
                showIcon
                message={t('masterData.dedupeReviewTab.alerts.blockedTitle')}
                description={selectedReview.cluster.reason_detail || selectedReviewDetailText || t('masterData.dedupeReviewTab.alerts.blockedFallback')}
              />
            ) : null}

            <Descriptions size="small" bordered column={3}>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.entity')}>
                {getRegistryEntityLabel(registryEntries, selectedReview.entity_type)}
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.reviewStatus')}>
                <Tag color={REVIEW_STATUS_COLORS[selectedReview.status] || 'default'}>
                  {reviewStatusOptions.find((option) => option.value === selectedReview.status)?.label || selectedReview.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.clusterStatus')}>
                <Tag>{selectedReview.cluster.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.canonicalId')}>
                {selectedReview.cluster.canonical_id || <Text type="secondary">{t('common.noValue')}</Text>}
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.reasonCode')}>
                <Text code>{selectedReview.reason_code}</Text>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.conflictingFields')}>
                {selectedReview.conflicting_fields.length > 0
                  ? selectedReview.conflicting_fields.join(', ')
                  : <Text type="secondary">{t('common.noValue')}</Text>}
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.reviewItemId')}>{selectedReview.id}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.clusterId')}>{selectedReview.cluster_id}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.dedupeReviewTab.details.resolvedAt')}>{formatDateTime(selectedReview.resolved_at)}</Descriptions.Item>
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

            <Card title={t('masterData.dedupeReviewTab.page.affectedBindingsTitle')} size="small">
              <Table
                rowKey="id"
                size="small"
                pagination={false}
                columns={bindingColumns}
                dataSource={selectedReview.affected_bindings ?? []}
                locale={{ emptyText: t('masterData.dedupeReviewTab.page.noAffectedBindings') }}
                scroll={{ x: 900 }}
              />
            </Card>

            <Card title={t('masterData.dedupeReviewTab.page.runtimeBlockersTitle')} size="small">
              <Table
                rowKey="code"
                size="small"
                pagination={false}
                columns={runtimeBlockerColumns}
                dataSource={selectedReview.runtime_blockers ?? []}
                locale={{ emptyText: t('masterData.dedupeReviewTab.page.noRuntimeBlockers') }}
              />
            </Card>

            <JsonBlock title={t('masterData.dedupeReviewTab.page.clusterSignalsTitle')} value={selectedReview.cluster.normalized_signals ?? {}} />
            <JsonBlock title={t('masterData.dedupeReviewTab.page.reviewMetadataTitle')} value={selectedReview.metadata ?? {}} />
            <JsonBlock
              title={t('masterData.dedupeReviewTab.page.selectedSourceSignalsTitle')}
              value={selectedSourceRecord?.normalized_signals ?? {}}
            />
            <JsonBlock
              title={t('masterData.dedupeReviewTab.page.selectedSourcePayloadTitle')}
              value={selectedSourceRecord?.payload_snapshot ?? {}}
            />
          </Space>
        )}
      </Card>
    </Space>
  )
}
