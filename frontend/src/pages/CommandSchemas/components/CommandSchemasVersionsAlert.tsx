import { Alert, Space, Typography } from 'antd'

import type { CommandSchemasEditorView } from '../../../api/commandSchemas'

const { Text } = Typography

export function CommandSchemasVersionsAlert(props: { view: CommandSchemasEditorView }) {
  return (
    <Alert
      type="info"
      showIcon
      message="Versions"
      description={(
        <Space direction="vertical" size={2}>
          <Text type="secondary">Base approved: {props.view.base.approved_version ?? '-'}</Text>
          <Text type="secondary">Base latest: {props.view.base.latest_version ?? '-'}</Text>
          <Text type="secondary">Overrides active: {props.view.overrides.active_version ?? '-'}</Text>
          <Text type="secondary">ETag: {props.view.etag}</Text>
        </Space>
      )}
    />
  )
}

