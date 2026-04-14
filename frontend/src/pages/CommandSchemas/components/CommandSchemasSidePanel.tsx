import { Alert, Button, Card, Input, Select, Space, Switch, Tabs, Tag, Typography } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import type { DriverCommandParamV2 } from '../../../api/driverCommands'
import { LazyJsonCodeEditor } from '../../../components/code/LazyJsonCodeEditor'
import { normalizeStringList, parseJsonObject, safeText } from '../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasSidePanel(props: { model: CommandSchemasPageModel }) {
  const model = props.model
  const { t } = useAdminSupportTranslation()

  const hasSelection = Boolean(model.selectedCommandId && model.selectedEffective)
  const paramsByName =
    hasSelection && model.selectedEffective && model.selectedEffective.params_by_name && typeof model.selectedEffective.params_by_name === 'object'
      ? (model.selectedEffective.params_by_name as Record<string, DriverCommandParamV2>)
      : {}
  const paramNames = Object.keys(paramsByName).sort()

  return (
    <Tabs
      activeKey={model.activeSideTab}
      onChange={(key) => model.setActiveSideTab(key as typeof model.activeSideTab)}
      items={[
        {
          key: 'preview',
          label: t(($) => $.commandSchemas.sidePanel.preview),
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {!hasSelection && <Alert type="info" showIcon message={t(($) => $.commandSchemas.sidePanel.selectCommandToPreview)} />}
              <Space wrap>
                <Select
                  value={model.previewMode}
                  onChange={(v) => model.setPreviewMode(v)}
                  style={{ width: 140 }}
                  options={[
                    { value: 'guided', label: t(($) => $.commandSchemas.sidePanel.previewModeGuided) },
                    { value: 'manual', label: t(($) => $.commandSchemas.sidePanel.previewModeManual) },
                  ]}
                />
                <Button
                  onClick={() => { void model.buildPreview() }}
                  loading={model.previewLoading}
                  disabled={!hasSelection || (model.activeDriver === 'ibcmd' && Boolean(model.previewConnectionError))}
                >
                  {t(($) => $.commandSchemas.sidePanel.buildArgv)}
                </Button>
              </Space>

              {model.activeDriver === 'ibcmd' && (
                <Card size="small" title={t(($) => $.commandSchemas.sidePanel.connectionTitle)}>
                  <LazyJsonCodeEditor
                    value={model.previewConnectionText}
                    onChange={(nextText) => {
                      model.setPreviewConnectionText(nextText)
                      model.setPreviewConnectionError(parseJsonObject(nextText) ? null : t(($) => $.commandSchemas.sidePanel.invalidJsonExpectedObject))
                    }}
                    height={180}
                    path={`command-schemas-${model.activeDriver}-${model.selectedCommandId}-preview-connection.json`}
                  />
                  {model.previewConnectionError && (
                    <div style={{ marginTop: 8 }}>
                      <Alert type="error" showIcon message={model.previewConnectionError} />
                    </div>
                  )}
                </Card>
              )}

              {paramNames.length > 0 && (
                <Card size="small" title={t(($) => $.commandSchemas.sidePanel.paramsTitle)}>
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {paramNames.map((name) => {
                      const schema = paramsByName[name]
                      const expectsValue = Boolean(schema.expects_value)
                      const kind = safeText(schema.kind)
                      const isRequired = Boolean(schema.required)
                      const isSensitive = Boolean(schema.sensitive)
                      const enumValues = normalizeStringList(schema.enum)
                      const currentValue = model.previewParams[name]

                      const setValue = (value: unknown) => {
                        model.setPreviewParams((prev) => ({ ...prev, [name]: value }))
                      }

                      return (
                        <div key={name}>
                          <Space wrap>
                            <Text code>{name}</Text>
                            {isRequired && <Tag color="red">{t(($) => $.commandSchemas.sidePanel.required)}</Tag>}
                            {isSensitive && <Tag color="orange">{t(($) => $.commandSchemas.sidePanel.sensitive)}</Tag>}
                            {kind === 'flag' && safeText(schema.flag) && <Tag>{safeText(schema.flag)}</Tag>}
                            {kind === 'positional' && Number.isFinite(Number(schema.position)) && (
                              <Tag>{t(($) => $.commandSchemas.sidePanel.position, { value: String(Number(schema.position)) })}</Tag>
                            )}
                          </Space>
                          <div style={{ marginTop: 6 }}>
                            {!expectsValue ? (
                              <Switch
                                checked={Boolean(currentValue)}
                                onChange={(checked) => setValue(checked)}
                              />
                            ) : enumValues.length > 0 ? (
                              <Select
                                value={safeText(currentValue) || undefined}
                                onChange={(v) => setValue(v)}
                                style={{ width: '100%' }}
                                options={enumValues.map((v) => ({ value: v, label: v }))}
                                allowClear
                              />
                            ) : isSensitive ? (
                              <Input.Password
                                value={safeText(currentValue)}
                                onChange={(e) => setValue(e.target.value)}
                                placeholder={t(($) => $.commandSchemas.sidePanel.valuePlaceholder)}
                              />
                            ) : (
                              <Input
                                value={safeText(currentValue)}
                                onChange={(e) => setValue(e.target.value)}
                                placeholder={t(($) => $.commandSchemas.sidePanel.valuePlaceholder)}
                              />
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </Space>
                </Card>
              )}

              <Card size="small" title={t(($) => $.commandSchemas.sidePanel.additionalArgsTitle)}>
                <Input.TextArea
                  value={model.previewArgsText}
                  onChange={(e) => model.setPreviewArgsText(e.target.value)}
                  rows={4}
                  placeholder={t(($) => $.commandSchemas.sidePanel.additionalArgsPlaceholder)}
                />
              </Card>

              {model.previewError && <Alert type="warning" showIcon message={t(($) => $.commandSchemas.sidePanel.previewError)} description={model.previewError} />}

              <Card size="small" title={t(($) => $.commandSchemas.sidePanel.argv)}>
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  {model.previewArgv.length === 0 ? (
                    <Text type="secondary">{t(($) => $.commandSchemas.sidePanel.noPreviewYet)}</Text>
                  ) : (
                    model.previewArgv.map((line, idx) => <Text key={idx} code>{line}</Text>)
                  )}
                </Space>
              </Card>
              <Card size="small" title={t(($) => $.commandSchemas.sidePanel.argvMasked)}>
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  {model.previewArgvMasked.length === 0 ? (
                    <Text type="secondary">{t(($) => $.commandSchemas.sidePanel.noPreviewYet)}</Text>
                  ) : (
                    model.previewArgvMasked.map((line, idx) => <Text key={idx} code>{line}</Text>)
                  )}
                </Space>
              </Card>
            </Space>
          ),
        },
        {
          key: 'diff',
          label: t(($) => $.commandSchemas.sidePanel.diff),
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {!hasSelection && <Alert type="info" showIcon message={t(($) => $.commandSchemas.sidePanel.selectCommandToDiff)} />}
              <Button onClick={() => { void model.loadDiff() }} loading={model.diffLoading} disabled={!hasSelection}>
                {t(($) => $.commandSchemas.sidePanel.loadDiff)}
              </Button>
              {model.diffError && <Alert type="warning" showIcon message={t(($) => $.commandSchemas.sidePanel.diffError)} description={model.diffError} />}
              <div style={{ maxHeight: 620, overflow: 'auto' }}>
                <Card size="small" title={t(($) => $.commandSchemas.sidePanel.changes, { count: model.diffItems.length })}>
                  {model.diffItems.length === 0 ? (
                    <Text type="secondary">{t(($) => $.commandSchemas.sidePanel.noChanges)}</Text>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left', padding: '6px 8px' }}>{t(($) => $.commandSchemas.sidePanel.path)}</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px' }}>{t(($) => $.commandSchemas.sidePanel.base)}</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px' }}>{t(($) => $.commandSchemas.sidePanel.effective)}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {model.diffItems.map((row) => (
                            <tr key={row.path}>
                              <td style={{ padding: '6px 8px', verticalAlign: 'top' }}><Text code>{row.path}</Text></td>
                              <td style={{ padding: '6px 8px', verticalAlign: 'top' }}>
                                {row.base_present ? <Text>{safeText(JSON.stringify(row.base))}</Text> : <Text type="secondary">-</Text>}
                              </td>
                              <td style={{ padding: '6px 8px', verticalAlign: 'top' }}>
                                {row.effective_present ? <Text>{safeText(JSON.stringify(row.effective))}</Text> : <Text type="secondary">-</Text>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              </div>
            </Space>
          ),
        },
        {
          key: 'validate',
          label: t(($) => $.commandSchemas.sidePanel.validate),
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Button onClick={() => { void model.runValidate() }} loading={model.validateLoading}>
                {t(($) => $.commandSchemas.sidePanel.validateCatalog)}
              </Button>
              {model.validateError && <Alert type="warning" showIcon message={t(($) => $.commandSchemas.sidePanel.validationError)} description={model.validateError} />}
              {model.validateSummary && (
                <Alert
                  type={model.validateSummary.ok ? 'success' : 'warning'}
                  showIcon
                  message={model.validateSummary.ok ? t(($) => $.commandSchemas.sidePanel.ok) : t(($) => $.commandSchemas.sidePanel.validationFailed)}
                  description={`errors=${model.validateSummary.errors}, warnings=${model.validateSummary.warnings}`}
                />
              )}
              <Card size="small" title={t(($) => $.commandSchemas.sidePanel.globalIssues, { count: model.globalIssues.length })}>
                {model.globalIssues.length === 0 ? (
                  <Text type="secondary">{t(($) => $.commandSchemas.sidePanel.noIssues)}</Text>
                ) : (
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {model.globalIssues.map((issue, idx) => (
                      <Alert
                        key={`${issue.code}-${idx}`}
                        type={issue.severity === 'error' ? 'error' : 'warning'}
                        showIcon
                        message={`${issue.code}: ${issue.message}`}
                        description={issue.path ? <Text code>{issue.path}</Text> : undefined}
                      />
                    ))}
                  </Space>
                )}
              </Card>
              <Card size="small" title={t(($) => $.commandSchemas.sidePanel.issuesForSelected, { count: model.issuesForSelected.length })}>
                {!hasSelection ? (
                  <Text type="secondary">{t(($) => $.commandSchemas.sidePanel.noCommandSelected)}</Text>
                ) : model.issuesForSelected.length === 0 ? (
                  <Text type="secondary">{t(($) => $.commandSchemas.sidePanel.noIssues)}</Text>
                ) : (
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {model.issuesForSelected.map((issue, idx) => (
                      <Alert
                        key={`${issue.code}-${idx}`}
                        type={issue.severity === 'error' ? 'error' : 'warning'}
                        showIcon
                        message={`${issue.code}: ${issue.message}`}
                        description={issue.path ? <Text code>{issue.path}</Text> : undefined}
                      />
                    ))}
                  </Space>
                )}
              </Card>
            </Space>
          ),
        },
      ]}
    />
  )
}
