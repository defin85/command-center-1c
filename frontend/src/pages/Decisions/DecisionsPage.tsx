import { EditOutlined, ImportOutlined, MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  App,
  Button,
  Collapse,
  Select,
  Space,
  Typography,
} from 'antd'
import type { PoolODataMetadataCatalogDocument } from '../../api/generated/model'

import {
  DrawerFormShell,
  EntityDetails,
  MasterDetailShell,
  PageHeader,
  RouteButton,
  WorkspacePage,
} from '../../components/platform'
import { useDecisionsTranslation } from '../../i18n'
import {
  DecisionLegacyImportPanel,
} from './DecisionLegacyImportPanel'
import {
  DecisionEditorPanel,
  type DecisionEditorMode,
  type DecisionEditorState,
} from './DecisionEditorPanel'
import { DecisionCatalogPanel } from './DecisionCatalogPanel'
import { DecisionDetailPanel } from './DecisionDetailPanel'
import { buildEmptyDraft, normalizeMetadataItems } from './decisionPageUtils'
import { useDecisionEditor } from './useDecisionEditor'
import { useDecisionLegacyImport } from './useDecisionLegacyImport'
import { useDecisionsCatalog } from './useDecisionsCatalog'

const { Text } = Typography

export function DecisionsPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { t } = useDecisionsTranslation()
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(false)
  const catalog = useDecisionsCatalog()
  const legacyImport = useDecisionLegacyImport({
    message,
    onImportComplete: (decisionId) => {
      catalog.setSelectedDecisionId(decisionId)
      setIsDetailDrawerOpen(true)
      catalog.reloadCatalog()
    },
  })
  const editor = useDecisionEditor({
    effectiveSelectedDatabaseId: catalog.effectiveSelectedDatabaseId,
    selectedDatabaseLabel: catalog.selectedDatabaseLabel,
    selectedDecision: catalog.selectedDecision,
    selectedDecisionPinnedInBinding: catalog.selectedDecisionPinnedInBinding,
    selectedDecisionRequiresRollover: catalog.selectedDecisionRequiresRollover,
    selectedDecisionSupportsDocumentPolicyAuthoring: catalog.selectedDecisionSupportsDocumentPolicyAuthoring,
    metadataContextFallbackActive: catalog.metadataContextFallbackActive,
    rolloverTargetMetadataContext: catalog.rolloverTargetMetadataContext,
    message,
    onDecisionSaved: (nextDecisionId) => {
      catalog.setSelectedDecisionId(nextDecisionId)
      setIsDetailDrawerOpen(true)
      catalog.reloadCatalog()
    },
  })

  const saving = editor.saving || legacyImport.saving
  const editorMetadataContext = editor.editorDraft?.mode === 'rollover'
    ? catalog.rolloverTargetMetadataContext
    : (catalog.detailContext ?? catalog.metadataContext)
  const editorMetadataDocuments = (
    editorMetadataContext
    && typeof editorMetadataContext === 'object'
    && Array.isArray((editorMetadataContext as { documents?: unknown }).documents)
      ? (editorMetadataContext as { documents: PoolODataMetadataCatalogDocument[] }).documents
      : []
  )

  const openEditor = (mode: DecisionEditorMode, draft: DecisionEditorState) => {
    editor.openEditor(mode, draft)
    setIsDetailDrawerOpen(false)
    legacyImport.resetLegacyImport()
  }

  const openLegacyImport = () => {
    setIsDetailDrawerOpen(false)
    editor.resetEditor()
    legacyImport.openLegacyImport()
  }

  const openRawImport = () => {
    setIsDetailDrawerOpen(false)
    legacyImport.resetLegacyImport()
    editor.openRawImport()
  }

  const handleOpenSelectedDecisionForEdit = () => {
    setIsDetailDrawerOpen(false)
    legacyImport.resetLegacyImport()
    editor.handleOpenSelectedDecisionForEdit()
  }

  const handleOpenSelectedDecisionForRollover = () => {
    setIsDetailDrawerOpen(false)
    legacyImport.resetLegacyImport()
    editor.handleOpenSelectedDecisionForRollover()
  }

  const handleOpenSelectedDecisionForClone = () => {
    setIsDetailDrawerOpen(false)
    legacyImport.resetLegacyImport()
    editor.handleOpenSelectedDecisionForClone()
  }

  const handleSelectDecision = (decisionId: string) => {
    catalog.selectDecision(decisionId)
    setIsDetailDrawerOpen(true)
  }

  const handleDatabaseChange = (nextValue: string | null) => {
    catalog.selectDatabase(nextValue)
    setIsDetailDrawerOpen(false)
  }

  const handleToggleSnapshotMode = () => {
    catalog.toggleSnapshotFilterMode()
  }

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t(($) => $.page.title)}
          subtitle={t(($) => $.page.subtitle)}
          actions={(
            <Select
              aria-label={t(($) => $.page.databaseAriaLabel)}
              allowClear
              data-testid="decisions-database-select"
              placeholder={t(($) => $.page.databasePlaceholder)}
              value={catalog.effectiveSelectedDatabaseId}
              style={{ width: 'min(320px, 100%)', minWidth: 240 }}
              options={catalog.databases.map((database) => ({
                value: database.id,
                label: `${database.name} (${database.base_name ?? database.version ?? database.id})`,
              }))}
              onChange={(nextValue) => handleDatabaseChange(nextValue ?? null)}
              loading={catalog.databasesQuery.isLoading}
            />
          )}
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message={t(($) => $.page.taskFirst.title)}
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              {t(($) => $.page.taskFirst.description)}
            </Text>
            <Space wrap>
              <RouteButton to="/workflows">{t(($) => $.page.taskFirst.workflows)}</RouteButton>
              <RouteButton to="/pools/execution-packs">{t(($) => $.page.taskFirst.executionPacks)}</RouteButton>
            </Space>
          </Space>
        )}
      />

      {editor.editorError && !editor.editorDraft ? (
        <Alert
          type="error"
          showIcon
          message={editor.editorError}
          action={editor.editorError.includes('/databases') ? (
            <Button
              size="small"
              onClick={() => { navigate('/databases') }}
              data-testid="decisions-open-databases"
            >
              {t(($) => $.page.openDatabases)}
            </Button>
          ) : undefined}
        />
      ) : null}

      {legacyImport.legacyImportResult ? (
        <Alert
          closable
          showIcon
          type={legacyImport.legacyImportResult.migration.binding_update_required ? 'warning' : 'success'}
          message={t(($) => $.page.importedTitle)}
          description={(
            <Space direction="vertical" size={4}>
              <span>
                {t(($) => $.page.importedSource, {
                  path: legacyImport.legacyImportResult.migration.source.source_path,
                  edgeVersionId: legacyImport.legacyImportResult.migration.source.edge_version_id,
                })}
              </span>
              <span>
                {t(($) => $.page.importedDecisionRef, {
                  decisionTableId: legacyImport.legacyImportResult.migration.decision_ref.decision_table_id,
                  decisionRevision: String(legacyImport.legacyImportResult.migration.decision_ref.decision_revision),
                })}
              </span>
              <span>
                {t(($) => $.page.importedBindingSlot, {
                  slotKey: legacyImport.legacyImportResult.migration.slot_key,
                })}
              </span>
              {legacyImport.legacyImportResult.migration.binding_update_required ? (
                <span>{t(($) => $.page.importedBindingManual)}</span>
              ) : (
                <span>{t(($) => $.page.importedBindingAutomatic)}</span>
              )}
            </Space>
          )}
          onClose={() => legacyImport.setLegacyImportResult(null)}
        />
      ) : null}

      <EntityDetails title={t(($) => $.page.authoringWorkspace)}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => openEditor('create', buildEmptyDraft('create', 'builder'))}
              disabled={saving}
              aria-label={t(($) => $.page.newPolicy)}
            >
              {t(($) => $.page.newPolicy)}
            </Button>
            <Space wrap>
              <Button
                icon={<EditOutlined />}
                onClick={handleOpenSelectedDecisionForEdit}
                disabled={
                  !catalog.selectedDecision
                  || !catalog.selectedDecisionSupportsDocumentPolicyAuthoring
                  || saving
                  || catalog.selectedDecisionRequiresRollover
                  || catalog.metadataContextFallbackActive
                }
                aria-label={t(($) => $.page.editSelectedDecision)}
              >
                {t(($) => $.page.editSelectedDecision)}
              </Button>
              <Button
                onClick={handleOpenSelectedDecisionForRollover}
                disabled={
                  !catalog.selectedDecision
                  || !catalog.selectedDecisionSupportsDocumentPolicyAuthoring
                  || saving
                  || !catalog.canOpenRollover
                }
                aria-label={t(($) => $.page.rolloverSelectedRevision)}
              >
                {t(($) => $.page.rolloverSelectedRevision)}
              </Button>
              <Button
                onClick={handleOpenSelectedDecisionForClone}
                disabled={
                  !catalog.selectedDecision
                  || !catalog.selectedDecisionSupportsDocumentPolicyAuthoring
                  || saving
                  || catalog.metadataContextFallbackActive
                }
                aria-label={t(($) => $.page.cloneSelectedRevision)}
              >
                {t(($) => $.page.cloneSelectedRevision)}
              </Button>
              <Button
                danger
                icon={<MinusCircleOutlined />}
                onClick={() => void editor.handleDeactivateSelected()}
                disabled={
                  !catalog.selectedDecision
                  || !catalog.selectedDecisionSupportsDocumentPolicyAuthoring
                  || saving
                  || catalog.selectedDecisionRequiresRollover
                  || catalog.metadataContextFallbackActive
                }
                aria-label={t(($) => $.page.deactivateSelectedDecision)}
              >
                {t(($) => $.page.deactivateSelectedDecision)}
              </Button>
            </Space>
          </Space>

          <Collapse
            size="small"
            items={[
              {
                key: 'imports',
                label: t(($) => $.page.importTools),
                children: (
                  <Space wrap>
                    <Button
                      icon={<ImportOutlined />}
                      onClick={openLegacyImport}
                      disabled={saving}
                      aria-label={t(($) => $.page.importLegacyEdge)}
                    >
                      {t(($) => $.page.importLegacyEdge)}
                    </Button>
                    <Button
                      onClick={openRawImport}
                      disabled={saving}
                      aria-label={t(($) => $.page.importRawJson)}
                    >
                      {t(($) => $.page.importRawJson)}
                    </Button>
                  </Space>
                ),
              },
              {
                key: 'metadata',
                label: t(($) => $.page.targetMetadataContext),
                children: (
                  <dl
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                      gap: 12,
                      margin: 0,
                    }}
                  >
                    {normalizeMetadataItems(catalog.metadataContext, {
                      unavailableLabel: t(($) => $.metadata.unavailable),
                      driftYesLabel: t(($) => $.metadata.driftYes),
                      driftNoLabel: t(($) => $.metadata.driftNo),
                    }).map((item) => (
                      <div key={item.key} style={{ minWidth: 0 }}>
                        <dt style={{ fontSize: 12, color: '#8c8c8c' }}>
                          {{
                            config: t(($) => $.metadata.config),
                            version: t(($) => $.metadata.version),
                            generation: t(($) => $.metadata.generation),
                            snapshot: t(($) => $.metadata.snapshot),
                            mode: t(($) => $.metadata.mode),
                            hash: t(($) => $.metadata.hash),
                            observed_hash: t(($) => $.metadata.observedHash),
                            drift: t(($) => $.metadata.drift),
                            provenance: t(($) => $.metadata.provenance),
                          }[item.key as 'config' | 'version' | 'generation' | 'snapshot' | 'mode' | 'hash' | 'observed_hash' | 'drift' | 'provenance']}
                        </dt>
                        <dd
                          style={{
                            margin: '4px 0 0',
                            minWidth: 0,
                            overflowWrap: 'anywhere',
                            wordBreak: 'break-word',
                          }}
                        >
                          {item.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ),
              },
            ]}
          />

          {catalog.metadataContextWarning ? (
            <Alert
              type="warning"
              showIcon
              message={catalog.metadataContextWarning}
              action={(
                <Button
                  size="small"
                  onClick={() => { navigate('/databases') }}
                  data-testid="decisions-warning-open-databases"
                >
                  {t(($) => $.page.openDatabases)}
                </Button>
              )}
            />
          ) : null}
        </Space>
      </EntityDetails>

      {catalog.listError ? <Alert type="error" showIcon message={catalog.listError || t(($) => $.page.listError)} /> : null}
      {catalog.bindingUsageError ? <Alert type="warning" showIcon message={catalog.bindingUsageError || t(($) => $.page.bindingUsageError)} /> : null}

      <MasterDetailShell
        detailOpen={isDetailDrawerOpen}
        onCloseDetail={() => setIsDetailDrawerOpen(false)}
        detailDrawerTitle={catalog.selectedDecision?.name || t(($) => $.page.detailTitle)}
        list={(
          <DecisionCatalogPanel
            title={catalog.decisionListTitle}
            decisions={catalog.visibleDecisions}
            loading={catalog.listLoading}
            selectedDecisionId={catalog.selectedDecisionId}
            pinnedDecisionRefs={catalog.pinnedDecisionRefs}
            hiddenDecisionCount={catalog.hiddenDecisionCount}
            snapshotFilterMode={catalog.snapshotFilterMode}
            snapshotFilterMessage={catalog.snapshotFilterMessage}
            selectedConfigurationLabel={catalog.selectedConfigurationLabel}
            canFilterBySnapshot={catalog.canFilterBySnapshot}
            onToggleSnapshotMode={handleToggleSnapshotMode}
            onSelectDecision={handleSelectDecision}
          />
        )}
        detail={(
          <DecisionDetailPanel
            selectedDecision={catalog.selectedDecision}
            detailLoading={catalog.detailLoading}
            detailError={catalog.detailError}
            detailContext={catalog.detailContext}
            selectedPolicy={catalog.selectedPolicy}
            selectedDecisionSupportsDocumentPolicyAuthoring={catalog.selectedDecisionSupportsDocumentPolicyAuthoring}
            selectedDecisionPinnedInBinding={catalog.selectedDecisionPinnedInBinding}
            selectedDecisionRequiresRollover={catalog.selectedDecisionRequiresRollover}
          />
        )}
      />

      <DrawerFormShell
        open={Boolean(legacyImport.legacyImportDraft)}
        onClose={legacyImport.closeLegacyImport}
        title={<Typography.Title level={4} style={{ marginBottom: 0 }}>{t(($) => $.page.importLegacyEdge)}</Typography.Title>}
        subtitle={t(($) => $.legacyImport.subtitle)}
      >
        {legacyImport.legacyImportDraft ? (
          <DecisionLegacyImportPanel
            value={legacyImport.legacyImportDraft}
            pools={legacyImport.pools}
            poolsLoading={legacyImport.poolsLoading}
            graph={legacyImport.legacyImportGraph}
            graphLoading={legacyImport.legacyImportGraphLoading}
            error={legacyImport.legacyImportError}
            saving={saving}
            onCancel={legacyImport.closeLegacyImport}
            onOpenRawImport={openRawImport}
            onChange={(nextValue) => {
              legacyImport.setLegacyImportDraft(nextValue)
              legacyImport.setLegacyImportError(null)
            }}
            onImport={() => legacyImport.handleImportLegacyEdge()}
          />
        ) : null}
      </DrawerFormShell>

      <DrawerFormShell
        open={Boolean(editor.editorDraft)}
        onClose={editor.closeEditor}
      >
        {editor.editorDraft ? (
          <DecisionEditorPanel
            value={editor.editorDraft}
            error={editor.editorError}
            saving={saving}
            metadataDocuments={editorMetadataDocuments}
            onCancel={editor.closeEditor}
            onSave={() => editor.handleSaveDecision()}
            onChange={editor.setEditorDraft}
            onTabChange={editor.handleEditorTabChange}
          />
        ) : null}
      </DrawerFormShell>
    </WorkspacePage>
  )
}

export default DecisionsPage
