import { Alert, Form, Select, Space, Switch, Typography } from 'antd'
import type { ModalFuncProps } from 'antd'

import { displayCommandId, normalizeStringList, safeText } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasPermissionsEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  if (!model.selectedCommandId || !model.selectedEffective) {
    return null
  }

  const displayId = displayCommandId(model.activeDriver, model.selectedCommandId)
  const patch = model.selectedPatch ?? {}
  const permissionsOver = Object.prototype.hasOwnProperty.call(patch, 'permissions')
  const basePermissionsRaw = (model.selectedBase?.permissions && typeof model.selectedBase.permissions === 'object')
    ? (model.selectedBase.permissions as Record<string, unknown>)
    : {}
  const effectivePermissionsRaw = (model.selectedEffective.permissions && typeof model.selectedEffective.permissions === 'object')
    ? (model.selectedEffective.permissions as Record<string, unknown>)
    : {}

  const baseAllowedRoles = normalizeStringList(basePermissionsRaw.allowed_roles)
  const baseDeniedRoles = normalizeStringList(basePermissionsRaw.denied_roles)
  const baseAllowedEnvs = normalizeStringList(basePermissionsRaw.allowed_envs)
  const baseDeniedEnvs = normalizeStringList(basePermissionsRaw.denied_envs)
  const baseMinDbLevel = safeText(basePermissionsRaw.min_db_level).toLowerCase() || ''

  const allowedRoles = normalizeStringList(effectivePermissionsRaw.allowed_roles)
  const deniedRoles = normalizeStringList(effectivePermissionsRaw.denied_roles)
  const allowedEnvs = normalizeStringList(effectivePermissionsRaw.allowed_envs)
  const deniedEnvs = normalizeStringList(effectivePermissionsRaw.denied_envs)
  const minDbLevel = safeText(effectivePermissionsRaw.min_db_level).toLowerCase() || ''

  const permissionsChangedFromBase = (
    JSON.stringify(allowedRoles) !== JSON.stringify(baseAllowedRoles)
    || JSON.stringify(deniedRoles) !== JSON.stringify(baseDeniedRoles)
    || JSON.stringify(allowedEnvs) !== JSON.stringify(baseAllowedEnvs)
    || JSON.stringify(deniedEnvs) !== JSON.stringify(baseDeniedEnvs)
    || minDbLevel !== baseMinDbLevel
  )

  const confirm = (config: ModalFuncProps) => model.confirm(config)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {permissionsChangedFromBase && (
        <Alert
          type="warning"
          showIcon
          message="Permissions/env constraints changed"
          description="You changed who can run the command and/or in which environments. Review carefully."
        />
      )}
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space direction="vertical" size={0}>
          <Text strong>Permissions</Text>
          <Text type="secondary">Optional constraints for roles/envs and min DB level.</Text>
        </Space>
        <Space size="small">
          <Text type="secondary">Override</Text>
          <Switch
            size="small"
            checked={permissionsOver}
            onChange={(checked) => {
              if (checked) {
                model.setCommandPatch(model.selectedCommandId, (p) => {
                  p.permissions = {
                    allowed_roles: allowedRoles,
                    denied_roles: deniedRoles,
                    allowed_envs: allowedEnvs,
                    denied_envs: deniedEnvs,
                    min_db_level: (minDbLevel === 'operate' || minDbLevel === 'manage' || minDbLevel === 'admin')
                      ? (minDbLevel as 'operate' | 'manage' | 'admin')
                      : undefined,
                  }
                })
                return
              }

              if (permissionsChangedFromBase) {
                confirm({
                  title: 'Permissions/env constraints changed',
                  content: `This will change permissions/env constraints for ${displayId}.`,
                  okText: 'Apply',
                  cancelText: 'Cancel',
                  onOk: () => {
                    model.setCommandPatch(model.selectedCommandId, (p) => {
                      delete p.permissions
                    })
                  },
                })
                return
              }

              model.setCommandPatch(model.selectedCommandId, (p) => {
                delete p.permissions
              })
            }}
          />
        </Space>
      </Space>

      <Form layout="vertical">
        <Form.Item label="Allowed roles">
          <Select
            mode="tags"
            value={allowedRoles}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.allowed_roles = value
            })}
            tokenSeparators={[',']}
            placeholder="e.g. staff, operators"
          />
        </Form.Item>
        <Form.Item label="Denied roles">
          <Select
            mode="tags"
            value={deniedRoles}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.denied_roles = value
            })}
            tokenSeparators={[',']}
            placeholder="e.g. guests"
          />
        </Form.Item>
        <Form.Item label="Allowed envs">
          <Select
            mode="tags"
            value={allowedEnvs}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.allowed_envs = value
            })}
            tokenSeparators={[',']}
            placeholder="e.g. prod, stage"
          />
        </Form.Item>
        <Form.Item label="Denied envs">
          <Select
            mode="tags"
            value={deniedEnvs}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.denied_envs = value
            })}
            tokenSeparators={[',']}
            placeholder="e.g. dev"
          />
        </Form.Item>
        <Form.Item label="Min DB level">
          <Select
            value={minDbLevel || undefined}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.min_db_level = (value || undefined) as 'operate' | 'manage' | 'admin' | undefined
            })}
            allowClear
            options={[
              { value: 'operate', label: 'operate' },
              { value: 'manage', label: 'manage' },
              { value: 'admin', label: 'admin' },
            ]}
          />
        </Form.Item>
      </Form>
    </Space>
  )
}
