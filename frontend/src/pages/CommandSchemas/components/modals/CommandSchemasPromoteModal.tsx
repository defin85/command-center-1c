import { Alert, Input, Modal, Space, Typography } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasPromoteModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  return (
    <Modal
      title={t(($) => $.commandSchemas.modals.promoteTitle)}
      open={model.promoteOpen}
      onCancel={() => model.setPromoteOpen(false)}
      onOk={() => { void model.handlePromote() }}
      okText={t(($) => $.commandSchemas.modals.promote)}
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
          message={t(($) => $.commandSchemas.modals.promoteSummary)}
          description={`driver=${model.activeDriver}, latest=${model.view?.base.latest_version ?? '-'}, approved=${model.view?.base.approved_version ?? '-'}`}
        />
        <Text type="secondary">{t(($) => $.commandSchemas.modals.reasonLabel)}</Text>
        <Input.TextArea
          data-testid="command-schemas-promote-reason"
          value={model.promoteReason}
          onChange={(e) => model.setPromoteReason(e.target.value)}
          placeholder={t(($) => $.commandSchemas.modals.promoteReasonPlaceholder)}
          rows={4}
          disabled={model.promoting}
        />
      </Space>
    </Modal>
  )
}
