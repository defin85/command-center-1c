import { Alert, Card, Space } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import { LazyJsonCodeEditor } from '../../../../components/code/LazyJsonCodeEditor'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

export function CommandSchemasAdvancedEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  if (!model.selectedCommandId) {
    return <Alert type="info" showIcon message={t(($) => $.commandSchemas.advanced.selectCommand)} />
  }
  const patch = model.overridesById[model.selectedCommandId] ?? {}
  const base = model.selectedBase ?? {}
  const effective = model.selectedEffective ?? {}

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card size="small" title={t(($) => $.commandSchemas.advanced.patchTitle)}>
        <LazyJsonCodeEditor
          value={JSON.stringify(patch, null, 2)}
          onChange={() => {}}
          height={260}
          path={`command-schemas-${model.activeDriver}-${model.selectedCommandId}-patch.json`}
        />
      </Card>
      <Card size="small" title={t(($) => $.commandSchemas.advanced.baseReadOnly)}>
        <LazyJsonCodeEditor
          value={JSON.stringify(base, null, 2)}
          onChange={() => {}}
          height={260}
          path={`command-schemas-${model.activeDriver}-${model.selectedCommandId}-base.json`}
        />
      </Card>
      <Card size="small" title={t(($) => $.commandSchemas.advanced.effectiveReadOnly)}>
        <LazyJsonCodeEditor
          value={JSON.stringify(effective, null, 2)}
          onChange={() => {}}
          height={260}
          path={`command-schemas-${model.activeDriver}-${model.selectedCommandId}-effective.json`}
        />
      </Card>
    </Space>
  )
}
