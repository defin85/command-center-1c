import { Alert, Card, Space, Tabs, Typography } from 'antd'

import type { CommandSchemaDriver } from '../../api/commandSchemas'
import { CommandSchemasRawEditor } from './CommandSchemasRawEditor'
import { displayCommandId } from './commandSchemasUtils'
import { CommandSchemasCommandList } from './components/CommandSchemasCommandList'
import { CommandSchemasEditorTabs } from './components/CommandSchemasEditorTabs'
import { CommandSchemasHeader } from './components/CommandSchemasHeader'
import { CommandSchemasSidePanel } from './components/CommandSchemasSidePanel'
import { CommandSchemasUnsavedBanner } from './components/CommandSchemasUnsavedBanner'
import { CommandSchemasVersionsAlert } from './components/CommandSchemasVersionsAlert'
import { CommandSchemasImportItsModal } from './components/modals/CommandSchemasImportItsModal'
import { CommandSchemasPromoteModal } from './components/modals/CommandSchemasPromoteModal'
import { CommandSchemasRollbackModal } from './components/modals/CommandSchemasRollbackModal'
import { CommandSchemasSaveModal } from './components/modals/CommandSchemasSaveModal'
import type { CommandSchemasPageModel } from './useCommandSchemasPageModel'

const { Text } = Typography

export function CommandSchemasPageView(props: { model: CommandSchemasPageModel }) {
  const model = props.model

  return (
    <div data-testid="command-schemas-page">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <CommandSchemasHeader
          mode={model.mode}
          setMode={model.setMode}
          loading={model.loading}
          viewLoaded={Boolean(model.view)}
          dirty={model.dirty}
          saving={model.saving}
          rollbackLoading={model.rollbackLoading}
          rollingBack={model.rollingBack}
          importingIts={model.importingIts}
          promoting={model.promoting}
          canPromoteLatest={model.canPromoteLatest}
          onRefresh={model.requestRefreshView}
          onOpenImportIts={model.openImportIts}
          onOpenRollback={model.openRollback}
          onOpenPromote={model.openPromote}
          onOpenSave={model.openSave}
        />

        {model.mode === 'guided' && model.dirty && (
          <CommandSchemasUnsavedBanner
            overridesCounts={model.overridesCounts}
            saving={model.saving}
            onDiscard={model.discardChanges}
            onSave={model.openSave}
          />
        )}

        {model.error && (
          <Alert type="warning" message="Failed to load command schemas" description={model.error} showIcon />
        )}

        <Tabs
          activeKey={model.activeDriver}
          onChange={(key) => model.requestDriverChange(key as CommandSchemaDriver)}
          items={[
            { key: 'ibcmd', label: 'IBCMD' },
            { key: 'cli', label: 'CLI' },
          ]}
        />

        {model.view && (
          <CommandSchemasVersionsAlert view={model.view} />
        )}

        {model.mode === 'guided' ? (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '360px minmax(560px, 1fr) 420px',
                gap: 16,
                alignItems: 'start',
              }}
            >
              <Card size="small" title="Commands">
                <CommandSchemasCommandList
                  search={model.search}
                  setSearch={model.setSearch}
                  riskFilter={model.riskFilter}
                  setRiskFilter={model.setRiskFilter}
                  scopeFilter={model.scopeFilter}
                  setScopeFilter={model.setScopeFilter}
                  onlyModified={model.onlyModified}
                  setOnlyModified={model.setOnlyModified}
                  hideDisabled={model.hideDisabled}
                  setHideDisabled={model.setHideDisabled}
                  commandsCount={model.commands.length}
                  groupedCommands={model.groupedCommands}
                  selectedCommandId={model.selectedCommandId}
                  onSelectCommand={model.selectCommand}
                />
              </Card>

              <Card
                size="small"
                title={model.selectedCommandId ? `Editor: ${displayCommandId(model.activeDriver, model.selectedCommandId)}` : 'Editor'}
              >
                <CommandSchemasEditorTabs model={model} />
              </Card>

              <Card size="small" title="Preview / Diff / Validate">
                <CommandSchemasSidePanel model={model} />
              </Card>
            </div>

            <CommandSchemasSaveModal model={model} />
          </>
        ) : (
          <CommandSchemasRawEditor
            driver={model.activeDriver}
            view={model.view}
            disabled={model.loading || model.importingIts || model.rollbackLoading || model.rollingBack}
            onReload={model.fetchView}
            onDirtyChange={model.setRawDirty}
          />
        )}

        <CommandSchemasImportItsModal model={model} />
        <CommandSchemasRollbackModal model={model} />
        <CommandSchemasPromoteModal model={model} />

        {model.mode === 'raw' && model.view && model.canPromoteLatest && (
          <Text type="secondary">
            Note: base latest differs from approved. Switch to Guided mode to edit overrides against approved base.
          </Text>
        )}
      </Space>
    </div>
  )
}

