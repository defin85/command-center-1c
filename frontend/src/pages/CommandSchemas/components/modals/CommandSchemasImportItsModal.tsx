import { Alert, Button, Input, Modal, Space, Typography, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'

import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasImportItsModal(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  return (
    <Modal
      title={`Import ITS JSON (${model.activeDriver.toUpperCase()})`}
      open={model.importItsOpen}
      onCancel={() => model.setImportItsOpen(false)}
      onOk={() => { void model.handleImportIts() }}
      okText="Import"
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
          message="ITS export"
          description={(
            <Space direction="vertical">
              <Text>Export ITS JSON via scripts/dev/its-scrape.py and upload it here to build base catalog.</Text>
              <Text type="secondary">
                Recommended: <Text code>python scripts/dev/its-scrape.py --with-blocks --no-raw-text</Text>
              </Text>
            </Space>
          )}
        />
        <Text type="secondary">ITS JSON file</Text>
        <Upload
          accept=".json,application/json"
          showUploadList={false}
          beforeUpload={model.handleImportItsFile}
          disabled={model.importingIts}
        >
          <Button icon={<UploadOutlined />} data-testid="command-schemas-import-its-file">
            Select file...
          </Button>
        </Upload>
        {model.importItsFile && (
          <Text type="secondary">Selected: {model.importItsFile.name}</Text>
        )}
        <Text type="secondary">Reason (required)</Text>
        <Input.TextArea
          data-testid="command-schemas-import-its-reason"
          value={model.importItsReason}
          onChange={(e) => model.setImportItsReason(e.target.value)}
          placeholder="Why import ITS?"
          rows={4}
          disabled={model.importingIts}
        />
      </Space>
    </Modal>
  )
}

