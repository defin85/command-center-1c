import { Checkbox, Input, Select, Space, Tag, Typography } from 'antd'

import type { CommandListItem } from '../commandSchemasUtils'

const { Text } = Typography

export function CommandSchemasCommandList(props: {
  search: string
  setSearch: (value: string) => void
  riskFilter: 'any' | 'safe' | 'dangerous'
  setRiskFilter: (value: 'any' | 'safe' | 'dangerous') => void
  scopeFilter: 'any' | 'per_database' | 'global'
  setScopeFilter: (value: 'any' | 'per_database' | 'global') => void
  onlyModified: boolean
  setOnlyModified: (value: boolean) => void
  hideDisabled: boolean
  setHideDisabled: (value: boolean) => void
  commandsCount: number
  groupedCommands: { keys: string[]; groups: Record<string, CommandListItem[]> }
  selectedCommandId: string
  onSelectCommand: (commandId: string) => void
}) {
  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Input.Search
        value={props.search}
        onChange={(e) => props.setSearch(e.target.value)}
        placeholder="Search id/label/description/flags"
        allowClear
      />
      <Space wrap>
        <Select
          value={props.riskFilter}
          onChange={(v) => props.setRiskFilter(v)}
          style={{ width: 140 }}
          options={[
            { value: 'any', label: 'Risk: any' },
            { value: 'safe', label: 'Risk: safe' },
            { value: 'dangerous', label: 'Risk: dangerous' },
          ]}
        />
        <Select
          value={props.scopeFilter}
          onChange={(v) => props.setScopeFilter(v)}
          style={{ width: 160 }}
          options={[
            { value: 'any', label: 'Scope: any' },
            { value: 'per_database', label: 'Scope: per_database' },
            { value: 'global', label: 'Scope: global' },
          ]}
        />
        <Checkbox checked={props.onlyModified} onChange={(e) => props.setOnlyModified(e.target.checked)}>
          Only modified
        </Checkbox>
        <Checkbox checked={props.hideDisabled} onChange={(e) => props.setHideDisabled(e.target.checked)}>
          Hide disabled
        </Checkbox>
      </Space>
      <Text type="secondary">Commands: {props.commandsCount}</Text>

      <div style={{ maxHeight: 720, overflow: 'auto', paddingRight: 6 }}>
        {props.groupedCommands.keys.map((groupKey) => (
          <div key={groupKey} style={{ marginBottom: 10 }}>
            <Text type="secondary">{groupKey} ({props.groupedCommands.groups[groupKey].length})</Text>
            <div style={{ marginTop: 6 }}>
              {props.groupedCommands.groups[groupKey].map((item) => {
                const selected = item.id === props.selectedCommandId

                return (
                  <button
                    type="button"
                    key={item.id}
                    data-testid={`command-schemas-command-${item.id}`}
                    onClick={() => props.onSelectCommand(item.id)}
                    aria-current={selected ? 'true' : undefined}
                    aria-label={`Select command ${item.display_id}`}
                    style={{
                      cursor: 'pointer',
                      border: '1px solid #f0f0f0',
                      borderRadius: 8,
                      padding: 10,
                      marginBottom: 8,
                      background: selected ? '#e6f4ff' : '#fff',
                      width: '100%',
                      textAlign: 'left',
                    }}
                  >
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Space wrap>
                        <Text strong>{item.display_id}</Text>
                        {item.has_overrides && <Tag color="blue">overrides</Tag>}
                        {item.disabled && <Tag>disabled</Tag>}
                        {item.risk_level === 'dangerous' && <Tag color="red">dangerous</Tag>}
                        {item.scope === 'global' && <Tag color="geekblue">global</Tag>}
                      </Space>
                      {item.description && (
                        <Text type="secondary" ellipsis={{ tooltip: item.description }}>{item.description}</Text>
                      )}
                    </Space>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </Space>
  )
}

