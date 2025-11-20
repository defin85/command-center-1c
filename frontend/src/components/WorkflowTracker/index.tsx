import React, { useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { WorkflowEvent } from '../../hooks/useOperationStream'
import { Alert } from 'antd'
import './styles.css'

interface WorkflowTrackerProps {
  events: WorkflowEvent[]
  currentState: string
  error: string | null
  isConnected: boolean
}

// Позиции состояний на canvas
const STATE_POSITIONS: Record<string, { x: number; y: number }> = {
  PENDING: { x: 50, y: 200 },
  QUEUED: { x: 250, y: 200 },
  PROCESSING: { x: 450, y: 200 },
  UPLOADING: { x: 650, y: 100 },
  INSTALLING: { x: 650, y: 200 },
  VERIFYING: { x: 650, y: 300 },
  SUCCESS: { x: 850, y: 200 },
  FAILED: { x: 850, y: 350 },
  TIMEOUT: { x: 850, y: 500 },
}

// Цвета состояний
const STATE_COLORS: Record<string, string> = {
  PENDING: '#d9d9d9',
  QUEUED: '#1890ff',
  PROCESSING: '#faad14',
  UPLOADING: '#faad14',
  INSTALLING: '#faad14',
  VERIFYING: '#faad14',
  SUCCESS: '#52c41a',
  FAILED: '#ff4d4f',
  TIMEOUT: '#fa8c16',
}

export const WorkflowTracker: React.FC<WorkflowTrackerProps> = ({
  events,
  currentState,
  error,
  isConnected,
}) => {
  // Создать nodes для State Machine
  const nodes: Node[] = useMemo(() => {
    return Object.entries(STATE_POSITIONS).map(([state, position]) => {
      const isActive = state === currentState
      const isPast = events.some((e) => e.state === state)

      return {
        id: state,
        position,
        data: {
          label: (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontWeight: 'bold', fontSize: '14px' }}>
                {state}
              </div>
              {isPast && (
                <div style={{ fontSize: '10px', color: '#666' }}>
                  {events.find((e) => e.state === state)?.microservice}
                </div>
              )}
            </div>
          ),
        },
        style: {
          background: isActive
            ? STATE_COLORS[state]
            : isPast
            ? '#f0f0f0'
            : '#fff',
          border: isActive ? '3px solid #1890ff' : '2px solid #d9d9d9',
          borderRadius: '8px',
          padding: '12px',
          width: 140,
          boxShadow: isActive ? '0 4px 12px rgba(24, 144, 255, 0.3)' : 'none',
        },
        className: isActive ? 'active-node' : '',
      }
    })
  }, [currentState, events])

  // Создать edges (связи между состояниями)
  const edges: Edge[] = useMemo(() => {
    const baseEdges: Edge[] = [
      { id: 'e1', source: 'PENDING', target: 'QUEUED' },
      { id: 'e2', source: 'QUEUED', target: 'PROCESSING' },
      { id: 'e3', source: 'PROCESSING', target: 'UPLOADING' },
      { id: 'e4', source: 'PROCESSING', target: 'INSTALLING' },
      { id: 'e5', source: 'UPLOADING', target: 'INSTALLING' },
      { id: 'e6', source: 'INSTALLING', target: 'VERIFYING' },
      { id: 'e7', source: 'VERIFYING', target: 'SUCCESS' },
      { id: 'e8', source: 'PROCESSING', target: 'FAILED', style: { stroke: '#ff4d4f' } },
      { id: 'e9', source: 'INSTALLING', target: 'FAILED', style: { stroke: '#ff4d4f' } },
      { id: 'e10', source: 'PROCESSING', target: 'TIMEOUT', style: { stroke: '#fa8c16' } },
    ]

    return baseEdges.map((edge) => {
      const isActive =
        edge.source === currentState || edge.target === currentState
      return {
        ...edge,
        animated: isActive,
        style: {
          ...edge.style,
          strokeWidth: isActive ? 3 : 2,
        },
      }
    })
  }, [currentState])

  return (
    <div className="workflow-tracker">
      {/* Connection status */}
      {!isConnected && (
        <Alert
          message="Подключение к real-time обновлениям..."
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Error display */}
      {error && (
        <Alert
          message="Ошибка подключения"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* ReactFlow visualization */}
      <div style={{ height: '500px', border: '1px solid #d9d9d9', borderRadius: '8px' }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>

      {/* Timeline view */}
      <div className="timeline-container" style={{ marginTop: 24 }}>
        <h3>Хронология событий</h3>
        <div className="timeline">
          {events.length === 0 ? (
            <div style={{ color: '#999', fontStyle: 'italic' }}>
              События еще не поступили...
            </div>
          ) : (
            events.map((event, i) => (
              <div
                key={i}
                className="timeline-event"
                style={{
                  padding: '12px',
                  borderLeft: '3px solid #1890ff',
                  marginBottom: '8px',
                  backgroundColor: '#fafafa',
                  borderRadius: '4px',
                }}
              >
                <div style={{ display: 'flex', gap: '12px', fontSize: '12px' }}>
                  <span style={{ color: '#999' }}>
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  <span
                    style={{
                      background: '#e6f7ff',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontWeight: 'bold',
                    }}
                  >
                    [{event.microservice}]
                  </span>
                  <span style={{ fontWeight: 'bold', color: STATE_COLORS[event.state] }}>
                    {event.state}
                  </span>
                  <span>{event.message}</span>
                </div>
                {event.metadata && Object.keys(event.metadata).length > 0 && (
                  <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
                    {JSON.stringify(event.metadata)}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
