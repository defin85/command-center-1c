import type { UIEventHandler } from 'react'
import { Button, Card, Input, Menu, Space, Typography } from 'antd'
import type { MenuProps } from 'antd'

const { Text } = Typography

type SelectOption = { label: string; value: string }

export function RbacResourceBrowser(props: {
  title: string
  searchPlaceholder?: string
  searchValue: string
  onSearchChange: (value: string) => void
  options: SelectOption[]
  selectedValue?: string
  onSelect: (value: string) => void
  loading?: boolean
  loadingText?: string
  onScroll?: UIEventHandler<HTMLDivElement>
  clearLabel?: string
  clearDisabled?: boolean
  onClear?: () => void
}) {
  const items: MenuProps['items'] = props.options.map((opt) => ({ key: opt.value, label: opt.label }))

  return (
    <Card title={props.title} size="small" style={{ width: 420 }}>
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Input
          placeholder={props.searchPlaceholder}
          allowClear
          value={props.searchValue}
          onChange={(e) => props.onSearchChange(e.target.value)}
        />
        <div
          style={{ maxHeight: 520, overflow: 'auto', border: '1px solid #f0f0f0', borderRadius: 6 }}
          onScroll={props.onScroll}
        >
          <Menu
            selectable
            selectedKeys={props.selectedValue ? [props.selectedValue] : []}
            items={items}
            onClick={({ key }) => props.onSelect(String(key))}
          />
          {props.loading && (
            <div style={{ padding: 8, textAlign: 'center' }}>
              <Text type="secondary">{props.loadingText ?? 'Loading\u2026'}</Text>
            </div>
          )}
        </div>
        {props.onClear && props.clearLabel ? (
          <Button size="small" disabled={props.clearDisabled} onClick={props.onClear}>
            {props.clearLabel}
          </Button>
        ) : null}
      </Space>
    </Card>
  )
}
