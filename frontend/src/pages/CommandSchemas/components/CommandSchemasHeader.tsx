import { Button, Space, Switch, Typography } from 'antd'
import { ReloadOutlined, RollbackOutlined, SaveOutlined, UploadOutlined } from '@ant-design/icons'

import type { CommandSchemasMode } from '../model/types'

const { Title, Text } = Typography

export function CommandSchemasHeader(props: {
  mode: CommandSchemasMode
  setMode: (value: CommandSchemasMode) => void
  loading: boolean
  viewLoaded: boolean
  dirty: boolean

  saving: boolean
  rollbackLoading: boolean
  rollingBack: boolean
  importingIts: boolean
  promoting: boolean
  canPromoteLatest: boolean

  onRefresh: () => void
  onOpenImportIts: () => void
  onOpenRollback: () => void | Promise<void>
  onOpenPromote: () => void
  onOpenSave: () => void
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
      <div>
        <Title level={2} style={{ marginBottom: 0 }}>Command Schemas</Title>
        <Text type="secondary">Human-oriented editor for driver command schemas (MinIO artifacts).</Text>
      </div>
      <Space wrap>
        <Space size="small" align="center">
          <Text type="secondary">Mode</Text>
          <Switch
            checked={props.mode === 'raw'}
            onChange={(checked) => props.setMode(checked ? 'raw' : 'guided')}
            checkedChildren="Raw"
            unCheckedChildren="Guided"
            disabled={props.loading}
          />
        </Space>
        <Button data-testid="command-schemas-refresh" onClick={props.onRefresh} loading={props.loading} icon={<ReloadOutlined />}>
          Refresh
        </Button>
        <Button
          data-testid="command-schemas-import-its-open"
          onClick={props.onOpenImportIts}
          disabled={props.loading || props.saving || props.rollingBack || props.rollbackLoading}
          icon={<UploadOutlined />}
        >
          Import ITS...
        </Button>
        <Button
          data-testid="command-schemas-rollback-open"
          onClick={() => { void props.onOpenRollback() }}
          disabled={!props.viewLoaded}
          icon={<RollbackOutlined />}
        >
          Rollback...
        </Button>
        <Button
          data-testid="command-schemas-promote-open"
          onClick={props.onOpenPromote}
          disabled={!props.viewLoaded || !props.canPromoteLatest || props.loading || props.saving || props.rollingBack || props.rollbackLoading || props.importingIts || props.promoting}
        >
          Promote latest...
        </Button>
        {props.mode === 'guided' && (
          <Button
            data-testid="command-schemas-save-open"
            type="primary"
            icon={<SaveOutlined />}
            onClick={props.onOpenSave}
            disabled={!props.viewLoaded || !props.dirty || props.saving}
          >
            Save...
          </Button>
        )}
      </Space>
    </div>
  )
}
