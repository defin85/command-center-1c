import { Alert, Button, Card, Space } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import { LazyJsonCodeEditor } from '../../../../components/code/LazyJsonCodeEditor'
import { safeCatalogDriverSchema } from '../../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../../useCommandSchemasPageModel'

export function CommandSchemasDriverSchemaEditor(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  if (!model.view) {
    return <Alert type="info" showIcon message={t(($) => $.commandSchemas.driverSchema.editorNotLoaded)} />
  }

  const baseSchema = safeCatalogDriverSchema(model.view.catalogs?.base)
  const effectiveSchema = safeCatalogDriverSchema(model.view.catalogs?.effective?.catalog)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {model.canPromoteLatest && (
        <Alert
          type="warning"
          showIcon
          message={t(($) => $.commandSchemas.driverSchema.latestDiffersTitle)}
          description={t(($) => $.commandSchemas.driverSchema.latestDiffersDescription)}
          action={(
            <Button size="small" onClick={model.openPromote} disabled={model.promoting || model.loading || model.saving}>
              {t(($) => $.commandSchemas.driverSchema.promoteLatest)}
            </Button>
          )}
        />
      )}
      <Alert
        type="info"
        showIcon
        message={t(($) => $.commandSchemas.driverSchema.schemaTitle)}
        description={t(($) => $.commandSchemas.driverSchema.schemaDescription)}
      />
      <Card
        size="small"
        title={t(($) => $.commandSchemas.driverSchema.patchTitle)}
        extra={(
          <Space>
            <Button onClick={model.copyEffectiveDriverSchema}>{t(($) => $.commandSchemas.driverSchema.copyEffective)}</Button>
            <Button
              data-testid="command-schemas-driver-schema-copy-latest"
              onClick={() => { void model.copyLatestBaseDriverSchema() }}
              loading={model.copyLatestDriverSchemaLoading}
              disabled={model.loading || model.saving || model.promoting}
            >
              {t(($) => $.commandSchemas.driverSchema.copyLatestBase)}
            </Button>
            <Button danger onClick={model.resetDriverSchemaOverrides}>{t(($) => $.commandSchemas.driverSchema.reset)}</Button>
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
      <Card size="small" title={t(($) => $.commandSchemas.driverSchema.baseReadOnly)}>
        <LazyJsonCodeEditor
          value={JSON.stringify(baseSchema ?? {}, null, 2)}
          onChange={() => {}}
          height={260}
          path={`command-schemas-${model.activeDriver}-driver-schema-base.json`}
          readOnly
        />
      </Card>
      <Card size="small" title={t(($) => $.commandSchemas.driverSchema.effectiveReadOnly)}>
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
