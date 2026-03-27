import { useEffect, useState } from 'react'
import { Button, Descriptions, Space, Typography } from 'antd'

import type { OrganizationPool } from '../../api/intercompanyPools'
import { EntityTable, RouteButton, StatusBadge } from '../../components/platform'
import {
  applyPoolFactualReviewAction,
  buildDemoPoolFactualReviewQueue,
  getPoolFactualReviewActionLabel,
  getPoolFactualReviewReasonLabel,
  getPoolFactualReviewStatusTone,
  type PoolFactualReviewAction,
  type PoolFactualReviewRow,
} from './poolFactualReviewQueue'


const { Text } = Typography

type PoolFactualWorkspaceDetailProps = {
  selectedPool: OrganizationPool
  focus: 'summary' | 'settlement' | 'drilldown' | 'review'
  runId: string | null
  poolCatalogHref: string
  runWorkspaceHref: string
}

type EmptyRow = {
  id: string
}

const EMPTY_ROWS: EmptyRow[] = []

const settlementColumns = [
  {
    title: 'Batch',
    dataIndex: 'id',
    key: 'id',
    render: () => <Text type="secondary">Pending factual API</Text>,
  },
  {
    title: 'Status',
    key: 'status',
    render: () => <StatusBadge status="unknown" label="pending" />,
  },
  {
    title: 'Open balance',
    key: 'open_balance',
    render: () => <Text type="secondary">Awaiting projection</Text>,
  },
]

const edgeColumns = [
  {
    title: 'Edge',
    dataIndex: 'id',
    key: 'id',
    render: () => <Text type="secondary">Awaiting edge balances</Text>,
  },
  {
    title: 'Incoming',
    key: 'incoming',
    render: () => <Text type="secondary">Pending factual API</Text>,
  },
  {
    title: 'Open balance',
    key: 'open_balance',
    render: () => <Text type="secondary">Pending factual API</Text>,
  },
]

export function PoolFactualWorkspaceDetail({
  selectedPool,
  focus,
  runId,
  poolCatalogHref,
  runWorkspaceHref,
}: PoolFactualWorkspaceDetailProps) {
  const [reviewRows, setReviewRows] = useState<PoolFactualReviewRow[]>(() =>
    buildDemoPoolFactualReviewQueue(selectedPool.code)
  )

  useEffect(() => {
    setReviewRows(buildDemoPoolFactualReviewQueue(selectedPool.code))
  }, [selectedPool.code, selectedPool.id])

  const reviewSummary = {
    pendingTotal: reviewRows.filter((row) => row.status === 'pending').length,
    attentionRequiredTotal: reviewRows.filter((row) => row.attentionRequired).length,
  }

  const handleReviewAction = (itemId: string, action: PoolFactualReviewAction) => {
    setReviewRows((current) => applyPoolFactualReviewAction(current, itemId, action))
  }

  const reviewColumns = [
    {
      title: 'Reason',
      dataIndex: 'reason',
      key: 'reason',
      render: (_: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <StatusBadge status={getPoolFactualReviewStatusTone(row)} label={getPoolFactualReviewReasonLabel(row.reason)} />
          <Text type="secondary">{row.quarter}</Text>
        </Space>
      ),
    },
    {
      title: 'Document',
      dataIndex: 'sourceDocumentRef',
      key: 'sourceDocumentRef',
      render: (value: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <Text>{value}</Text>
          <Text type="secondary">{row.summary}</Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (_: string, row: PoolFactualReviewRow) => (
        <Space direction="vertical" size={4}>
          <StatusBadge status={getPoolFactualReviewStatusTone(row)} label={row.status} />
          {row.attentionRequired ? <Text type="secondary">attention required</Text> : null}
        </Space>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: unknown, row: PoolFactualReviewRow) => (
        row.allowedActions.length > 0 ? (
          <Space wrap>
            {row.allowedActions.map((action) => (
              <Button
                key={action}
                size="small"
                type={action === 'resolve_without_change' ? 'default' : 'primary'}
                aria-label={`${getPoolFactualReviewActionLabel(action)} review item ${row.id}`}
                onClick={() => handleReviewAction(row.id, action)}
              >
                {getPoolFactualReviewActionLabel(action)}
              </Button>
            ))}
          </Space>
        ) : (
          <Text type="secondary">Closed in factual workspace</Text>
        )
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Descriptions bordered size="small" column={2}>
        <Descriptions.Item label="Pool" span={1}>
          <Text>{selectedPool.name}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Code" span={1}>
          <Text code>{selectedPool.code}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Linked run" span={1}>
          <Text code>{runId ?? '-'}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Workspace contract" span={1}>
          <Text>factual summary / settlement / review</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Focused section" span={1}>
          <Text>{focus}</Text>
        </Descriptions.Item>
      </Descriptions>

      {runId && focus === 'settlement' ? (
        <div
          style={{
            border: '1px solid #d9f7be',
            borderRadius: 12,
            padding: 16,
            background: '#f6ffed',
          }}
        >
          <Space direction="vertical" size={8}>
            <Space wrap>
              <Text strong>Run-linked settlement handoff</Text>
              <StatusBadge status="active" label="focus=settlement" />
            </Space>
            <Text type="secondary">
              This deep link keeps the operator in factual dashboard context while starting from the linked run
              report and its batch settlement handoff.
            </Text>
          </Space>
        </div>
      ) : null}

      <div
        style={{
          display: 'grid',
          gap: 16,
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        }}
      >
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Quarter summary</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge status="unknown" label="awaiting API" />
              <Text type="secondary">
                Inbound, closed, and carry-forward totals will land here once the factual read-model route is wired.
              </Text>
            </Space>
          </div>
        </div>
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Freshness</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge status="warning" label="not connected" />
              <Text type="secondary">
                This card will surface near-real-time lag, blocked external sessions, and maintenance windows.
              </Text>
            </Space>
          </div>
        </div>
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Settlement handoff</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge status="unknown" label="batch queue pending" />
              <Text type="secondary">
                Receipt distribution and closing sale handoff stays visible here without mixing execution diagnostics.
              </Text>
            </Space>
          </div>
        </div>
        <div
          style={{
            border: '1px solid #f0f0f0',
            borderRadius: 12,
            padding: 16,
            background: '#fff',
          }}
        >
          <Text strong>Review queue</Text>
          <div style={{ marginTop: 12 }}>
            <Space direction="vertical" size={8}>
              <StatusBadge
                status={reviewSummary.attentionRequiredTotal > 0 ? 'warning' : 'active'}
                label={`${reviewSummary.pendingTotal} pending`}
              />
              <Text type="secondary">
                Unattributed documents and late corrections stay in this route instead of the run-local canvas.
                {` ${reviewSummary.attentionRequiredTotal} item(s) currently require manual reconcile.`}
              </Text>
            </Space>
          </div>
        </div>
      </div>

      <EntityTable
        title="Batch settlement"
        extra={(
          <Space wrap>
            {focus === 'settlement' ? <StatusBadge status="active" label="run-linked focus" /> : null}
            <RouteButton to={runWorkspaceHref}>Open linked run context</RouteButton>
          </Space>
        )}
        dataSource={EMPTY_ROWS}
        columns={settlementColumns}
        rowKey="id"
        emptyDescription="Settlement summary appears here once factual read-model API is connected."
      />

      <EntityTable
        title="Edge drill-down"
        extra={<RouteButton to={poolCatalogHref}>Open pool topology context</RouteButton>}
        dataSource={EMPTY_ROWS}
        columns={edgeColumns}
        rowKey="id"
        emptyDescription="Edge-level incoming, outgoing, and stuck balance diagnostics appear here when projection data is available."
      />

      <EntityTable
        title="Manual review queue"
        extra={focus === 'review' ? <StatusBadge status="active" label="review focus" /> : null}
        dataSource={reviewRows}
        columns={reviewColumns}
        rowKey="id"
        emptyDescription="Unattributed and late-correction review stays isolated here until the review API is delivered."
      />
    </Space>
  )
}
