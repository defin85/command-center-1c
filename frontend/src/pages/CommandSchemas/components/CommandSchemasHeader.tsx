import { Button, Space, Switch, Typography } from 'antd'
import { ReloadOutlined, RollbackOutlined, SaveOutlined, UploadOutlined } from '@ant-design/icons'
import { useAdminSupportTranslation } from '@/i18n'

import type { CommandSchemasMode } from '../model/types'

const { Title, Text } = Typography

export function CommandSchemasHeader(props: {
  hideTitle?: boolean
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
  const { t } = useAdminSupportTranslation()

  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
      {props.hideTitle ? <div /> : (
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>{t(($) => $.commandSchemas.header.title)}</Title>
          <Text type="secondary">{t(($) => $.commandSchemas.header.subtitle)}</Text>
        </div>
      )}
      <Space wrap>
        <Space size="small" align="center">
          <Text type="secondary">{t(($) => $.commandSchemas.header.modeLabel)}</Text>
          <Switch
            checked={props.mode === 'raw'}
            onChange={(checked) => props.setMode(checked ? 'raw' : 'guided')}
            checkedChildren={t(($) => $.commandSchemas.header.raw)}
            unCheckedChildren={t(($) => $.commandSchemas.header.guided)}
            disabled={props.loading}
          />
        </Space>
        <Button data-testid="command-schemas-refresh" onClick={props.onRefresh} loading={props.loading} icon={<ReloadOutlined />}>
          {t(($) => $.commandSchemas.header.refresh)}
        </Button>
        <Button
          data-testid="command-schemas-import-its-open"
          onClick={props.onOpenImportIts}
          disabled={props.loading || props.saving || props.rollingBack || props.rollbackLoading}
          icon={<UploadOutlined />}
        >
          {t(($) => $.commandSchemas.header.importIts)}
        </Button>
        <Button
          data-testid="command-schemas-rollback-open"
          onClick={() => { void props.onOpenRollback() }}
          disabled={!props.viewLoaded}
          icon={<RollbackOutlined />}
        >
          {t(($) => $.commandSchemas.header.rollback)}
        </Button>
        <Button
          data-testid="command-schemas-promote-open"
          onClick={props.onOpenPromote}
          disabled={!props.viewLoaded || !props.canPromoteLatest || props.loading || props.saving || props.rollingBack || props.rollbackLoading || props.importingIts || props.promoting}
        >
          {t(($) => $.commandSchemas.header.promoteLatest)}
        </Button>
        {props.mode === 'guided' && (
          <Button
            data-testid="command-schemas-save-open"
            type="primary"
            icon={<SaveOutlined />}
            onClick={props.onOpenSave}
            disabled={!props.viewLoaded || !props.dirty || props.saving}
          >
            {t(($) => $.commandSchemas.header.save)}
          </Button>
        )}
      </Space>
    </div>
  )
}
