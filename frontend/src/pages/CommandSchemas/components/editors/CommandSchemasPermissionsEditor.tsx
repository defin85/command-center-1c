import { Alert, Form, Select, Space, Switch, Typography } from 'antd'
import type { ModalFuncProps } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import { displayCommandId, normalizeStringList, safeText } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasPermissionsEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

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
          message={t(($) => $.commandSchemas.permissions.changedTitle)}
          description={t(($) => $.commandSchemas.permissions.changedDescription)}
        />
      )}
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space direction="vertical" size={0}>
          <Text strong>{t(($) => $.commandSchemas.permissions.title)}</Text>
          <Text type="secondary">{t(($) => $.commandSchemas.permissions.subtitle)}</Text>
        </Space>
        <Space size="small">
          <Text type="secondary">{t(($) => $.commandSchemas.permissions.override)}</Text>
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
                  title: t(($) => $.commandSchemas.permissions.confirmTitle),
                  content: t(($) => $.commandSchemas.permissions.confirmDescription, { commandId: displayId }),
                  okText: t(($) => $.commandSchemas.basics.apply),
                  cancelText: t(($) => $.commandSchemas.basics.cancel),
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
        <Form.Item label={t(($) => $.commandSchemas.permissions.allowedRoles)}>
          <Select
            mode="tags"
            value={allowedRoles}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.allowed_roles = value
            })}
            tokenSeparators={[',']}
            placeholder={t(($) => $.commandSchemas.permissions.placeholderAllowedRoles)}
          />
        </Form.Item>
        <Form.Item label={t(($) => $.commandSchemas.permissions.deniedRoles)}>
          <Select
            mode="tags"
            value={deniedRoles}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.denied_roles = value
            })}
            tokenSeparators={[',']}
            placeholder={t(($) => $.commandSchemas.permissions.placeholderDeniedRoles)}
          />
        </Form.Item>
        <Form.Item label={t(($) => $.commandSchemas.permissions.allowedEnvs)}>
          <Select
            mode="tags"
            value={allowedEnvs}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.allowed_envs = value
            })}
            tokenSeparators={[',']}
            placeholder={t(($) => $.commandSchemas.permissions.placeholderAllowedEnvs)}
          />
        </Form.Item>
        <Form.Item label={t(($) => $.commandSchemas.permissions.deniedEnvs)}>
          <Select
            mode="tags"
            value={deniedEnvs}
            disabled={!permissionsOver}
            onChange={(value) => model.setCommandPatch(model.selectedCommandId, (p) => {
              if (!p.permissions) p.permissions = {}
              p.permissions.denied_envs = value
            })}
            tokenSeparators={[',']}
            placeholder={t(($) => $.commandSchemas.permissions.placeholderDeniedEnvs)}
          />
        </Form.Item>
        <Form.Item label={t(($) => $.commandSchemas.permissions.minDbLevel)}>
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
