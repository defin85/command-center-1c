import { EditOutlined, ImportOutlined, MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Select,
  Space,
  Typography,
} from 'antd'

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

const { Title, Text } = Typography

export function DecisionsPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const catalog = useDecisionsCatalog()
  const legacyImport = useDecisionLegacyImport({
    message,
    onImportComplete: (decisionId) => {
      catalog.setSelectedDecisionId(decisionId)
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
      catalog.reloadCatalog()
    },
  })

  const saving = editor.saving || legacyImport.saving

  const openEditor = (mode: DecisionEditorMode, draft: DecisionEditorState) => {
    editor.openEditor(mode, draft)
    legacyImport.resetLegacyImport()
  }

  const openLegacyImport = () => {
    editor.resetEditor()
    legacyImport.openLegacyImport()
  }

  const openRawImport = () => {
    legacyImport.resetLegacyImport()
    editor.openRawImport()
  }

  const handleOpenSelectedDecisionForEdit = () => {
    legacyImport.resetLegacyImport()
    editor.handleOpenSelectedDecisionForEdit()
  }

  const handleOpenSelectedDecisionForRollover = () => {
    legacyImport.resetLegacyImport()
    editor.handleOpenSelectedDecisionForRollover()
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space direction="vertical" size={4}>
        <Title level={2} style={{ marginBottom: 0 }}>Decision Policy Library</Title>
        <Text type="secondary">/decisions is the primary surface for document_policy authoring.</Text>
      </Space>

      <Alert
        type="info"
        showIcon
        message="Canonical authoring surfaces"
        description={(
          <Space direction="vertical" size={8}>
            <Text>
              Use `/decisions` to author document policies, `/workflows` to publish reusable workflow revisions,
              and `/pools/binding-profiles` to pin those revisions into reusable profile bundles without copy-paste.
            </Text>
            <Space wrap>
              <Button href="/workflows">Open workflow catalog</Button>
              <Button href="/pools/binding-profiles">Open binding profile catalog</Button>
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
              Открыть /databases
            </Button>
          ) : undefined}
        />
      ) : null}

      {legacyImport.legacyImportResult ? (
        <Alert
          closable
          showIcon
          type={legacyImport.legacyImportResult.migration.binding_update_required ? 'warning' : 'success'}
          message="Imported to /decisions"
          description={(
            <Space direction="vertical" size={4}>
              <span>
                {`Source: ${legacyImport.legacyImportResult.migration.source.source_path} (${legacyImport.legacyImportResult.migration.source.edge_version_id})`}
              </span>
              <span>
                {`Decision ref: ${legacyImport.legacyImportResult.migration.decision_ref.decision_table_id} r${legacyImport.legacyImportResult.migration.decision_ref.decision_revision}`}
              </span>
              <span>
                {`Binding slot: ${legacyImport.legacyImportResult.migration.slot_key}`}
              </span>
              {legacyImport.legacyImportResult.migration.binding_update_required ? (
                <span>Updated bindings: manual binding pin required</span>
              ) : (
                <span>Affected workflow bindings were updated automatically.</span>
              )}
            </Space>
          )}
          onClose={() => legacyImport.setLegacyImportResult(null)}
        />
      ) : null}

      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space wrap>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => openEditor('create', buildEmptyDraft('create', 'builder'))}
                disabled={saving}
                aria-label="New policy"
              >
                New policy
              </Button>
              <Button
                icon={<ImportOutlined />}
                onClick={openLegacyImport}
                disabled={saving}
                aria-label="Import legacy edge"
              >
                Import legacy edge
              </Button>
              <Button
                onClick={openRawImport}
                disabled={saving}
                aria-label="Import raw JSON"
              >
                Import raw JSON
              </Button>
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
                aria-label="Edit selected decision"
              >
                Edit selected decision
              </Button>
              <Button
                onClick={handleOpenSelectedDecisionForRollover}
                disabled={
                  !catalog.selectedDecision
                  || !catalog.selectedDecisionSupportsDocumentPolicyAuthoring
                  || saving
                  || !catalog.canOpenRollover
                }
                aria-label="Rollover selected revision"
              >
                Rollover selected revision
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
                aria-label="Deactivate selected decision"
              >
                Deactivate selected decision
              </Button>
            </Space>

            <Select
              allowClear
              data-testid="decisions-database-select"
              placeholder="Select database"
              value={catalog.effectiveSelectedDatabaseId}
              style={{ minWidth: 260 }}
              options={catalog.databases.map((database) => ({
                value: database.id,
                label: `${database.name} (${database.base_name ?? database.version ?? database.id})`,
              }))}
              onChange={(nextValue) => catalog.setSelectedDatabaseId(nextValue ?? null)}
              loading={catalog.databasesQuery.isLoading}
            />
          </Space>

          <Descriptions
            size="small"
            column={{ xs: 1, md: 3 }}
            items={normalizeMetadataItems(catalog.metadataContext).map((item) => ({
              key: item.key,
              label: item.label,
              children: item.value,
            }))}
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
                  Открыть /databases
                </Button>
              )}
            />
          ) : null}
        </Space>
      </Card>

      {catalog.listError ? <Alert type="error" showIcon message={catalog.listError} /> : null}
      {catalog.bindingUsageError ? <Alert type="warning" showIcon message={catalog.bindingUsageError} /> : null}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(320px, 420px) minmax(0, 1fr)',
          gap: 24,
          alignItems: 'start',
        }}
      >
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
          onToggleSnapshotMode={() => catalog.setSnapshotFilterMode((current) => (
            current === 'matching_snapshot' ? 'all' : 'matching_snapshot'
          ))}
          onSelectDecision={catalog.setSelectedDecisionId}
        />

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
      </div>

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
          onImport={() => void legacyImport.handleImportLegacyEdge()}
        />
      ) : null}

      {editor.editorDraft ? (
        <DecisionEditorPanel
          value={editor.editorDraft}
          error={editor.editorError}
          saving={saving}
          onCancel={editor.closeEditor}
          onSave={() => void editor.handleSaveDecision()}
          onChange={editor.setEditorDraft}
          onTabChange={editor.handleEditorTabChange}
        />
      ) : null}
    </Space>
  )
}

export default DecisionsPage
