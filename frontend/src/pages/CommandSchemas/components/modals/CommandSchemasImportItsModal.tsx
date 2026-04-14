import { Alert, Button, Input, Modal, Space, Typography, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { useAdminSupportTranslation } from '@/i18n'

import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasImportItsModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  return (
    <Modal
      title={t(($) => $.commandSchemas.modals.importItsTitle, { driver: model.activeDriver.toUpperCase() })}
      open={model.importItsOpen}
      onCancel={() => model.setImportItsOpen(false)}
      onOk={() => { void model.handleImportIts() }}
      okText={t(($) => $.commandSchemas.modals.importIts)}
      okButtonProps={{
        disabled: model.importingIts || !model.importItsFile || !model.importItsReason.trim(),
        loading: model.importingIts,
        'data-testid': 'command-schemas-import-its-confirm',
      }}
      cancelButtonProps={{ disabled: model.importingIts }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message={t(($) => $.commandSchemas.modals.importItsInfoTitle)}
          description={(
            <Space direction="vertical">
              <Text>{t(($) => $.commandSchemas.modals.importItsInfoDescription)}</Text>
              <Text type="secondary">
                {t(($) => $.commandSchemas.modals.importItsRecommended, { command: 'python scripts/dev/its-scrape.py --with-blocks --no-raw-text' })}
              </Text>
            </Space>
          )}
        />
        <Text type="secondary">{t(($) => $.commandSchemas.modals.importItsFileLabel)}</Text>
        <Upload
          accept=".json,application/json"
          showUploadList={false}
          beforeUpload={model.handleImportItsFile}
          disabled={model.importingIts}
        >
          <Button icon={<UploadOutlined />} data-testid="command-schemas-import-its-file">
            {t(($) => $.commandSchemas.modals.importItsSelectFile)}
          </Button>
        </Upload>
        {model.importItsFile && (
          <Text type="secondary">{t(($) => $.commandSchemas.modals.importItsSelected, { name: model.importItsFile.name })}</Text>
        )}
        <Text type="secondary">{t(($) => $.commandSchemas.modals.reasonLabel)}</Text>
        <Input.TextArea
          data-testid="command-schemas-import-its-reason"
          value={model.importItsReason}
          onChange={(e) => model.setImportItsReason(e.target.value)}
          placeholder={t(($) => $.commandSchemas.modals.importItsReasonPlaceholder)}
          rows={4}
          disabled={model.importingIts}
        />
      </Space>
    </Modal>
  )
}
