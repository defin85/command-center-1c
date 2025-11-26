import React, { useState, useEffect } from 'react'
import { Card, Input, Button, Space, Typography, Alert } from 'antd'
import { SearchOutlined, MonitorOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { WorkflowTracker } from '../../components/WorkflowTracker'
import { useOperationStream } from '../../hooks/useOperationStream'

const { Title, Text } = Typography

export const OperationMonitor: React.FC = () => {
  const [searchParams] = useSearchParams()
  const operationFromUrl = searchParams.get('operation')

  const [operationId, setOperationId] = useState<string | null>(operationFromUrl)
  const [inputValue, setInputValue] = useState(operationFromUrl || '')

  const { events, currentState, error, isConnected } = useOperationStream(operationId)

  // Auto-connect if operation ID in URL
  useEffect(() => {
    if (operationFromUrl && !operationId) {
      setOperationId(operationFromUrl)
      setInputValue(operationFromUrl)
    }
  }, [operationFromUrl])

  const handleConnect = () => {
    if (inputValue.trim()) {
      setOperationId(inputValue.trim())
    }
  }

  const handleDisconnect = () => {
    setOperationId(null)
    setInputValue('')
  }

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <Title level={2} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
              <MonitorOutlined />
              Operation Workflow Monitor
            </Title>
            <Text type="secondary">
              Real-time мониторинг выполнения операций с визуализацией workflow
            </Text>
          </div>

          {/* Input для Operation ID */}
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="Введите Operation ID (UUID)"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPressEnter={handleConnect}
              size="large"
              disabled={!!operationId}
              prefix={<SearchOutlined />}
            />
            {!operationId ? (
              <Button
                type="primary"
                size="large"
                onClick={handleConnect}
                disabled={!inputValue.trim()}
              >
                Подключиться
              </Button>
            ) : (
              <Button
                size="large"
                onClick={handleDisconnect}
                danger
              >
                Отключиться
              </Button>
            )}
          </Space.Compact>

          {/* Connection info */}
          {operationId && (
            <Alert
              message={`Подключено к операции: ${operationId}`}
              description={isConnected ? 'Real-time обновления активны' : 'Подключение...'}
              type={isConnected ? 'success' : 'info'}
              showIcon
            />
          )}
        </Space>
      </Card>

      {/* Workflow Tracker */}
      {operationId && (
        <Card
          title={
            <Space>
              <span>Workflow Visualization</span>
              <Text type="secondary" style={{ fontSize: 14, fontWeight: 'normal' }}>
                Текущее состояние: <strong>{currentState}</strong>
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

      {/* Help */}
      {!operationId && (
        <Card title="Как использовать">
          <Space direction="vertical" size="middle">
            <div>
              <Text strong>1. Получить Operation ID</Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Запустите любую операцию (установка расширения, обновление БД и т.д.)
              </Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Скопируйте Operation ID из ответа API или списка операций
              </Text>
            </div>
            <div>
              <Text strong>2. Подключиться к мониторингу</Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Вставьте Operation ID в поле выше
              </Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Нажмите "Подключиться"
              </Text>
            </div>
            <div>
              <Text strong>3. Наблюдать workflow</Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Визуальная диаграмма покажет текущее состояние операции
              </Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Временная шкала отобразит все события в хронологическом порядке
              </Text>
              <Text type="secondary" style={{ display: 'block' }}>
                - Обновления поступают в real-time через Server-Sent Events
              </Text>
            </div>
          </Space>
        </Card>
      )}
    </div>
  )
}
