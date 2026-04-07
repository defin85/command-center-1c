import { Alert, Button, Space, Typography } from 'antd'

import type { CommandSchemaDriver } from '../../api/commandSchemas'
import { EntityDetails, MasterDetailShell, PageHeader, WorkspacePage } from '../../components/platform'
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
    <WorkspacePage
      header={(
        <PageHeader
          title="Command Schemas"
          subtitle="Command schema workspace с route-addressable driver, mode и selected command context."
          actions={(
            <Space wrap>
              {(['ibcmd', 'cli'] as CommandSchemaDriver[]).map((driver) => (
                <Button
                  key={driver}
                  type={model.activeDriver === driver ? 'primary' : 'default'}
                  onClick={() => model.requestDriverChange(driver)}
                >
                  {driver.toUpperCase()}
                </Button>
              ))}
            </Space>
          )}
        />
      )}
    >
      <div data-testid="command-schemas-page">
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <CommandSchemasHeader
            hideTitle
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

          {model.view && (
            <CommandSchemasVersionsAlert view={model.view} />
          )}

          {model.mode === 'guided' ? (
            <>
              <MasterDetailShell
                list={(
                  <EntityDetails title={`Commands (${model.commands.length})`}>
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
                  </EntityDetails>
                )}
                detail={(
                  <EntityDetails
                    title={model.selectedCommandId
                      ? `Editor: ${displayCommandId(model.activeDriver, model.selectedCommandId)}`
                      : 'Editor'}
                    empty={!model.selectedCommandId}
                    emptyDescription="Select a command from the list to open inspect/editor flow."
                  >
                    <Space direction="vertical" size="large" style={{ width: '100%' }}>
                      <CommandSchemasEditorTabs model={model} />
                      <EntityDetails title="Preview / Diff / Validate">
                        <CommandSchemasSidePanel model={model} />
                      </EntityDetails>
                    </Space>
                  </EntityDetails>
                )}
                detailOpen={Boolean(model.selectedCommandId)}
                onCloseDetail={() => model.selectCommand('')}
                detailDrawerTitle={model.selectedCommandId
                  ? `Editor: ${displayCommandId(model.activeDriver, model.selectedCommandId)}`
                  : 'Editor'}
                listMinWidth={320}
                listMaxWidth={380}
              />

              <CommandSchemasSaveModal model={model} />
            </>
          ) : (
            <EntityDetails title={`Raw editor: ${model.activeDriver.toUpperCase()}`}>
              <CommandSchemasRawEditor
                driver={model.activeDriver}
                view={model.view}
                disabled={model.loading || model.importingIts || model.rollbackLoading || model.rollingBack}
                onReload={model.fetchView}
                onDirtyChange={model.setRawDirty}
              />
            </EntityDetails>
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
    </WorkspacePage>
  )
}
