import { Button, Form, Input, InputNumber, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'
import { useMemo, useState } from 'react'

import type { Database } from '../../../api/generated/model/database'
import { useDriverCommands } from '../../../api/queries/driverCommands'
import { ModalFormShell } from '../../../components/platform'

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
      title={database ? `IBCMD connection profile: ${database.name}` : 'IBCMD connection profile'}
      subtitle="Database-scoped ibcmd runtime profile"
      submitText="Save"
      confirmLoading={saving}
      width={720}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button danger onClick={onReset} disabled={disableReset}>
            Reset
          </Button>
        </Space>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          Профиль хранится на уровне базы и используется по умолчанию для запусков ibcmd. Это raw flags: система не
          пытается интерпретировать режимы, а пользователь отвечает за корректные комбинации. Секреты здесь не задаются.
        </Typography.Paragraph>

        <Form form={form} layout="vertical">
          <Form.Item
            label="remote (SSH URL)"
            name="remote"
            htmlFor="database-ibcmd-profile-remote"
            rules={[
              {
                validator: async (_, value) => {
                  const v = typeof value === 'string' ? value.trim() : ''
                  if (!v) return
                  if (!v.toLowerCase().startsWith('ssh://')) {
                    throw new Error('remote должен начинаться с ssh://')
                  }
                },
              },
            ]}
          >
            <Input id="database-ibcmd-profile-remote" placeholder="ssh://host:port" />
          </Form.Item>

          <Form.Item label="pid" name="pid" htmlFor="database-ibcmd-profile-pid">
            <InputNumber id="database-ibcmd-profile-pid" min={1} style={{ width: '100%' }} placeholder="12345" />
          </Form.Item>

          <div
            aria-hidden
            style={{
              borderTop: '1px solid #e5e7eb',
              margin: '8px 0 0',
              width: '100%',
            }}
          />
          <Typography.Title level={5} style={{ marginTop: 0 }}>offline</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
            Любые offline.* ключи из driver schema. Они будут прокинуты как флаги вида <Typography.Text code>--key=value</Typography.Text>
            (snake_case преобразуется в kebab-case). Ключи <Typography.Text code>db_user</Typography.Text>,{' '}
            <Typography.Text code>db_pwd</Typography.Text>, <Typography.Text code>db_password</Typography.Text> запрещены.
          </Typography.Paragraph>

          <Form.List name="offline_entries">
            {(fields, { add, remove }) => (
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Form.Item label="Добавить offline флаг (из схемы)" style={{ marginBottom: 0 }}>
                  <Space.Compact style={{ width: '100%' }}>
                    <Input
                      data-testid="ibcmd-profile-offline-schema-input"
                      placeholder={offlineSchemaKeys.length > 0 ? 'например db_name' : 'Схема не загружена'}
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
                      Add
                    </Button>
                  </Space.Compact>
                </Form.Item>

                {fields.map((field) => (
                  <Space key={field.key} align="baseline" style={{ width: '100%' }}>
                    <Form.Item
                      name={[field.name, 'key']}
                      rules={[
                        { required: true, message: 'key обязателен' },
                        {
                          validator: async (_, value) => {
                            const v = typeof value === 'string' ? value.trim() : ''
                            if (!v) return
                            if (v.startsWith('-')) {
                              throw new Error('key задаётся без префикса -- (например db_name, а не --db-name)')
                            }
                            const lowered = v.toLowerCase()
                            if (lowered === 'db_user' || lowered === 'db_pwd' || lowered === 'db_password') {
                              throw new Error('секретные ключи запрещены (db_user/db_pwd/db_password)')
                            }
                          },
                        },
                      ]}
                      style={{ marginBottom: 0, flex: 1 }}
                    >
                      <Input placeholder="config" />
                    </Form.Item>
                    <Form.Item
                      name={[field.name, 'value']}
                      rules={[{ required: true, message: 'value обязателен' }]}
                      style={{ marginBottom: 0, flex: 2 }}
                    >
                      <Input placeholder="/path/to/value" />
                    </Form.Item>
                    <Button danger onClick={() => remove(field.name)}>
                      Remove
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
