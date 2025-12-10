/**
 * SelectTypeStep - Step 1 of NewOperationWizard
 * Displays operation types as cards grouped by category.
 * Supports both built-in operations and custom workflow templates.
 */

import { useMemo, useCallback } from 'react'
import { Card, Row, Col, Typography, Badge, Spin, Alert, Empty } from 'antd'
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
  UserSwitchOutlined,
  ToolOutlined,
  CodeOutlined,
  DatabaseOutlined,
  FileOutlined,
  SettingOutlined,
  AppstoreOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { SelectTypeStepProps, OperationCategory, OperationTypeConfig } from './types'
import { OPERATION_TYPES, OPERATION_CATEGORIES } from './types'
import { useWorkflowTemplates } from '../../../../hooks/useWorkflowTemplates'

const { Title, Text } = Typography

/**
 * Map icon names to actual Ant Design icon components
 */
const iconMap: Record<string, React.ReactNode> = {
  // Built-in operation icons
  LockOutlined: <LockOutlined style={{ fontSize: 24 }} />,
  UnlockOutlined: <UnlockOutlined style={{ fontSize: 24 }} />,
  StopOutlined: <StopOutlined style={{ fontSize: 24 }} />,
  CheckCircleOutlined: <CheckCircleOutlined style={{ fontSize: 24 }} />,
  CloseCircleOutlined: <CloseCircleOutlined style={{ fontSize: 24 }} />,
  RocketOutlined: <RocketOutlined style={{ fontSize: 24 }} />,
  SearchOutlined: <SearchOutlined style={{ fontSize: 24 }} />,
  SyncOutlined: <SyncOutlined style={{ fontSize: 24 }} />,
  HeartOutlined: <HeartOutlined style={{ fontSize: 24 }} />,
  // Custom template icons
  UserSwitchOutlined: <UserSwitchOutlined style={{ fontSize: 24 }} />,
  ToolOutlined: <ToolOutlined style={{ fontSize: 24 }} />,
  CodeOutlined: <CodeOutlined style={{ fontSize: 24 }} />,
  DatabaseOutlined: <DatabaseOutlined style={{ fontSize: 24 }} />,
  FileOutlined: <FileOutlined style={{ fontSize: 24 }} />,
  SettingOutlined: <SettingOutlined style={{ fontSize: 24 }} />,
  AppstoreOutlined: <AppstoreOutlined style={{ fontSize: 24 }} />,
  ThunderboltOutlined: <ThunderboltOutlined style={{ fontSize: 24 }} />,
}

/**
 * Default icon for custom templates without a specified icon
 */
const defaultIcon = <AppstoreOutlined style={{ fontSize: 24 }} />

/**
 * Get icon component by name, with fallback to default
 */
function getIcon(iconName: string): React.ReactNode {
  return iconMap[iconName] || defaultIcon
}

/**
 * Unified item type for both built-in operations and custom templates
 */
interface OperationItem {
  id: string
  label: string
  description: string
  icon: string
  category: OperationCategory
  isCustomTemplate: boolean
  /** Original type for built-in operations */
  operationType?: OperationTypeConfig['type']
  /** Template ID for custom templates */
  templateId?: string
  /** Whether the template requires configuration */
  requiresConfig: boolean
}

/**
 * SelectTypeStep component
 * Renders operation types grouped by category as selectable cards.
 * Combines built-in operations with custom workflow templates.
 */
export const SelectTypeStep = ({
  selectedType,
  selectedTemplateId,
  onSelect,
  onSelectTemplate,
}: SelectTypeStepProps) => {
  // Fetch custom templates
  const { templates, loading, error } = useWorkflowTemplates({
    is_template: true,
    is_active: true,
  })

  // Combine built-in operations with custom templates
  const allOperations: OperationItem[] = useMemo(() => {
    // Convert built-in operations to unified format
    const builtInOperations: OperationItem[] = OPERATION_TYPES.map((op) => ({
      id: op.type,
      label: op.label,
      description: op.description,
      icon: op.icon,
      category: op.category,
      isCustomTemplate: false,
      operationType: op.type,
      requiresConfig: op.requiresConfig,
    }))

    // Convert custom templates to unified format
    const customOperations: OperationItem[] = templates.map((template) => ({
      id: `template:${template.id}`,
      label: template.name,
      description: template.description || 'Custom workflow template',
      icon: template.icon || 'AppstoreOutlined',
      category: 'custom' as OperationCategory,
      isCustomTemplate: true,
      templateId: template.id,
      // Custom templates always require configuration (via DynamicForm)
      requiresConfig: template.input_schema !== null,
    }))

    return [...builtInOperations, ...customOperations]
  }, [templates])

  // Group operations by category
  const operationsByCategory = useMemo(() => {
    return allOperations.reduce(
      (acc, op) => {
        if (!acc[op.category]) {
          acc[op.category] = []
        }
        acc[op.category].push(op)
        return acc
      },
      {} as Record<OperationCategory, OperationItem[]>
    )
  }, [allOperations])

  // Sort categories by order (only include categories that have items)
  const sortedCategories = useMemo(() => {
    return (Object.keys(operationsByCategory) as OperationCategory[]).sort(
      (a, b) => OPERATION_CATEGORIES[a].order - OPERATION_CATEGORIES[b].order
    )
  }, [operationsByCategory])

  // Handle card click
  const handleClick = useCallback((item: OperationItem) => {
    if (item.isCustomTemplate && item.templateId) {
      // Custom template selected - clear operation type and set template
      onSelectTemplate(item.templateId)
    } else if (item.operationType) {
      // Built-in operation selected - set operation type and clear template
      onSelect(item.operationType)
      onSelectTemplate(null)
    }
  }, [onSelect, onSelectTemplate])

  // Check if an item is selected
  const isSelected = (item: OperationItem): boolean => {
    if (item.isCustomTemplate && item.templateId) {
      return selectedTemplateId === item.templateId
    }
    return selectedType === item.operationType && selectedTemplateId === null
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        Select Operation Type
      </Title>

      {/* Loading state for custom templates */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Spin tip="Loading custom templates..." />
        </div>
      )}

      {/* Error state for custom templates (non-blocking) */}
      {error && (
        <Alert
          message="Could not load custom templates"
          description="Built-in operations are still available. Custom templates may appear after refresh."
          type="warning"
          showIcon
          style={{ marginBottom: 24 }}
          closable
        />
      )}

      {/* Render categories */}
      {sortedCategories.map((category) => {
        const items = operationsByCategory[category]
        if (!items || items.length === 0) return null

        return (
          <div key={category} style={{ marginBottom: 32 }}>
            <Text strong style={{ fontSize: 16, display: 'block', marginBottom: 16 }}>
              {OPERATION_CATEGORIES[category].label}
            </Text>

            <Row gutter={[16, 16]}>
              {items.map((item) => {
                const selected = isSelected(item)
                return (
                  <Col key={item.id} xs={24} sm={12} md={8} lg={6}>
                    <Badge.Ribbon
                      text="Custom"
                      color="purple"
                      style={{ display: item.isCustomTemplate ? 'block' : 'none' }}
                    >
                      <Card
                        hoverable
                        onClick={() => handleClick(item)}
                        style={{
                          cursor: 'pointer',
                          border: selected ? '2px solid #1890ff' : '1px solid #d9d9d9',
                          backgroundColor: selected ? '#e6f7ff' : undefined,
                          transition: 'all 0.2s ease',
                          height: '100%',
                        }}
                        styles={{
                          body: {
                            padding: '16px',
                            textAlign: 'center',
                          },
                        }}
                      >
                        <div
                          style={{
                            color: selected ? '#1890ff' : '#595959',
                            marginBottom: 8,
                          }}
                        >
                          {getIcon(item.icon)}
                        </div>
                        <Text
                          strong
                          style={{
                            display: 'block',
                            marginBottom: 4,
                            color: selected ? '#1890ff' : undefined,
                          }}
                        >
                          {item.label}
                        </Text>
                        <Text
                          type="secondary"
                          style={{
                            fontSize: 12,
                            display: 'block',
                          }}
                        >
                          {item.description}
                        </Text>
                      </Card>
                    </Badge.Ribbon>
                  </Col>
                )
              })}
            </Row>
          </div>
        )
      })}

      {/* Empty state when no operations available */}
      {sortedCategories.length === 0 && !loading && (
        <Empty
          description="No operations available"
          style={{ marginTop: 48 }}
        />
      )}
    </div>
  )
}
