import { Button, Divider, Form, Input, Modal, Select, Typography } from 'antd'
import type { FormInstance } from 'antd'

import type { Database } from '../../../api/generated/model/database'
import type { DatabaseIbcmdConnectionMode } from '../../../api/queries/databases'

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
        Профиль хранится на уровне базы и используется по умолчанию для запусков ibcmd. Пароли здесь не задаются.
      </Typography.Paragraph>

      <Form form={form} layout="vertical">
        <Form.Item
          label="Mode"
          name="mode"
          htmlFor="database-ibcmd-profile-mode"
          rules={[{ required: true, message: 'Выберите режим' }]}
        >
          <Select
            id="database-ibcmd-profile-mode"
            options={[
              { label: 'Auto (prefer remote, fallback offline)', value: 'auto' satisfies DatabaseIbcmdConnectionMode },
              { label: 'Remote (--remote=<url>)', value: 'remote' satisfies DatabaseIbcmdConnectionMode },
              { label: 'Offline (paths + DBMS metadata)', value: 'offline' satisfies DatabaseIbcmdConnectionMode },
            ]}
          />
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.mode !== cur.mode}>
          {({ getFieldValue }) => {
            const mode = String(getFieldValue('mode') || 'auto').toLowerCase()
            return (
              <Form.Item
                label="Remote URL"
                name="remote_url"
                htmlFor="database-ibcmd-profile-remote-url"
                rules={[
                  {
                    required: mode === 'remote',
                    message: 'remote_url обязателен для mode=remote',
                  },
                ]}
              >
                <Input
                  id="database-ibcmd-profile-remote-url"
                  placeholder="e.g. http://127.0.0.1:1548"
                />
              </Form.Item>
            )
          }}
        </Form.Item>

        <Divider />
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          Offline
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          Для offline режима обязательны <Typography.Text code>config</Typography.Text> и{' '}
          <Typography.Text code>data</Typography.Text>. DBMS metadata можно задать здесь или оставить пустым и использовать
          DBMS metadata базы как fallback.
        </Typography.Paragraph>

        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.mode !== cur.mode}>
          {({ getFieldValue }) => {
            const mode = String(getFieldValue('mode') || 'auto').toLowerCase()
            const requiredOffline = mode === 'offline'
            return (
              <>
                <Form.Item
                  label="offline.config"
                  name={['offline', 'config']}
                  htmlFor="database-ibcmd-profile-offline-config"
                  rules={[
                    {
                      required: requiredOffline,
                      message: 'offline.config обязателен для mode=offline',
                    },
                  ]}
                >
                  <Input id="database-ibcmd-profile-offline-config" placeholder="Path to config directory" />
                </Form.Item>
                <Form.Item
                  label="offline.data"
                  name={['offline', 'data']}
                  htmlFor="database-ibcmd-profile-offline-data"
                  rules={[
                    {
                      required: requiredOffline,
                      message: 'offline.data обязателен для mode=offline',
                    },
                  ]}
                >
                  <Input id="database-ibcmd-profile-offline-data" placeholder="Path to data directory" />
                </Form.Item>
              </>
            )
          }}
        </Form.Item>

        <Form.Item label="offline.db_path" name={['offline', 'db_path']} htmlFor="database-ibcmd-profile-offline-db-path">
          <Input id="database-ibcmd-profile-offline-db-path" placeholder="Path to file database (optional)" />
        </Form.Item>

        <Divider />
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          Offline DBMS metadata (optional)
        </Typography.Title>
        <Form.Item label="offline.dbms" name={['offline', 'dbms']} htmlFor="database-ibcmd-profile-offline-dbms">
          <Input id="database-ibcmd-profile-offline-dbms" placeholder="e.g. PostgreSQL" />
        </Form.Item>
        <Form.Item label="offline.db_server" name={['offline', 'db_server']} htmlFor="database-ibcmd-profile-offline-db-server">
          <Input id="database-ibcmd-profile-offline-db-server" placeholder="e.g. db.example.local" />
        </Form.Item>
        <Form.Item label="offline.db_name" name={['offline', 'db_name']} htmlFor="database-ibcmd-profile-offline-db-name">
          <Input id="database-ibcmd-profile-offline-db-name" placeholder="e.g. my_infobase" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

