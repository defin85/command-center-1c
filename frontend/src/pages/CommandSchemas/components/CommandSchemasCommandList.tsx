import { Checkbox, Input, Select, Space, Tag, Typography } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

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
  const { t } = useAdminSupportTranslation()

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Input.Search
        value={props.search}
        onChange={(e) => props.setSearch(e.target.value)}
        placeholder={t(($) => $.commandSchemas.list.searchPlaceholder)}
        allowClear
      />
      <Space wrap>
        <Select
          value={props.riskFilter}
          onChange={(v) => props.setRiskFilter(v)}
          style={{ width: 140 }}
          options={[
            { value: 'any', label: t(($) => $.commandSchemas.list.riskAny) },
            { value: 'safe', label: t(($) => $.commandSchemas.list.riskSafe) },
            { value: 'dangerous', label: t(($) => $.commandSchemas.list.riskDangerous) },
          ]}
        />
        <Select
          value={props.scopeFilter}
          onChange={(v) => props.setScopeFilter(v)}
          style={{ width: 160 }}
          options={[
            { value: 'any', label: t(($) => $.commandSchemas.list.scopeAny) },
            { value: 'per_database', label: t(($) => $.commandSchemas.list.scopePerDatabase) },
            { value: 'global', label: t(($) => $.commandSchemas.list.scopeGlobal) },
          ]}
        />
        <Checkbox checked={props.onlyModified} onChange={(e) => props.setOnlyModified(e.target.checked)}>
          {t(($) => $.commandSchemas.list.onlyModified)}
        </Checkbox>
        <Checkbox checked={props.hideDisabled} onChange={(e) => props.setHideDisabled(e.target.checked)}>
          {t(($) => $.commandSchemas.list.hideDisabled)}
        </Checkbox>
      </Space>
      <Text type="secondary">{t(($) => $.commandSchemas.list.commandsCount, { count: props.commandsCount })}</Text>

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
                    aria-label={t(($) => $.commandSchemas.list.selectCommandAria, { commandId: item.display_id })}
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
                        {item.has_overrides && <Tag color="blue">{t(($) => $.commandSchemas.list.overrides)}</Tag>}
                        {item.disabled && <Tag>{t(($) => $.commandSchemas.list.disabled)}</Tag>}
                        {item.risk_level === 'dangerous' && <Tag color="red">{t(($) => $.commandSchemas.list.dangerous)}</Tag>}
                        {item.scope === 'global' && <Tag color="geekblue">{t(($) => $.commandSchemas.list.global)}</Tag>}
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
