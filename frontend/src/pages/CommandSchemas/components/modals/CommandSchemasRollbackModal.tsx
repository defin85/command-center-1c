import { Input, Modal, Select, Space, Typography } from 'antd'

import { safeText } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasRollbackModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  return (
    <Modal
      title="Rollback overrides"
      open={model.rollbackOpen}
      onCancel={() => model.setRollbackOpen(false)}
      onOk={() => { void model.handleRollback() }}
      okText="Rollback"
      okButtonProps={{
        disabled: model.rollbackLoading || model.rollingBack || !model.rollbackVersion || !model.rollbackReason.trim(),
        'data-testid': 'command-schemas-rollback-confirm',
      }}
      cancelButtonProps={{ disabled: model.rollbackLoading || model.rollingBack }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Text type="secondary">Version</Text>
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
              label: `${v.version}${v.created_at ? ` (${v.created_at})` : ''}${v.created_by ? ` by ${v.created_by}` : ''}${reasonText ? ` - ${reasonText}` : ''}`,
            }
          })}
          placeholder="Select overrides version"
          showSearch
          optionFilterProp="label"
        />
        <Text type="secondary">Reason (required)</Text>
        <Input.TextArea
          data-testid="command-schemas-rollback-reason"
          value={model.rollbackReason}
          onChange={(e) => model.setRollbackReason(e.target.value)}
          placeholder="Why rollback?"
          rows={4}
          disabled={model.rollingBack}
        />
      </Space>
    </Modal>
  )
}

