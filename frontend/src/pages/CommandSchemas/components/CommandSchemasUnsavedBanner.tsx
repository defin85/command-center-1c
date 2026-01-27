import { Alert, Button, Space } from 'antd'

export function CommandSchemasUnsavedBanner(props: {
  overridesCounts: { commands: number; params: number; permissions: number; driver_schema: number }
  saving: boolean
  onDiscard: () => void
  onSave: () => void
}) {
  return (
    <div data-testid="command-schemas-unsaved-banner" style={{ position: 'sticky', top: 0, zIndex: 20, background: '#fff' }}>
      <Alert
        type="warning"
        showIcon
        message="Unsaved changes"
        description={`driver_schema=${props.overridesCounts.driver_schema}, commands=${props.overridesCounts.commands}, params=${props.overridesCounts.params}, permissions=${props.overridesCounts.permissions}`}
        action={(
          <Space>
            <Button size="small" onClick={props.onDiscard} disabled={props.saving}>
              Discard
            </Button>
            <Button size="small" type="primary" onClick={props.onSave} disabled={props.saving}>
              Save...
            </Button>
          </Space>
        )}
      />
    </div>
  )
}

