/**
 * SelectTypeStep - Step 1 of NewOperationWizard
 * Displays operation types as cards grouped by category.
 */

import { Card, Row, Col, Typography } from 'antd'
import {
  LockOutlined,
  UnlockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  RocketOutlined,
  SearchOutlined,
  SyncOutlined,
  HeartOutlined,
} from '@ant-design/icons'
import type { SelectTypeStepProps, OperationCategory } from './types'
import { OPERATION_TYPES, OPERATION_CATEGORIES } from './types'

const { Title, Text } = Typography

/**
 * Map icon names to actual Ant Design icon components
 */
const iconMap: Record<string, React.ReactNode> = {
  LockOutlined: <LockOutlined style={{ fontSize: 24 }} />,
  UnlockOutlined: <UnlockOutlined style={{ fontSize: 24 }} />,
  StopOutlined: <StopOutlined style={{ fontSize: 24 }} />,
  CheckCircleOutlined: <CheckCircleOutlined style={{ fontSize: 24 }} />,
  CloseCircleOutlined: <CloseCircleOutlined style={{ fontSize: 24 }} />,
  RocketOutlined: <RocketOutlined style={{ fontSize: 24 }} />,
  SearchOutlined: <SearchOutlined style={{ fontSize: 24 }} />,
  SyncOutlined: <SyncOutlined style={{ fontSize: 24 }} />,
  HeartOutlined: <HeartOutlined style={{ fontSize: 24 }} />,
}

/**
 * SelectTypeStep component
 * Renders operation types grouped by category as selectable cards
 */
export const SelectTypeStep = ({ selectedType, onSelect }: SelectTypeStepProps) => {
  // Group operations by category
  const operationsByCategory = OPERATION_TYPES.reduce(
    (acc, op) => {
      if (!acc[op.category]) {
        acc[op.category] = []
      }
      acc[op.category].push(op)
      return acc
    },
    {} as Record<OperationCategory, typeof OPERATION_TYPES>
  )

  // Sort categories by order
  const sortedCategories = (Object.keys(operationsByCategory) as OperationCategory[]).sort(
    (a, b) => OPERATION_CATEGORIES[a].order - OPERATION_CATEGORIES[b].order
  )

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        Select Operation Type
      </Title>

      {sortedCategories.map((category) => (
        <div key={category} style={{ marginBottom: 32 }}>
          <Text strong style={{ fontSize: 16, display: 'block', marginBottom: 16 }}>
            {OPERATION_CATEGORIES[category].label}
          </Text>

          <Row gutter={[16, 16]}>
            {operationsByCategory[category].map((operation) => {
              const isSelected = selectedType === operation.type
              return (
                <Col key={operation.type} xs={24} sm={12} md={8} lg={6}>
                  <Card
                    hoverable
                    onClick={() => onSelect(operation.type)}
                    style={{
                      cursor: 'pointer',
                      border: isSelected ? '2px solid #1890ff' : '1px solid #d9d9d9',
                      backgroundColor: isSelected ? '#e6f7ff' : undefined,
                      transition: 'all 0.2s ease',
                    }}
                    bodyStyle={{
                      padding: '16px',
                      textAlign: 'center',
                    }}
                  >
                    <div
                      style={{
                        color: isSelected ? '#1890ff' : '#595959',
                        marginBottom: 8,
                      }}
                    >
                      {iconMap[operation.icon]}
                    </div>
                    <Text
                      strong
                      style={{
                        display: 'block',
                        marginBottom: 4,
                        color: isSelected ? '#1890ff' : undefined,
                      }}
                    >
                      {operation.label}
                    </Text>
                    <Text
                      type="secondary"
                      style={{
                        fontSize: 12,
                        display: 'block',
                      }}
                    >
                      {operation.description}
                    </Text>
                  </Card>
                </Col>
              )
            })}
          </Row>
        </div>
      ))}
    </div>
  )
}
