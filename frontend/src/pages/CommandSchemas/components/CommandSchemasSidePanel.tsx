import { Alert, Button, Card, Input, Select, Space, Switch, Tabs, Tag, Typography } from 'antd'

import type { DriverCommandParamV2 } from '../../../api/driverCommands'
import { LazyJsonCodeEditor } from '../../../components/code/LazyJsonCodeEditor'
import { normalizeStringList, parseJsonObject, safeText } from '../commandSchemasUtils'
import type { CommandSchemasPageModel } from '../useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasSidePanel(props: { model: CommandSchemasPageModel }) {
  const model = props.model

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
          label: 'Preview',
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {!hasSelection && <Alert type="info" showIcon message="Select a command to preview" />}
              <Space wrap>
                <Select
                  value={model.previewMode}
                  onChange={(v) => model.setPreviewMode(v)}
                  style={{ width: 140 }}
                  options={[
                    { value: 'guided', label: 'guided' },
                    { value: 'manual', label: 'manual' },
                  ]}
                />
                <Button
                  onClick={() => { void model.buildPreview() }}
                  loading={model.previewLoading}
                  disabled={!hasSelection || (model.activeDriver === 'ibcmd' && Boolean(model.previewConnectionError))}
                >
                  Build argv
                </Button>
              </Space>

              {model.activeDriver === 'ibcmd' && (
                <Card size="small" title="Connection (ibcmd)">
                  <LazyJsonCodeEditor
                    value={model.previewConnectionText}
                    onChange={(nextText) => {
                      model.setPreviewConnectionText(nextText)
                      model.setPreviewConnectionError(parseJsonObject(nextText) ? null : 'Invalid JSON: expected a JSON object')
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
                <Card size="small" title="Params">
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
                            {isRequired && <Tag color="red">required</Tag>}
                            {isSensitive && <Tag color="orange">sensitive</Tag>}
                            {kind === 'flag' && safeText(schema.flag) && <Tag>{safeText(schema.flag)}</Tag>}
                            {kind === 'positional' && Number.isFinite(Number(schema.position)) && (
                              <Tag>pos {Number(schema.position)}</Tag>
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
                                placeholder="value"
                              />
                            ) : (
                              <Input
                                value={safeText(currentValue)}
                                onChange={(e) => setValue(e.target.value)}
                                placeholder="value"
                              />
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </Space>
                </Card>
              )}

              <Card size="small" title="Additional args (one per line)">
                <Input.TextArea
                  value={model.previewArgsText}
                  onChange={(e) => model.setPreviewArgsText(e.target.value)}
                  rows={4}
                  placeholder="--extra\n--flag=value"
                />
              </Card>

              {model.previewError && <Alert type="warning" showIcon message="Preview error" description={model.previewError} />}

              <Card size="small" title="argv">
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  {model.previewArgv.length === 0 ? (
                    <Text type="secondary">No preview yet</Text>
                  ) : (
                    model.previewArgv.map((line, idx) => <Text key={idx} code>{line}</Text>)
                  )}
                </Space>
              </Card>
              <Card size="small" title="argv_masked">
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  {model.previewArgvMasked.length === 0 ? (
                    <Text type="secondary">No preview yet</Text>
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
          label: 'Diff',
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {!hasSelection && <Alert type="info" showIcon message="Select a command to diff" />}
              <Button onClick={() => { void model.loadDiff() }} loading={model.diffLoading} disabled={!hasSelection}>
                Load diff (base to effective)
              </Button>
              {model.diffError && <Alert type="warning" showIcon message="Diff error" description={model.diffError} />}
              <div style={{ maxHeight: 620, overflow: 'auto' }}>
                <Card size="small" title={`Changes (${model.diffItems.length})`}>
                  {model.diffItems.length === 0 ? (
                    <Text type="secondary">No changes</Text>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Path</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Base</th>
                            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Effective</th>
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
          label: 'Validate',
          children: (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Button onClick={() => { void model.runValidate() }} loading={model.validateLoading}>
                Validate effective catalog
              </Button>
              {model.validateError && <Alert type="warning" showIcon message="Validation error" description={model.validateError} />}
              {model.validateSummary && (
                <Alert
                  type={model.validateSummary.ok ? 'success' : 'warning'}
                  showIcon
                  message={model.validateSummary.ok ? 'OK' : 'Validation failed'}
                  description={`errors=${model.validateSummary.errors}, warnings=${model.validateSummary.warnings}`}
                />
              )}
              <Card size="small" title={`Global issues (${model.globalIssues.length})`}>
                {model.globalIssues.length === 0 ? (
                  <Text type="secondary">No issues</Text>
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
              <Card size="small" title={`Issues for selected command (${model.issuesForSelected.length})`}>
                {!hasSelection ? (
                  <Text type="secondary">No command selected</Text>
                ) : model.issuesForSelected.length === 0 ? (
                  <Text type="secondary">No issues</Text>
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

