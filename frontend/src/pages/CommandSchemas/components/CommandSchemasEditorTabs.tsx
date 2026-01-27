import { Alert, Tabs } from 'antd'

import type { CommandSchemasPageModel } from '../useCommandSchemasPageModel'
import { CommandSchemasAdvancedEditor } from './editors/CommandSchemasAdvancedEditor'
import { CommandSchemasBasicsEditor } from './editors/CommandSchemasBasicsEditor'
import { CommandSchemasDriverSchemaEditor } from './editors/CommandSchemasDriverSchemaEditor'
import { CommandSchemasParamsEditor } from './editors/CommandSchemasParamsEditor'
import { CommandSchemasPermissionsEditor } from './editors/CommandSchemasPermissionsEditor'

export function CommandSchemasEditorTabs(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  return (
    <Tabs
      activeKey={model.activeEditorTab}
      onChange={(key) => model.setActiveEditorTab(key as typeof model.activeEditorTab)}
      items={[
        {
          key: 'basics',
          label: 'Basics',
          children: model.selectedCommandId && model.selectedEffective
            ? <CommandSchemasBasicsEditor model={model} />
            : <Alert type="info" message="Select a command from the list" showIcon />,
        },
        {
          key: 'permissions',
          label: 'Permissions',
          children: model.selectedCommandId && model.selectedEffective
            ? <CommandSchemasPermissionsEditor model={model} />
            : <Alert type="info" message="Select a command from the list" showIcon />,
        },
        {
          key: 'params',
          label: 'Params',
          children: model.selectedCommandId && model.selectedEffective
            ? <CommandSchemasParamsEditor model={model} />
            : <Alert type="info" message="Select a command from the list" showIcon />,
        },
        {
          key: 'driver',
          label: 'Driver',
          children: <CommandSchemasDriverSchemaEditor model={model} />,
        },
        {
          key: 'advanced',
          label: 'Advanced',
          children: <CommandSchemasAdvancedEditor model={model} />,
        },
      ]}
    />
  )
}
