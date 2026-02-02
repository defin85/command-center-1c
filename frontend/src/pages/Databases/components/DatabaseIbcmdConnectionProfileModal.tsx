import { Button, Divider, Form, Input, InputNumber, Modal, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'

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

  return (
    <Modal
      title={database ? `IBCMD connection profile: ${database.name}` : 'IBCMD connection profile'}
      open={open}
      onCancel={onCancel}
      width={720}
      footer={[
        <Button key="reset" danger onClick={onReset} disabled={disableReset}>
          Reset
        </Button>,
        <Button key="cancel" onClick={onCancel}>
          Cancel
        </Button>,
        <Button key="save" type="primary" onClick={onSave} loading={saving}>
          Save
        </Button>,
      ]}
    >
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

        <Divider />
        <Typography.Title level={5} style={{ marginTop: 0 }}>offline</Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          Любые offline.* ключи из driver schema. Они будут прокинуты как флаги вида <Typography.Text code>--key=value</Typography.Text>
          (snake_case преобразуется в kebab-case). Ключи <Typography.Text code>db_user</Typography.Text>,{' '}
          <Typography.Text code>db_pwd</Typography.Text>, <Typography.Text code>db_password</Typography.Text> запрещены.
        </Typography.Paragraph>

        <Form.List name="offline_entries">
          {(fields, { add, remove }) => (
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {fields.map((field) => (
                <Space key={field.key} align="baseline" style={{ width: '100%' }}>
                  <Form.Item
                    name={[field.name, 'key']}
                    rules={[{ required: true, message: 'key обязателен' }]}
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
              <Button type="dashed" onClick={() => add({ key: '', value: '' })}>
                Add offline flag
              </Button>
            </Space>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}
