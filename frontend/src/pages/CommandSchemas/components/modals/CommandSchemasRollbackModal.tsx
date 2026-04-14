import { Input, Modal, Select, Space, Typography } from 'antd'
import { useAdminSupportTranslation, useLocaleFormatters } from '@/i18n'

import { safeText } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasRollbackModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()
  const formatters = useLocaleFormatters()

  return (
    <Modal
      title={t(($) => $.commandSchemas.modals.rollbackTitle)}
      open={model.rollbackOpen}
      onCancel={() => model.setRollbackOpen(false)}
      onOk={() => { void model.handleRollback() }}
      okText={t(($) => $.commandSchemas.modals.rollback)}
      okButtonProps={{
        disabled: model.rollbackLoading || model.rollingBack || !model.rollbackVersion || !model.rollbackReason.trim(),
        'data-testid': 'command-schemas-rollback-confirm',
      }}
      cancelButtonProps={{ disabled: model.rollbackLoading || model.rollingBack }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Text type="secondary">{t(($) => $.commandSchemas.modals.versionLabel)}</Text>
        <Select
          data-testid="command-schemas-rollback-version"
          value={model.rollbackVersion || undefined}
          onChange={model.setRollbackVersion}
          loading={model.rollbackLoading}
          disabled={model.rollingBack}
          options={model.rollbackVersions.map((v) => {
            const reasonText = safeText(v.metadata?.['reason']).trim()
            return {
              value: v.version,
              label: `${v.version}${v.created_at ? ` (${formatters.dateTime(v.created_at, { fallback: v.created_at })})` : ''}${v.created_by ? ` by ${v.created_by}` : ''}${reasonText ? ` - ${reasonText}` : ''}`,
            }
          })}
          placeholder={t(($) => $.commandSchemas.modals.selectVersion)}
          showSearch
          optionFilterProp="label"
        />
        <Text type="secondary">{t(($) => $.commandSchemas.modals.reasonLabel)}</Text>
        <Input.TextArea
          data-testid="command-schemas-rollback-reason"
          value={model.rollbackReason}
          onChange={(e) => model.setRollbackReason(e.target.value)}
          placeholder={t(($) => $.commandSchemas.modals.rollbackReasonPlaceholder)}
          rows={4}
          disabled={model.rollingBack}
        />
      </Space>
    </Modal>
  )
}
