import { Alert, Input, Modal, Space, Typography } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasSaveModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  if (model.mode !== 'guided') {
    return null
  }

  return (
    <Modal
      title={t(($) => $.commandSchemas.modals.saveTitle)}
      open={model.saveOpen}
      onCancel={() => model.setSaveOpen(false)}
      onOk={() => { void model.handleSave() }}
      okText={t(($) => $.commandSchemas.modals.save)}
      okButtonProps={{ loading: model.saving, 'data-testid': 'command-schemas-save-confirm' }}
      cancelButtonProps={{ disabled: model.saving }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message={t(($) => $.commandSchemas.modals.summary)}
          description={`driver_schema=${model.overridesCounts.driver_schema}, commands=${model.overridesCounts.commands}, params=${model.overridesCounts.params}, permissions=${model.overridesCounts.permissions}`}
        />
        <Text type="secondary">{t(($) => $.commandSchemas.modals.reasonLabel)}</Text>
        <Input.TextArea
          data-testid="command-schemas-save-reason"
          value={model.saveReason}
          onChange={(e) => model.setSaveReason(e.target.value)}
          placeholder={t(($) => $.commandSchemas.modals.reasonPlaceholder)}
          rows={4}
        />
      </Space>
    </Modal>
  )
}
