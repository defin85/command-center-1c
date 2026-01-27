import { Divider, Form, Input, InputNumber, Typography } from 'antd'

import type { IbcmdCliConnection, IbcmdCliConnectionOffline } from './types'

const { Text } = Typography

export function IbcmdConnectionForm({
  connection,
  onChange,
  readOnly,
}: {
  connection: IbcmdCliConnection
  onChange: (next: IbcmdCliConnection) => void
  readOnly?: boolean
}) {
  const offline = connection.offline ?? {}

  const update = (updates: Partial<IbcmdCliConnection>) => {
    onChange({ ...connection, ...updates })
  }

  const updateOffline = (updates: Partial<IbcmdCliConnectionOffline>) => {
    update({ offline: { ...offline, ...updates } })
  }

  return (
    <Form layout="vertical">
      <Form.Item label="Remote (optional)" style={{ marginBottom: 12 }}>
        <Input
          value={connection.remote || ''}
          disabled={readOnly}
          placeholder="http://host:port"
          onChange={(event) => update({ remote: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="PID (optional)" style={{ marginBottom: 12 }}>
        <InputNumber
          style={{ width: '100%' }}
          value={typeof connection.pid === 'number' ? connection.pid : undefined}
          disabled={readOnly}
          onChange={(value) => update({ pid: typeof value === 'number' ? value : null })}
        />
      </Form.Item>

      <Divider style={{ margin: '8px 0 16px' }} />
      <Text strong>Offline (optional)</Text>

      <Form.Item label="Config path" style={{ marginBottom: 12 }}>
        <Input
          value={offline.config || ''}
          disabled={readOnly}
          placeholder="/path/to/config"
          onChange={(event) => updateOffline({ config: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="Data path" style={{ marginBottom: 12 }}>
        <Input
          value={offline.data || ''}
          disabled={readOnly}
          placeholder="/path/to/data"
          onChange={(event) => updateOffline({ data: event.target.value })}
        />
      </Form.Item>

      <Form.Item label="DBMS" style={{ marginBottom: 12 }}>
        <Input
          value={offline.dbms || ''}
          disabled={readOnly}
          placeholder="PostgreSQL"
          onChange={(event) => updateOffline({ dbms: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB server" style={{ marginBottom: 12 }}>
        <Input
          value={offline.db_server || ''}
          disabled={readOnly}
          placeholder="db-host:5432"
          onChange={(event) => updateOffline({ db_server: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB name" style={{ marginBottom: 12 }}>
        <Input
          value={offline.db_name || ''}
          disabled={readOnly}
          placeholder="infobase_db"
          onChange={(event) => updateOffline({ db_name: event.target.value })}
        />
      </Form.Item>
    </Form>
  )
}

