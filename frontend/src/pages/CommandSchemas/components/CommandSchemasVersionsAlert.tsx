import { Alert, Space, Typography } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import type { CommandSchemasEditorView } from '../../../api/commandSchemas'

const { Text } = Typography

export function CommandSchemasVersionsAlert(props: { view: CommandSchemasEditorView }) {
  const { t } = useAdminSupportTranslation()

  return (
    <Alert
      type="info"
      showIcon
      message={t(($) => $.commandSchemas.versions.title)}
      description={(
        <Space direction="vertical" size={2}>
          <Text type="secondary">{t(($) => $.commandSchemas.versions.baseApproved, { value: props.view.base.approved_version ?? '-' })}</Text>
          <Text type="secondary">{t(($) => $.commandSchemas.versions.baseLatest, { value: props.view.base.latest_version ?? '-' })}</Text>
          <Text type="secondary">{t(($) => $.commandSchemas.versions.overridesActive, { value: props.view.overrides.active_version ?? '-' })}</Text>
          <Text type="secondary">{t(($) => $.commandSchemas.versions.etag, { value: props.view.etag })}</Text>
        </Space>
      )}
    />
  )
}
