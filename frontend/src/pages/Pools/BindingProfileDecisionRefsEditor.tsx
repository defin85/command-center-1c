import { Button, Form, Input, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'

import { EntityDetails } from '../../components/platform'
import type { AvailableDecisionRevision } from '../../types/workflow'
import { DecisionRevisionSelect } from '../../components/workflow/DecisionRevisionSelect'
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
  const decisionValues = Form.useWatch('decisions', form) ?? []

  return (
    <EntityDetails title="Publication slots">
      <Form.List name="decisions">
        {(decisionFields, decisionActions) => (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {decisionFields.length === 0 ? (
              <Text type="secondary">
                No publication slots pinned yet. Add a slot and pick a decision revision from `/decisions`.
              </Text>
            ) : null}
            {decisionFields.map((decisionField) => {
              const currentDecision = decisionValues[decisionField.name] ?? {}
              const decisionTableId = String(currentDecision.decision_table_id ?? '').trim()
              const decisionKey = String(currentDecision.decision_key ?? '').trim()
              const slotKey = String(currentDecision.slot_key ?? '').trim()
              const decisionRevisionRaw = Number(currentDecision.decision_revision ?? 0)
              return (
                <Space
                  key={decisionField.key}
                  align="start"
                  size="middle"
                  style={{ display: 'flex', width: '100%' }}
                >
                  <Form.Item
                    name={[decisionField.name, 'slot_key']}
                    label={decisionField.name === 0 ? 'Slot key' : undefined}
                    rules={[{ required: true, message: 'Slot key is required.' }]}
                    style={{ flex: '0 0 180px', marginBottom: 0 }}
                  >
                    <Input
                      disabled={disabled}
                      placeholder="sale, purchase, return"
                      data-testid={`pool-binding-profiles-${mode}-slot-key-${decisionField.name}`}
                    />
                  </Form.Item>

                  <Form.Item
                    label={decisionField.name === 0 ? 'Pinned decision revision' : undefined}
                    style={{ flex: 1, marginBottom: 0 }}
                    help={decisionField.name === 0 ? 'Select decision revision from /decisions. Slot key remains binding-profile-local.' : undefined}
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
                      placeholder="Select decision revision from /decisions"
                      testId={`pool-binding-profiles-${mode}-decision-select-${decisionField.name}`}
                      onChange={(selected) => {
                        form.setFieldValue(['decisions', decisionField.name, 'decision_table_id'], selected?.decision_table_id ?? '')
                        form.setFieldValue(['decisions', decisionField.name, 'decision_key'], selected?.decision_key ?? '')
                        form.setFieldValue(['decisions', decisionField.name, 'decision_revision'], selected?.decision_revision ?? null)
                      }}
                    />
                    <Form.Item
                      name={[decisionField.name, 'decision_revision']}
                      rules={[{ required: true, message: 'Decision revision is required.' }]}
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

                  <Button
                    danger
                    onClick={() => decisionActions.remove(decisionField.name)}
                    disabled={disabled}
                    data-testid={`pool-binding-profiles-${mode}-remove-slot-${decisionField.name}`}
                  >
                    Remove
                  </Button>

                  {decisionTableId ? (
                    <Text type="secondary" data-testid={`pool-binding-profiles-${mode}-slot-ref-${decisionField.name}`}>
                      {decisionTableId} ({decisionKey}) · r{decisionRevisionRaw || '—'}
                      {slotKey ? ` · slot ${slotKey}` : ''}
                    </Text>
                  ) : null}
                </Space>
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
              Add slot
            </Button>
          </Space>
        )}
      </Form.List>
    </EntityDetails>
  )
}
