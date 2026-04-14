import { Alert, Button, Card, Descriptions, Drawer, Space, Tag, Typography } from 'antd'
import { ExportOutlined, LinkOutlined } from '@ant-design/icons'

import type { NodeStatus } from '../../../hooks/useWorkflowExecution'
import { useLocaleFormatters, useWorkflowTranslation } from '../../../i18n'

const { Text } = Typography

export interface NodeDetails {
  nodeId: string
  nodeName: string
  status: NodeStatus
}

export function NodeDetailsDrawer({
  open,
  selectedNode,
  traceId,
  jaegerUiUrl,
  onClose,
  onOpenTraceDetails,
}: {
  open: boolean
  selectedNode: NodeDetails | null
  traceId: string | null
  jaegerUiUrl: string
  onClose: () => void
  onOpenTraceDetails: (nodeId: string) => void
}) {
  const { t } = useWorkflowTranslation()
  const formatters = useLocaleFormatters()

  return (
    <Drawer
      title={selectedNode?.nodeName || t('nodeDetails.title')}
      open={open}
      onClose={onClose}
      width={400}
    >
      {selectedNode && (
        <div className="node-details">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label={t('nodeDetails.fields.nodeId')}>
              <Text copyable className="mono-text">
                {selectedNode.nodeId}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label={t('nodeDetails.fields.status')}>
              <Tag color={
                selectedNode.status.status === 'completed' ? 'success' :
                selectedNode.status.status === 'failed' ? 'error' :
                selectedNode.status.status === 'running' ? 'processing' :
                selectedNode.status.status === 'skipped' ? 'warning' :
                'default'
              }>
                {t(`statuses.${selectedNode.status.status}`)}
              </Tag>
            </Descriptions.Item>
            {selectedNode.status.startedAt && (
              <Descriptions.Item label={t('nodeDetails.fields.started')}>
                {formatters.dateTime(selectedNode.status.startedAt, { fallback: t('common.notAvailable') })}
              </Descriptions.Item>
            )}
            {selectedNode.status.completedAt && (
              <Descriptions.Item label={t('nodeDetails.fields.completed')}>
                {formatters.dateTime(selectedNode.status.completedAt, { fallback: t('common.notAvailable') })}
              </Descriptions.Item>
            )}
            {selectedNode.status.durationMs !== undefined && (
              <Descriptions.Item label={t('nodeDetails.fields.duration')}>
                {(selectedNode.status.durationMs / 1000).toFixed(3)}s
              </Descriptions.Item>
            )}
            {selectedNode.status.spanId && (
              <Descriptions.Item label={t('nodeDetails.fields.spanId')}>
                <Text copyable className="mono-text">
                  {selectedNode.status.spanId}
                </Text>
              </Descriptions.Item>
            )}
          </Descriptions>

          {selectedNode.status.output && (
            <Card title={t('nodeDetails.output')} size="small" className="detail-card">
              <pre className="json-output">
                {JSON.stringify(selectedNode.status.output, null, 2)}
              </pre>
            </Card>
          )}

          {selectedNode.status.error && (
            <Alert
              type="error"
              message={t('nodeDetails.error')}
              description={selectedNode.status.error}
              showIcon
              className="error-detail"
            />
          )}

          {selectedNode.status.spanId && traceId && (
            <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
              <Button
                type="primary"
                icon={<LinkOutlined />}
                onClick={() => onOpenTraceDetails(selectedNode.nodeId)}
                block
              >
                {t('nodeDetails.viewTraceDetails')}
              </Button>
              <Button
                type="link"
                icon={<ExportOutlined />}
                onClick={() => {
                  window.open(
                    `${jaegerUiUrl}/trace/${traceId}?uiFind=${selectedNode.status.spanId}`,
                    '_blank',
                    'noopener,noreferrer'
                  )
                }}
                className="trace-link"
              >
                {t('nodeDetails.openInJaeger')}
              </Button>
            </Space>
          )}
        </div>
      )}
    </Drawer>
  )
}
