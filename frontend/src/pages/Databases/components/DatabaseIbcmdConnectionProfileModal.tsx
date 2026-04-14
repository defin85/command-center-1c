import { Button, Form, Input, InputNumber, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'
import { useMemo, useState } from 'react'

import type { Database } from '../../../api/generated/model/database'
import { useDriverCommands } from '../../../api/queries/driverCommands'
import { ModalFormShell } from '../../../components/platform'
import { useDatabasesTranslation } from '../../../i18n'

export type DatabaseIbcmdConnectionProfileModalProps = {
  open: boolean
  database: Database | null
  form: FormInstance
  saving: boolean
  onCancel: () => void
  onSave: () => void
  onReset: () => void
}

export function DatabaseIbcmdConnectionProfileModal({
  open,
  database,
  form,
  saving,
  onCancel,
  onSave,
  onReset,
}: DatabaseIbcmdConnectionProfileModalProps) {
  const { t } = useDatabasesTranslation()
  const dbAny = (database ?? null) as (Database & { ibcmd_connection?: unknown }) | null
  const disableReset = !dbAny?.ibcmd_connection

  const driverCommandsQuery = useDriverCommands('ibcmd', open)
  const [schemaKeyDraft, setSchemaKeyDraft] = useState('')

  const offlineSchemaKeys = useMemo(() => {
    const isRecord = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
    const schema = driverCommandsQuery.data?.catalog?.driver_schema
    if (!isRecord(schema)) return []
    const connection = schema.connection
    if (!isRecord(connection)) return []
    const offline = connection.offline
    if (!isRecord(offline)) return []

    const forbidden = new Set(['db_user', 'db_pwd', 'db_password'])
    return Object.keys(offline)
      .map((k) => String(k).trim())
      .filter((k) => !!k)
      .filter((k) => !forbidden.has(k.toLowerCase()))
      .sort((a, b) => a.localeCompare(b))
  }, [driverCommandsQuery.data])

  return (
    <ModalFormShell
      open={open}
      onClose={onCancel}
      onSubmit={onSave}
      title={database
        ? t(($) => $.modals.ibcmd.titleWithName, { name: database.name })
        : t(($) => $.modals.ibcmd.title)}
      subtitle={t(($) => $.modals.ibcmd.subtitle)}
      submitText={t(($) => $.modals.ibcmd.save)}
      confirmLoading={saving}
      width={720}
      forceRender
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onReset} disabled={disableReset}>
            {t(($) => $.modals.ibcmd.reset)}
          </Button>
        </Space>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          {t(($) => $.modals.ibcmd.description)}
        </Typography.Paragraph>

        <Form form={form} layout="vertical">
          <Form.Item
            label={t(($) => $.modals.ibcmd.remoteLabel)}
            name="remote"
            htmlFor="database-ibcmd-profile-remote"
            rules={[
              {
                validator: async (_, value) => {
                  const v = typeof value === 'string' ? value.trim() : ''
                  if (!v) return
                  if (!v.toLowerCase().startsWith('ssh://')) {
                    throw new Error(t(($) => $.modals.ibcmd.remoteInvalid))
                  }
                },
              },
            ]}
          >
            <Input id="database-ibcmd-profile-remote" placeholder={t(($) => $.modals.ibcmd.remotePlaceholder)} />
          </Form.Item>

          <Form.Item label={t(($) => $.modals.ibcmd.pidLabel)} name="pid" htmlFor="database-ibcmd-profile-pid">
            <InputNumber id="database-ibcmd-profile-pid" min={1} style={{ width: '100%' }} placeholder={t(($) => $.modals.ibcmd.pidPlaceholder)} />
          </Form.Item>

          <div
            aria-hidden
            style={{
              borderTop: '1px solid #e5e7eb',
              margin: '8px 0 0',
              width: '100%',
            }}
          />
          <Typography.Title level={5} style={{ marginTop: 0 }}>{t(($) => $.modals.ibcmd.offlineTitle)}</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
            {t(($) => $.modals.ibcmd.offlineDescription)}
          </Typography.Paragraph>

          <Form.List name="offline_entries">
            {(fields, { add, remove }) => (
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Form.Item label={t(($) => $.modals.ibcmd.addSchemaKeyLabel)} style={{ marginBottom: 0 }}>
                  <Space.Compact style={{ width: '100%' }}>
                    <Input
                      data-testid="ibcmd-profile-offline-schema-input"
                      placeholder={offlineSchemaKeys.length > 0
                        ? t(($) => $.modals.ibcmd.addSchemaKeyPlaceholderLoaded)
                        : t(($) => $.modals.ibcmd.addSchemaKeyPlaceholderEmpty)}
                      disabled={offlineSchemaKeys.length === 0}
                      value={schemaKeyDraft}
                      list="ibcmd-offline-schema-keys"
                      onChange={(e) => setSchemaKeyDraft(e.target.value)}
                    />
                    <datalist id="ibcmd-offline-schema-keys">
                      {offlineSchemaKeys.map((k) => (
                        <option key={k} value={k} />
                      ))}
                    </datalist>
                    <Button
                      disabled={!schemaKeyDraft.trim()}
                      onClick={() => {
                        const key = schemaKeyDraft.trim()
                        if (!key) return
                        const entries = form.getFieldValue('offline_entries')
                        const rows = Array.isArray(entries) ? (entries as unknown[]) : []
                        const has = rows.some(
                          (r) => !!r && typeof r === 'object' && String((r as Record<string, unknown>).key || '').trim() === key
                        )
                        if (!has) add({ key, value: '' })
                        setSchemaKeyDraft('')
                      }}
                    >
                      {t(($) => $.modals.ibcmd.add)}
                    </Button>
                  </Space.Compact>
                </Form.Item>

                {fields.map((field) => (
                  <Space key={field.key} align="baseline" style={{ width: '100%' }}>
                    <Form.Item
                      name={[field.name, 'key']}
                      rules={[
                        { required: true, message: t(($) => $.modals.ibcmd.keyRequired) },
                        {
                          validator: async (_, value) => {
                            const v = typeof value === 'string' ? value.trim() : ''
                            if (!v) return
                            if (v.startsWith('-')) {
                              throw new Error(t(($) => $.modals.ibcmd.keyNoPrefix))
                            }
                            const lowered = v.toLowerCase()
                            if (lowered === 'db_user' || lowered === 'db_pwd' || lowered === 'db_password') {
                              throw new Error(t(($) => $.modals.ibcmd.keySecretsForbidden))
                            }
                          },
                        },
                      ]}
                      style={{ marginBottom: 0, flex: 1 }}
                    >
                      <Input placeholder={t(($) => $.modals.ibcmd.keyPlaceholder)} />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, 'value']}
                      rules={[{ required: true, message: t(($) => $.modals.ibcmd.valueRequired) }]}
                      style={{ marginBottom: 0, flex: 2 }}
                    >
                      <Input placeholder={t(($) => $.modals.ibcmd.valuePlaceholder)} />
                    </Form.Item>
                    <Button danger onClick={() => remove(field.name)}>
                      {t(($) => $.modals.ibcmd.remove)}
                    </Button>
                  </Space>
                ))}
              </Space>
            )}
          </Form.List>
        </Form>
      </Space>
    </ModalFormShell>
  )
}
