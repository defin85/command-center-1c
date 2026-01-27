import { Alert, Card, Input, Select, Space, Switch, Tag, Typography } from 'antd'

import type { DriverCommandParamV2 } from '../../../../api/driverCommands'
import { deepCopy, normalizeStringList, safeText } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasParamsEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  if (!model.selectedCommandId || !model.selectedEffective) {
    return null
  }

  const effectiveParams = (model.selectedEffective.params_by_name && typeof model.selectedEffective.params_by_name === 'object')
    ? (model.selectedEffective.params_by_name as Record<string, DriverCommandParamV2>)
    : {}
  const patchParamsByName = (model.selectedPatch?.params_by_name && typeof model.selectedPatch.params_by_name === 'object')
    ? (model.selectedPatch.params_by_name as Record<string, Partial<DriverCommandParamV2>>)
    : {}

  const names = Object.keys(effectiveParams).sort()
  if (names.length === 0) {
    return <Alert type="info" showIcon message="No params for this command" />
  }

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      {names.map((name) => {
        const effectiveParam = effectiveParams[name]
        const baseParam = model.selectedBase?.params_by_name && typeof model.selectedBase.params_by_name === 'object'
          ? (model.selectedBase.params_by_name as Record<string, DriverCommandParamV2>)[name]
          : undefined
        const paramOver = Object.prototype.hasOwnProperty.call(patchParamsByName, name)
        const patchParam = paramOver ? patchParamsByName[name] : {}

        const currentKind = paramOver ? safeText(patchParam.kind) : safeText(effectiveParam.kind)
        const currentRequired = paramOver ? Boolean(patchParam.required) : Boolean(effectiveParam.required)
        const currentExpects = paramOver ? Boolean(patchParam.expects_value) : Boolean(effectiveParam.expects_value)
        const currentFlag = paramOver ? safeText(patchParam.flag) : safeText(effectiveParam.flag)
        const currentPosition = paramOver ? Number(patchParam.position) : Number(effectiveParam.position)
        const currentEnum = paramOver ? normalizeStringList(patchParam.enum) : normalizeStringList(effectiveParam.enum)

        return (
          <Card
            key={name}
            size="small"
            title={<Space wrap><Text code>{name}</Text>{effectiveParam.required && <Tag color="red">required</Tag>}</Space>}
            extra={(
              <Space size="small">
                <Text type="secondary">Override</Text>
                <Switch
                  size="small"
                  checked={paramOver}
                  onChange={(checked) => {
                    model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (!p.params_by_name) p.params_by_name = {}
                      if (checked) {
                        p.params_by_name[name] = deepCopy(baseParam ?? effectiveParam)
                      } else {
                        delete p.params_by_name[name]
                        if (Object.keys(p.params_by_name).length === 0) {
                          delete p.params_by_name
                        }
                      }
                    })
                  }}
                />
              </Space>
            )}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space wrap>
                <div style={{ width: 220 }}>
                  <Text type="secondary">Kind</Text>
                  <Select
                    value={currentKind || undefined}
                    disabled={!paramOver}
                    onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (!p.params_by_name) p.params_by_name = {}
                      if (!p.params_by_name[name]) p.params_by_name[name] = {}
                      p.params_by_name[name].kind = value as 'flag' | 'positional'
                    })}
                    options={[
                      { value: 'flag', label: 'flag' },
                      { value: 'positional', label: 'positional' },
                    ]}
                  />
                </div>
                <div style={{ width: 220 }}>
                  <Text type="secondary">Required</Text>
                  <Switch
                    checked={currentRequired}
                    disabled={!paramOver}
                    onChange={(checked) => model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (!p.params_by_name) p.params_by_name = {}
                      if (!p.params_by_name[name]) p.params_by_name[name] = {}
                      p.params_by_name[name].required = checked
                    })}
                  />
                </div>
                <div style={{ width: 220 }}>
                  <Text type="secondary">Expects value</Text>
                  <Switch
                    checked={currentExpects}
                    disabled={!paramOver}
                    onChange={(checked) => model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (!p.params_by_name) p.params_by_name = {}
                      if (!p.params_by_name[name]) p.params_by_name[name] = {}
                      p.params_by_name[name].expects_value = checked
                    })}
                  />
                </div>
              </Space>

              {currentKind === 'flag' && (
                <div style={{ width: 340 }}>
                  <Text type="secondary">Flag</Text>
                  <Input
                    value={currentFlag}
                    disabled={!paramOver}
                    onChange={(e) => model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (!p.params_by_name) p.params_by_name = {}
                      if (!p.params_by_name[name]) p.params_by_name[name] = {}
                      p.params_by_name[name].flag = e.target.value
                    })}
                    placeholder="--flag"
                  />
                </div>
              )}

              {currentKind === 'positional' && (
                <div style={{ width: 220 }}>
                  <Text type="secondary">Position</Text>
                  <Input
                    value={Number.isFinite(currentPosition) ? String(currentPosition) : ''}
                    disabled={!paramOver}
                    onChange={(e) => {
                      const raw = e.target.value.trim()
                      const num = raw ? Number(raw) : NaN
                      model.setCommandPatch(model.selectedCommandId, (p) => {
                        if (!p.params_by_name) p.params_by_name = {}
                        if (!p.params_by_name[name]) p.params_by_name[name] = {}
                        p.params_by_name[name].position = Number.isFinite(num) ? num : undefined
                      })
                    }}
                    placeholder="1"
                  />
                </div>
              )}

              <div style={{ width: '100%' }}>
                <Text type="secondary">Enum</Text>
                <Select
                  mode="tags"
                  value={currentEnum}
                  disabled={!paramOver}
                  onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
                    if (!p.params_by_name) p.params_by_name = {}
                    if (!p.params_by_name[name]) p.params_by_name[name] = {}
                    p.params_by_name[name].enum = value
                  })}
                  tokenSeparators={[',']}
                  placeholder="Allowed values (optional)"
                />
              </div>
            </Space>
          </Card>
        )
      })}
    </Space>
  )
}
