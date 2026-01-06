/**
 * SelectTypeStep - Step 1 of NewOperationWizard
 * Displays operation types as cards grouped by category.
 * Supports both built-in operations and custom workflow templates.
 */

import { useMemo, useCallback, useEffect, useState } from 'react'
import { Card, Row, Col, Typography, Badge, Spin, Alert, Empty, Input, Select, Space, Collapse, Tooltip, Tag } from 'antd'
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
  PlayCircleOutlined,
} from '@ant-design/icons'
import type { SelectTypeStepProps, OperationType } from './types'
import { useOperationCatalog } from '../../../../hooks/useOperationCatalog'
import type { OperationCatalogItem } from '../../../../api/operations'

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
  PlayCircleOutlined: <PlayCircleOutlined style={{ fontSize: 24 }} />,
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

const DRIVER_LABELS: Record<string, string> = {
  ras: 'RAS',
  odata: 'OData',
  cli: 'CLI',
  ibcmd: 'IBCMD',
  workflow: 'Workflow',
}

const DRIVER_ORDER: Record<string, number> = {
  ras: 1,
  odata: 2,
  cli: 3,
  ibcmd: 4,
  workflow: 5,
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
  const { items, loading, error } = useOperationCatalog()
  const [searchValue, setSearchValue] = useState('')
  const [selectedDrivers, setSelectedDrivers] = useState<string[]>([])
  const [driversInitialized, setDriversInitialized] = useState(false)

  const availableDrivers = useMemo(() => {
    const unique = new Set(items.map((item) => item.driver))
    return Array.from(unique).sort((a, b) => (DRIVER_ORDER[a] ?? 99) - (DRIVER_ORDER[b] ?? 99))
  }, [items])

  useEffect(() => {
    if (!driversInitialized && availableDrivers.length > 0) {
      setSelectedDrivers(availableDrivers)
      setDriversInitialized(true)
    }
  }, [availableDrivers, driversInitialized])

  const filteredItems = useMemo(() => {
    const query = searchValue.trim().toLowerCase()
    return items.filter((item) => {
      if (item.kind === 'operation' && typeof item.operation_type === 'string') {
        const op = item.operation_type
        if (op.startsWith('ibcmd_') && op !== 'ibcmd_cli') {
          return false
        }
      }
      if (selectedDrivers.length > 0 && !selectedDrivers.includes(item.driver)) {
        return false
      }
      if (!query) return true
      const tags = item.tags?.join(' ') ?? ''
      const haystack = `${item.label} ${item.description} ${tags} ${item.driver}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [items, searchValue, selectedDrivers])

  const itemsByDriver = useMemo(() => {
    return filteredItems.reduce((acc, item) => {
      const driver = item.driver
      if (!acc[driver]) {
        acc[driver] = []
      }
      acc[driver].push(item)
      return acc
    }, {} as Record<string, OperationCatalogItem[]>)
  }, [filteredItems])

  const sortedDrivers = useMemo(
    () => Object.keys(itemsByDriver).sort((a, b) => (DRIVER_ORDER[a] ?? 99) - (DRIVER_ORDER[b] ?? 99)),
    [itemsByDriver]
  )

  // Handle card click
  const handleClick = useCallback((item: OperationCatalogItem) => {
    if (!item.has_ui_form || item.deprecated) {
      return
    }
    if (item.kind === 'template' && item.template_id) {
      onSelectTemplate(item.template_id)
      return
    }
    if (item.kind === 'operation' && item.operation_type) {
      onSelect(item.operation_type as OperationType)
    }
  }, [onSelect, onSelectTemplate])

  // Check if an item is selected
  const isSelected = (item: OperationCatalogItem): boolean => {
    if (item.kind === 'template' && item.template_id) {
      return selectedTemplateId === item.template_id
    }
    return selectedType === item.operation_type && selectedTemplateId === null
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <Title level={4} style={{ marginBottom: 24 }}>
        Select Operation Type
      </Title>

      <Space wrap style={{ marginBottom: 16 }}>
        <Input
          allowClear
          placeholder="Search operations"
          prefix={<SearchOutlined />}
          value={searchValue}
          onChange={(event) => setSearchValue(event.target.value)}
          style={{ width: 280 }}
        />
        <Select
          mode="multiple"
          placeholder="Filter by driver"
          value={selectedDrivers}
          onChange={(value) => setSelectedDrivers(value)}
          options={availableDrivers.map((driver) => ({
            value: driver,
            label: DRIVER_LABELS[driver] ?? driver,
          }))}
          style={{ minWidth: 260 }}
        />
      </Space>

      {/* Loading state for catalog */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Spin />
          <div style={{ marginTop: 8, color: '#595959' }}>Loading operation catalog...</div>
        </div>
      )}

      {/* Error state for catalog */}
      {error && (
        <Alert
          message="Could not load operation catalog"
          description="Try again later or check API status."
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
          closable
        />
      )}

      {/* Render categories */}
      {!loading && sortedDrivers.length > 0 && (
        <Collapse
          defaultActiveKey={sortedDrivers}
          style={{ background: 'transparent' }}
          items={sortedDrivers.map((driver) => {
            const driverItems = itemsByDriver[driver] || []
            return {
              key: driver,
              label: (
                <Space>
                  <Text strong style={{ fontSize: 16 }}>
                    {DRIVER_LABELS[driver] ?? driver}
                  </Text>
                  <Tag>{driverItems.length}</Tag>
                </Space>
              ),
              children: (
                <Row gutter={[16, 16]}>
                  {driverItems.map((item) => {
                    const selected = isSelected(item)
                    const hasUiForm = item.has_ui_form ?? true
                    const disabled = !hasUiForm || item.deprecated
                    const disabledReason = item.deprecated
                      ? (item.deprecated_message || 'Deprecated')
                      : item.has_ui_form === false
                        ? 'Not available in UI yet'
                        : null
                    const iconName = item.icon || 'AppstoreOutlined'
                    const card = (
                      <Card
                        hoverable={!disabled}
                        onClick={() => handleClick(item)}
                        style={{
                          cursor: disabled ? 'not-allowed' : 'pointer',
                          border: selected ? '2px solid #1890ff' : '1px solid #d9d9d9',
                          backgroundColor: selected ? '#e6f7ff' : undefined,
                          transition: 'all 0.2s ease',
                          height: '100%',
                          opacity: disabled ? 0.6 : 1,
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
                          {getIcon(iconName)}
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
                        <Space size={4} style={{ marginTop: 8 }} wrap>
                          {item.deprecated && <Tag color="red">Deprecated</Tag>}
                          {item.has_ui_form === false && <Tag>UI form not available</Tag>}
                        </Space>
                      </Card>
                    )
                    const wrappedCard = item.kind === 'template' ? (
                      <Badge.Ribbon text="Template" color="blue">
                        {card}
                      </Badge.Ribbon>
                    ) : card

                    return (
                      <Col key={item.id} xs={24} sm={12} md={8} lg={6}>
                        {disabledReason ? (
                          <Tooltip title={disabledReason}>
                            <div>{wrappedCard}</div>
                          </Tooltip>
                        ) : (
                          wrappedCard
                        )}
                      </Col>
                    )
                  })}
                </Row>
              ),
            }
          })}
        />
      )}

      {/* Empty state when no operations available */}
      {sortedDrivers.length === 0 && !loading && (
        <Empty
          description="No operations available"
          style={{ marginTop: 48 }}
        />
      )}
    </div>
  )
}
