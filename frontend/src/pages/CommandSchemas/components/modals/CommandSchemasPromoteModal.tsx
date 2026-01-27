import { Alert, Input, Modal, Space, Typography } from 'antd'

import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasPromoteModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  return (
    <Modal
      title="Promote base catalog"
      open={model.promoteOpen}
      onCancel={() => model.setPromoteOpen(false)}
      onOk={() => { void model.handlePromote() }}
      okText="Promote"
      okButtonProps={{
        disabled: model.promoting || !model.promoteReason.trim() || !model.canPromoteLatest,
        loading: model.promoting,
        'data-testid': 'command-schemas-promote-confirm',
      }}
      cancelButtonProps={{ disabled: model.promoting }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message="Promote latest → approved"
          description={`driver=${model.activeDriver}, latest=${model.view?.base.latest_version ?? '-'}, approved=${model.view?.base.approved_version ?? '-'}`}
        />
        <Text type="secondary">Reason (required)</Text>
        <Input.TextArea
          data-testid="command-schemas-promote-reason"
          value={model.promoteReason}
          onChange={(e) => model.setPromoteReason(e.target.value)}
          placeholder="Why are you promoting this base catalog?"
          rows={4}
          disabled={model.promoting}
        />
      </Space>
    </Modal>
  )
}

