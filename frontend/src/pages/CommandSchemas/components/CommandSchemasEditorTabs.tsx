import { Alert, Tabs } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import type { CommandSchemasPageModel } from '../useCommandSchemasPageModel'
import { CommandSchemasAdvancedEditor } from './editors/CommandSchemasAdvancedEditor'
import { CommandSchemasBasicsEditor } from './editors/CommandSchemasBasicsEditor'
import { CommandSchemasDriverSchemaEditor } from './editors/CommandSchemasDriverSchemaEditor'
import { CommandSchemasParamsEditor } from './editors/CommandSchemasParamsEditor'
import { CommandSchemasPermissionsEditor } from './editors/CommandSchemasPermissionsEditor'

export function CommandSchemasEditorTabs(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  return (
    <Tabs
      activeKey={model.activeEditorTab}
      onChange={(key) => model.setActiveEditorTab(key as typeof model.activeEditorTab)}
      items={[
        {
          key: 'basics',
          label: t(($) => $.commandSchemas.tabs.basics),
          children: model.selectedCommandId && model.selectedEffective
            ? <CommandSchemasBasicsEditor model={model} />
            : <Alert type="info" message={t(($) => $.commandSchemas.tabs.selectCommand)} showIcon />,
        },
        {
          key: 'permissions',
          label: t(($) => $.commandSchemas.tabs.permissions),
          children: model.selectedCommandId && model.selectedEffective
            ? <CommandSchemasPermissionsEditor model={model} />
            : <Alert type="info" message={t(($) => $.commandSchemas.tabs.selectCommand)} showIcon />,
        },
        {
          key: 'params',
          label: t(($) => $.commandSchemas.tabs.params),
          children: model.selectedCommandId && model.selectedEffective
            ? <CommandSchemasParamsEditor model={model} />
            : <Alert type="info" message={t(($) => $.commandSchemas.tabs.selectCommand)} showIcon />,
        },
        {
          key: 'driver',
          label: t(($) => $.commandSchemas.tabs.driver),
          children: <CommandSchemasDriverSchemaEditor model={model} />,
        },
        {
          key: 'advanced',
          label: t(($) => $.commandSchemas.tabs.advanced),
          children: <CommandSchemasAdvancedEditor model={model} />,
        },
      ]}
    />
  )
}
