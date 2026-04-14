import { Button, Divider, Form, Input, Select, Space, Switch, Typography } from 'antd'
import type { ModalFuncProps } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import type { DriverCommandV2 } from '../../../../api/driverCommands'
import type { CommandSchemaCommandPatch } from '../../../../api/commandSchemas'
import { displayCommandId, safeText } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasBasicsEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  if (!model.selectedCommandId || !model.selectedEffective) {
    return null
  }

  const displayId = displayCommandId(model.activeDriver, model.selectedCommandId)
  const patch: CommandSchemaCommandPatch = model.selectedPatch ?? {}
  const labelOver = Object.prototype.hasOwnProperty.call(patch, 'label')
  const descOver = Object.prototype.hasOwnProperty.call(patch, 'description')
  const scopeOver = Object.prototype.hasOwnProperty.call(patch, 'scope')
  const riskOver = Object.prototype.hasOwnProperty.call(patch, 'risk_level')
  const disabledOver = Object.prototype.hasOwnProperty.call(patch, 'disabled')

  const currentLabel = labelOver ? safeText(patch.label) : safeText(model.selectedEffective.label)
  const currentDesc = descOver ? safeText(patch.description) : safeText(model.selectedEffective.description)
  const currentScope = scopeOver ? safeText(patch.scope).toLowerCase() : safeText(model.selectedEffective.scope).toLowerCase()
  const currentRisk = riskOver ? safeText(patch.risk_level).toLowerCase() : safeText(model.selectedEffective.risk_level).toLowerCase()
  const currentDisabled = disabledOver ? Boolean(patch.disabled) : Boolean(model.selectedEffective.disabled)

  const baseRisk = safeText(model.selectedBase?.risk_level).toLowerCase()
  const baseDisabled = Boolean(model.selectedBase?.disabled)

  const confirm = (config: ModalFuncProps) => model.confirm(config)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Space align="baseline" wrap style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space direction="vertical" size={0}>
          <Text type="secondary">{t(($) => $.commandSchemas.basics.commandId)}</Text>
          <Text code>{displayId}</Text>
        </Space>
        <Button onClick={() => model.resetCommandPatch(model.selectedCommandId)} disabled={!model.selectedPatch}>
          {t(($) => $.commandSchemas.basics.resetCommand)}
        </Button>
      </Space>

      <Divider style={{ margin: '8px 0' }} />

      <Form layout="vertical">
        <Space wrap style={{ width: '100%' }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Text>{t(($) => $.commandSchemas.basics.label)}</Text>
              <Space size="small">
                <Text type="secondary">{t(($) => $.commandSchemas.basics.override)}</Text>
                <Switch
                  data-testid="command-schemas-basics-label-override"
                  size="small"
                  checked={labelOver}
                  onChange={(checked) => {
                    model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (checked) {
                        p.label = safeText(model.selectedEffective?.label).trim() || model.selectedCommandId
                      } else {
                        delete p.label
                      }
                    })
                  }}
                />
              </Space>
            </Space>
            <Input
              data-testid="command-schemas-basics-label-input"
              value={currentLabel}
              disabled={!labelOver}
              onChange={(e) => model.setCommandPatch(model.selectedCommandId, (p) => { p.label = e.target.value })}
            />
          </div>

          <div style={{ width: 220 }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Text>{t(($) => $.commandSchemas.basics.scope)}</Text>
              <Space size="small">
                <Text type="secondary">{t(($) => $.commandSchemas.basics.override)}</Text>
                <Switch
                  size="small"
                  checked={scopeOver}
                  onChange={(checked) => {
                    model.setCommandPatch(model.selectedCommandId, (p) => {
                      if (checked) {
                        p.scope = model.selectedEffective?.scope
                      } else {
                        delete p.scope
                      }
                    })
                  }}
                />
              </Space>
            </Space>
            <Select
              value={currentScope || undefined}
              disabled={!scopeOver}
              onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => { p.scope = value as DriverCommandV2['scope'] })}
              options={[
                { value: 'per_database', label: 'per_database' },
                { value: 'global', label: 'global' },
              ]}
            />
          </div>

          <div style={{ width: 220 }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Text>{t(($) => $.commandSchemas.basics.risk)}</Text>
              <Space size="small">
                <Text type="secondary">{t(($) => $.commandSchemas.basics.override)}</Text>
                <Switch
                  size="small"
                  checked={riskOver}
                  onChange={(checked) => {
                    if (checked) {
                      model.setCommandPatch(model.selectedCommandId, (p) => {
                        p.risk_level = model.selectedEffective?.risk_level
                      })
                      return
                    }

                    const beforeRisk = currentRisk
                    const afterRisk = baseRisk
                    const beforeKnown = beforeRisk === 'safe' || beforeRisk === 'dangerous'
                    const afterKnown = afterRisk === 'safe' || afterRisk === 'dangerous'

                    if (beforeKnown && afterKnown && beforeRisk !== afterRisk) {
                      const nextRisk = afterRisk as DriverCommandV2['risk_level']
                      const title = nextRisk === 'dangerous'
                        ? t(($) => $.commandSchemas.basics.confirmRiskDangerousTitle)
                        : t(($) => $.commandSchemas.basics.confirmRiskSafeTitle)
                      const content = nextRisk === 'dangerous'
                        ? t(($) => $.commandSchemas.basics.confirmRiskDangerousDescription, { commandId: displayId })
                        : t(($) => $.commandSchemas.basics.confirmRiskSafeDescription, { commandId: displayId })
                      confirm({
                        title,
                        content,
                        okText: t(($) => $.commandSchemas.basics.apply),
                        cancelText: t(($) => $.commandSchemas.basics.cancel),
                        onOk: () => {
                          model.setCommandPatch(model.selectedCommandId, (p) => {
                            delete p.risk_level
                          })
                        },
                      })
                      return
                    }

                    model.setCommandPatch(model.selectedCommandId, (p) => {
                      delete p.risk_level
                    })
                  }}
                />
              </Space>
            </Space>
            <Select
              value={currentRisk || undefined}
              disabled={!riskOver}
              onChange={(value) => {
                const nextRisk = value as DriverCommandV2['risk_level']
                const prevRisk = currentRisk
                if (nextRisk && (prevRisk === 'safe' || prevRisk === 'dangerous') && prevRisk !== nextRisk) {
                  const title = nextRisk === 'dangerous'
                    ? t(($) => $.commandSchemas.basics.confirmRiskDangerousTitle)
                    : t(($) => $.commandSchemas.basics.confirmRiskSafeTitle)
                  const content = nextRisk === 'dangerous'
                    ? t(($) => $.commandSchemas.basics.confirmRiskDangerousDescription, { commandId: displayId })
                    : t(($) => $.commandSchemas.basics.confirmRiskSafeDescription, { commandId: displayId })
                  confirm({
                    title,
                    content,
                    okText: t(($) => $.commandSchemas.basics.apply),
                    cancelText: t(($) => $.commandSchemas.basics.cancel),
                    onOk: () => {
                      model.setCommandPatch(model.selectedCommandId, (p) => { p.risk_level = nextRisk })
                    },
                  })
                  return
                }
                model.setCommandPatch(model.selectedCommandId, (p) => { p.risk_level = nextRisk })
              }}
              options={[
                { value: 'safe', label: 'safe' },
                { value: 'dangerous', label: 'dangerous' },
              ]}
            />
          </div>

          <div style={{ width: 220 }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Text>{t(($) => $.commandSchemas.basics.disabled)}</Text>
              <Space size="small">
                <Text type="secondary">{t(($) => $.commandSchemas.basics.override)}</Text>
                <Switch
                  size="small"
                  checked={disabledOver}
                  onChange={(checked) => {
                    if (checked) {
                      model.setCommandPatch(model.selectedCommandId, (p) => {
                        p.disabled = Boolean(model.selectedEffective?.disabled)
                      })
                      return
                    }

                    const beforeDisabled = currentDisabled
                    const afterDisabled = baseDisabled
                    if (beforeDisabled && !afterDisabled) {
                      confirm({
                        title: t(($) => $.commandSchemas.basics.enableDisabledTitle),
                        content: t(($) => $.commandSchemas.basics.enableDisabledDescription, { commandId: displayId }),
                        okText: t(($) => $.commandSchemas.basics.enable),
                        cancelText: t(($) => $.commandSchemas.basics.cancel),
                        onOk: () => {
                          model.setCommandPatch(model.selectedCommandId, (p) => {
                            delete p.disabled
                          })
                        },
                      })
                      return
                    }

                    model.setCommandPatch(model.selectedCommandId, (p) => {
                      delete p.disabled
                    })
                  }}
                />
              </Space>
            </Space>
            <Switch
              checked={currentDisabled}
              disabled={!disabledOver}
              onChange={(checked) => {
                if (currentDisabled && !checked) {
                  confirm({
                    title: t(($) => $.commandSchemas.basics.enableDisabledTitle),
                    content: t(($) => $.commandSchemas.basics.enableDisabledDescription, { commandId: displayId }),
                    okText: t(($) => $.commandSchemas.basics.enable),
                    cancelText: t(($) => $.commandSchemas.basics.cancel),
                    onOk: () => {
                      model.setCommandPatch(model.selectedCommandId, (p) => { p.disabled = checked })
                    },
                  })
                  return
                }
                model.setCommandPatch(model.selectedCommandId, (p) => { p.disabled = checked })
              }}
            />
          </div>
        </Space>

        <div style={{ marginTop: 12 }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Text>{t(($) => $.commandSchemas.basics.description)}</Text>
            <Space size="small">
              <Text type="secondary">{t(($) => $.commandSchemas.basics.override)}</Text>
              <Switch
                size="small"
                checked={descOver}
                onChange={(checked) => {
                  model.setCommandPatch(model.selectedCommandId, (p) => {
                    if (checked) {
                      p.description = safeText(model.selectedEffective?.description)
                    } else {
                      delete p.description
                    }
                  })
                }}
              />
            </Space>
          </Space>
          <Input.TextArea
            value={currentDesc}
            disabled={!descOver}
            onChange={(e) => model.setCommandPatch(model.selectedCommandId, (p) => { p.description = e.target.value })}
            rows={4}
          />
        </div>
      </Form>

      {model.selectedBase && (
        <Text type="secondary">
          {t(($) => $.commandSchemas.basics.baseSummary, {
            label: safeText(model.selectedBase.label).trim() || '-',
            scope: safeText(model.selectedBase.scope),
            risk: safeText(model.selectedBase.risk_level),
          })}
        </Text>
      )}
    </Space>
  )
}
