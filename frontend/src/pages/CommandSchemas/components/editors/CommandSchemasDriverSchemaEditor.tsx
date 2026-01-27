import { Alert, Button, Card, Space } from 'antd'

import { LazyJsonCodeEditor } from '../../../../components/code/LazyJsonCodeEditor'
import { safeCatalogDriverSchema } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

export function CommandSchemasDriverSchemaEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  if (!model.view) {
    return <Alert type="info" showIcon message="Editor data is not loaded yet" />
  }

  const baseSchema = safeCatalogDriverSchema(model.view.catalogs?.base)
  const effectiveSchema = safeCatalogDriverSchema(model.view.catalogs?.effective?.catalog)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {model.canPromoteLatest && (
        <Alert
          type="warning"
          showIcon
          message="Base latest differs from approved"
          description="Guided mode edits overrides against approved base, while Raw mode shows base=latest. Promote latest → approved to make guided/effective reflect it."
          action={(
            <Button size="small" onClick={model.openPromote} disabled={model.promoting || model.loading || model.saving}>
              Promote latest...
            </Button>
          )}
        />
      )}
      <Alert
        type="info"
        showIcon
        message="Driver-level schema"
        description="Shared connection/options schema for this driver (independent from any selected command)."
      />
      <Card
        size="small"
        title="Driver schema patch (draft overrides)"
        extra={(
          <Space>
            <Button onClick={model.copyEffectiveDriverSchema}>Copy effective</Button>
            <Button
              data-testid="command-schemas-driver-schema-copy-latest"
              onClick={() => { void model.copyLatestBaseDriverSchema() }}
              loading={model.copyLatestDriverSchemaLoading}
              disabled={model.loading || model.saving || model.promoting}
            >
              Copy latest base
            </Button>
            <Button danger onClick={model.resetDriverSchemaOverrides}>Reset</Button>
          </Space>
        )}
      >
        <LazyJsonCodeEditor
          value={model.driverSchemaText}
          onChange={model.applyDriverSchemaText}
          height={260}
          path={`command-schemas-${model.activeDriver}-driver-schema-overrides.json`}
        />
        {model.driverSchemaTextError && (
          <div style={{ marginTop: 8 }}>
            <Alert type="error" showIcon message={model.driverSchemaTextError} />
          </div>
        )}
      </Card>
      <Card size="small" title="Base driver schema (read-only)">
        <LazyJsonCodeEditor
          value={JSON.stringify(baseSchema ?? {}, null, 2)}
          onChange={() => {}}
          height={260}
          path={`command-schemas-${model.activeDriver}-driver-schema-base.json`}
          readOnly
        />
      </Card>
      <Card size="small" title="Effective driver schema (read-only)">
        <LazyJsonCodeEditor
          value={JSON.stringify(effectiveSchema ?? {}, null, 2)}
          onChange={() => {}}
          height={260}
          path={`command-schemas-${model.activeDriver}-driver-schema-effective.json`}
          readOnly
        />
      </Card>
    </Space>
  )
}

