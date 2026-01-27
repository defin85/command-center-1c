import { Alert, Button, Card, Descriptions, Drawer, Space, Tag, Typography } from 'antd'
import { ExportOutlined, LinkOutlined } from '@ant-design/icons'

import type { NodeStatus } from '../../../hooks/useWorkflowExecution'

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
  return (
    <Drawer
      title={selectedNode?.nodeName || 'Node Details'}
      open={open}
      onClose={onClose}
      width={400}
    >
      {selectedNode && (
        <div className="node-details">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Node ID">
              <Text copyable className="mono-text">
                {selectedNode.nodeId}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={
                selectedNode.status.status === 'completed' ? 'success' :
                selectedNode.status.status === 'failed' ? 'error' :
                selectedNode.status.status === 'running' ? 'processing' :
                selectedNode.status.status === 'skipped' ? 'warning' :
                'default'
              }>
                {selectedNode.status.status}
              </Tag>
            </Descriptions.Item>
            {selectedNode.status.startedAt && (
              <Descriptions.Item label="Started">
                {new Date(selectedNode.status.startedAt).toLocaleString()}
              </Descriptions.Item>
            )}
            {selectedNode.status.completedAt && (
              <Descriptions.Item label="Completed">
                {new Date(selectedNode.status.completedAt).toLocaleString()}
              </Descriptions.Item>
            )}
            {selectedNode.status.durationMs !== undefined && (
              <Descriptions.Item label="Duration">
                {(selectedNode.status.durationMs / 1000).toFixed(3)}s
              </Descriptions.Item>
            )}
            {selectedNode.status.spanId && (
              <Descriptions.Item label="Span ID">
                <Text copyable className="mono-text">
                  {selectedNode.status.spanId}
                </Text>
              </Descriptions.Item>
            )}
          </Descriptions>

          {selectedNode.status.output && (
            <Card title="Output" size="small" className="detail-card">
              <pre className="json-output">
                {JSON.stringify(selectedNode.status.output, null, 2)}
              </pre>
            </Card>
          )}

          {selectedNode.status.error && (
            <Alert
              type="error"
              message="Error"
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
                View Trace Details
              </Button>
              <Button
                type="link"
                icon={<ExportOutlined />}
                href={`${jaegerUiUrl}/trace/${traceId}?uiFind=${selectedNode.status.spanId}`}
                target="_blank"
                className="trace-link"
              >
                Open in Jaeger
              </Button>
            </Space>
          )}
        </div>
      )}
    </Drawer>
  )
}
