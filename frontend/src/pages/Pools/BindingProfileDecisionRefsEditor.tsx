import { Button, Form, Input, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'

import { EntityDetails } from '../../components/platform'
import type { AvailableDecisionRevision } from '../../types/workflow'
import { DecisionRevisionSelect } from '../../components/workflow/DecisionRevisionSelect'
import { usePoolsTranslation } from '../../i18n'
import type { BindingProfileEditorFormValues } from './poolBindingProfilesForm'

const { Text } = Typography

type BindingProfileDecisionRefsEditorProps = {
  form: FormInstance<BindingProfileEditorFormValues>
  availableDecisions: AvailableDecisionRevision[]
  decisionsLoading: boolean
  disabled: boolean
  mode: 'create' | 'revise'
}

export function BindingProfileDecisionRefsEditor({
  form,
  availableDecisions,
  decisionsLoading,
  disabled,
  mode,
}: BindingProfileDecisionRefsEditorProps) {
  const { t } = usePoolsTranslation()
  const decisionValues = Form.useWatch('decisions', form) ?? []

  return (
    <EntityDetails title={t('executionPacks.decisionRefs.title')}>
      <Form.List name="decisions">
        {(decisionFields, decisionActions) => (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {decisionFields.length === 0 ? (
              <Text type="secondary">
                {t('executionPacks.decisionRefs.emptyDescription')}
              </Text>
            ) : null}
            {decisionFields.map((decisionField) => {
              const currentDecision = decisionValues[decisionField.name] ?? {}
              const decisionTableId = String(currentDecision.decision_table_id ?? '').trim()
              const decisionKey = String(currentDecision.decision_key ?? '').trim()
              const slotKey = String(currentDecision.slot_key ?? '').trim()
              const decisionRevisionRaw = Number(currentDecision.decision_revision ?? 0)
              return (
                <div
                  key={decisionField.key}
                  data-testid={`pool-binding-profiles-${mode}-slot-row-${decisionField.name}`}
                  style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}
                >
                  <div
                    data-testid={`pool-binding-profiles-${mode}-slot-controls-${decisionField.name}`}
                    style={{
                      alignItems: 'flex-start',
                      columnGap: 16,
                      display: 'flex',
                      flexWrap: 'wrap',
                      rowGap: 8,
                      width: '100%',
                    }}
                  >
                    <div style={{ flex: '1 1 180px', minWidth: 180 }}>
                      <Form.Item
                        name={[decisionField.name, 'slot_key']}
                        label={decisionField.name === 0 ? t('executionPacks.decisionRefs.slotKey') : undefined}
                        rules={[{ required: true, message: t('executionPacks.decisionRefs.validation.slotKeyRequired') }]}
                        style={{ marginBottom: 0 }}
                      >
                        <Input
                          disabled={disabled}
                          placeholder={t('executionPacks.decisionRefs.slotKeyPlaceholder')}
                          data-testid={`pool-binding-profiles-${mode}-slot-key-${decisionField.name}`}
                        />
                      </Form.Item>
                    </div>

                    <div style={{ flex: '2 1 320px', minWidth: 240 }}>
                      <Form.Item
                        label={decisionField.name === 0 ? t('executionPacks.decisionRefs.pinnedDecisionRevision') : undefined}
                        style={{ marginBottom: 0 }}
                        help={decisionField.name === 0 ? t('executionPacks.decisionRefs.pinnedDecisionRevisionHelp') : undefined}
                      >
                        <DecisionRevisionSelect
                          allowClear
                          disabled={disabled}
                          loading={decisionsLoading}
                          availableDecisions={availableDecisions}
                          currentDecision={(
                            decisionTableId && decisionKey && decisionRevisionRaw > 0
                              ? {
                                  decision_table_id: decisionTableId,
                                  decision_key: decisionKey,
                                  decision_revision: decisionRevisionRaw,
                                }
                              : undefined
                          )}
                          placeholder={t('executionPacks.decisionRefs.decisionRevisionPlaceholder')}
                          testId={`pool-binding-profiles-${mode}-decision-select-${decisionField.name}`}
                          onChange={(selected) => {
                            form.setFieldValue(['decisions', decisionField.name, 'decision_table_id'], selected?.decision_table_id ?? '')
                            form.setFieldValue(['decisions', decisionField.name, 'decision_key'], selected?.decision_key ?? '')
                            form.setFieldValue(['decisions', decisionField.name, 'decision_revision'], selected?.decision_revision ?? null)
                          }}
                        />
                        <Form.Item
                          name={[decisionField.name, 'decision_revision']}
                          rules={[{ required: true, message: t('executionPacks.decisionRefs.validation.decisionRevisionRequired') }]}
                          hidden
                        >
                          <Input />
                        </Form.Item>
                        <Form.Item name={[decisionField.name, 'decision_table_id']} hidden>
                          <Input />
                        </Form.Item>
                        <Form.Item name={[decisionField.name, 'decision_key']} hidden>
                          <Input />
                        </Form.Item>
                      </Form.Item>
                    </div>

                    <div style={{ flex: '0 0 auto' }}>
                      <div style={{ paddingTop: decisionField.name === 0 ? 30 : 0 }}>
                        <Button
                          danger
                          onClick={() => decisionActions.remove(decisionField.name)}
                          disabled={disabled}
                          data-testid={`pool-binding-profiles-${mode}-remove-slot-${decisionField.name}`}
                        >
                          {t('common.remove')}
                        </Button>
                      </div>
                    </div>
                  </div>

                  {decisionTableId ? (
                    <Text type="secondary" data-testid={`pool-binding-profiles-${mode}-slot-ref-${decisionField.name}`}>
                      {t('executionPacks.decisionRefs.slotSummary', {
                        tableId: decisionTableId,
                        decisionKey,
                        revision: decisionRevisionRaw || '—',
                        slotSuffix: slotKey
                          ? t('executionPacks.decisionRefs.slotSuffix', { value: slotKey })
                          : '',
                      })}
                    </Text>
                  ) : null}
                </div>
              )
            })}

            <Button
              onClick={() => decisionActions.add({
                decision_table_id: '',
                decision_key: '',
                slot_key: '',
                decision_revision: null,
              })}
              disabled={disabled}
              data-testid={`pool-binding-profiles-${mode}-add-slot`}
            >
              {t('executionPacks.decisionRefs.addSlot')}
            </Button>
          </Space>
        )}
      </Form.List>
    </EntityDetails>
  )
}
