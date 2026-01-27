import { Alert, Input, Modal, Space, Typography } from 'antd'

import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasSaveModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  if (model.mode !== 'guided') {
    return null
  }

  return (
    <Modal
      title="Save overrides"
      open={model.saveOpen}
      onCancel={() => model.setSaveOpen(false)}
      onOk={() => { void model.handleSave() }}
      okText="Save"
      okButtonProps={{ loading: model.saving, 'data-testid': 'command-schemas-save-confirm' }}
      cancelButtonProps={{ disabled: model.saving }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message="Summary"
          description={`driver_schema=${model.overridesCounts.driver_schema}, commands=${model.overridesCounts.commands}, params=${model.overridesCounts.params}, permissions=${model.overridesCounts.permissions}`}
        />
        <Text type="secondary">Reason (required)</Text>
        <Input.TextArea
          data-testid="command-schemas-save-reason"
          value={model.saveReason}
          onChange={(e) => model.setSaveReason(e.target.value)}
          placeholder="Why are you changing command schemas?"
          rows={4}
        />
      </Space>
    </Modal>
  )
}
