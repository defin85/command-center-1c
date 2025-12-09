/**
 * LiveMonitorTab - Real-time SSE monitor embedded in Operations page.
 * Integrates WorkflowTracker with useOperationStream hook.
 */

import { useState, useEffect } from 'react'
import { Input, Button, Space, Typography, Alert, Card } from 'antd'
import { SearchOutlined, DisconnectOutlined, LinkOutlined } from '@ant-design/icons'
import { useOperationStream } from '../../../hooks/useOperationStream'
import { WorkflowTracker } from '../../../components/WorkflowTracker'
import type { LiveMonitorTabProps } from '../types'

const { Text } = Typography

/**
 * LiveMonitorTab - SSE-based real-time operation monitoring
 *
 * Features:
 * - Auto-connect when operationId prop is provided
 * - Manual input for Operation ID
 * - Real-time workflow visualization via WorkflowTracker
 * - Connection status indicator
 */
export const LiveMonitorTab = ({ operationId: propOperationId }: LiveMonitorTabProps) => {
  // Internal state for connection management
  const [connectedOperationId, setConnectedOperationId] = useState<string | null>(
    propOperationId || null
  )
  const [inputValue, setInputValue] = useState(propOperationId || '')

  // SSE hook
  const { events, currentState, error, isConnected } = useOperationStream(connectedOperationId)

  // Auto-connect when prop changes (e.g., from clicking "Monitor" in details modal)
  useEffect(() => {
    if (propOperationId && propOperationId !== connectedOperationId) {
      setConnectedOperationId(propOperationId)
      setInputValue(propOperationId)
    }
  }, [propOperationId, connectedOperationId])

  const handleConnect = () => {
    const trimmed = inputValue.trim()
    if (trimmed) {
      setConnectedOperationId(trimmed)
    }
  }

  const handleDisconnect = () => {
    setConnectedOperationId(null)
    // Keep inputValue for convenience (user might want to reconnect)
  }

  const handleClear = () => {
    setConnectedOperationId(null)
    setInputValue('')
  }

  return (
    <div>
      {/* Connection Controls */}
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* Input + Buttons */}
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="Enter Operation ID (UUID)"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPressEnter={handleConnect}
              disabled={!!connectedOperationId}
              prefix={<SearchOutlined />}
              allowClear={!connectedOperationId}
              onClear={handleClear}
            />
            {!connectedOperationId ? (
              <Button
                type="primary"
                onClick={handleConnect}
                disabled={!inputValue.trim()}
                icon={<LinkOutlined />}
              >
                Connect
              </Button>
            ) : (
              <Button
                onClick={handleDisconnect}
                danger
                icon={<DisconnectOutlined />}
              >
                Disconnect
              </Button>
            )}
          </Space.Compact>

          {/* Connection Status */}
          {connectedOperationId && (
            <Alert
              message={
                <Space>
                  <Text strong>Connected to operation:</Text>
                  <Text code copyable={{ text: connectedOperationId }}>
                    {connectedOperationId}
                  </Text>
                </Space>
              }
              description={
                isConnected
                  ? 'Real-time updates active via Server-Sent Events'
                  : 'Connecting...'
              }
              type={isConnected ? 'success' : 'info'}
              showIcon
            />
          )}

          {/* Error Alert */}
          {error && (
            <Alert
              message="Connection Error"
              description={error}
              type="error"
              showIcon
            />
          )}
        </Space>
      </Card>

      {/* Workflow Tracker */}
      {connectedOperationId && (
        <Card
          title={
            <Space>
              <span>Workflow Visualization</span>
              <Text type="secondary" style={{ fontSize: 14, fontWeight: 'normal' }}>
                Current state: <strong>{currentState}</strong>
              </Text>
            </Space>
          }
        >
          <WorkflowTracker
            events={events}
            currentState={currentState}
            error={error}
            isConnected={isConnected}
          />
        </Card>
      )}

      {/* Help Card - shown when not connected */}
      {!connectedOperationId && (
        <Card title="How to Use Live Monitor">
          <Space direction="vertical" size="middle">
            <div>
              <Text strong>Option 1: From Operations List</Text>
              <Text type="secondary" style={{ display: 'block' }}>
                Click on any operation in the "All Operations" tab, then click "Monitor Workflow"
                button in the details modal.
              </Text>
            </div>
            <div>
              <Text strong>Option 2: Manual Connection</Text>
              <Text type="secondary" style={{ display: 'block' }}>
                Enter an Operation ID (UUID) in the input field above and click "Connect".
              </Text>
            </div>
            <div>
              <Text strong>What You'll See</Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Visual workflow diagram with current state highlighted
              </Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Timeline of all events in chronological order
              </Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Real-time updates via Server-Sent Events (SSE)
              </Text>
            </div>
          </Space>
        </Card>
      )}
    </div>
  )
}
