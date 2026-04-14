import { Alert, Button, Space } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

export function CommandSchemasUnsavedBanner(props: {
  overridesCounts: { commands: number; params: number; permissions: number; driver_schema: number }
  saving: boolean
  onDiscard: () => void
  onSave: () => void
}) {
  const { t } = useAdminSupportTranslation()
  const description = t(($) => $.commandSchemas.unsaved.description, {
    driverSchema: String(props.overridesCounts.driver_schema),
    commands: String(props.overridesCounts.commands),
    params: String(props.overridesCounts.params),
    permissions: String(props.overridesCounts.permissions),
  })

  return (
    <div data-testid="command-schemas-unsaved-banner" style={{ position: 'sticky', top: 0, zIndex: 20, background: '#fff' }}>
      <Alert
        type="warning"
        showIcon
        message={t(($) => $.commandSchemas.unsaved.title)}
        description={description}
        action={(
          <Space>
            <Button size="small" onClick={props.onDiscard} disabled={props.saving}>
              {t(($) => $.commandSchemas.unsaved.discard)}
            </Button>
            <Button size="small" type="primary" onClick={props.onSave} disabled={props.saving}>
              {t(($) => $.commandSchemas.unsaved.save)}
            </Button>
          </Space>
        )}
      />
    </div>
  )
}
