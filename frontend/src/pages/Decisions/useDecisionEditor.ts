import { useState } from 'react'

import type { DecisionTable } from '../../api/generated/model'
import { getV2 } from '../../api/generated'
import {
  buildDocumentPolicyDecisionPayload,
  buildDocumentPolicyFromBuilder,
  documentPolicyToBuilderChains,
  type DocumentPolicyBuilderChainFormValue,
} from './documentPolicyBuilder'
import type {
  DecisionEditorMode,
  DecisionEditorState,
  DecisionEditorTab,
} from './DecisionEditorPanel'
import {
  buildChainsFromDraft,
  buildDraftFromDecision,
  buildEditorTargetSummary,
  LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE,
  METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE,
  METADATA_CONTEXT_CLONE_BLOCKED_MESSAGE,
  METADATA_CONTEXT_ROLLOVER_BLOCKED_MESSAGE,
  toErrorMessage,
  type MetadataContextLike,
  DECISIONS_API_OPTIONS,
} from './decisionPageUtils'

const api = getV2()

type MessageLike = {
  success: (content: string) => void
  warning: (content: string) => void
}

type UseDecisionEditorArgs = {
  effectiveSelectedDatabaseId: string | undefined
  selectedDatabaseLabel: string
  selectedDecision: DecisionTable | null
  selectedDecisionPinnedInBinding: boolean
  selectedDecisionRequiresRollover: boolean
  selectedDecisionSupportsDocumentPolicyAuthoring: boolean
  metadataContextFallbackActive: boolean
  rolloverTargetMetadataContext: MetadataContextLike
  message: MessageLike
  onDecisionSaved: (nextDecisionId: string | null) => void
}

const buildRawJsonFromChains = (chains: DocumentPolicyBuilderChainFormValue[]) =>
  JSON.stringify(buildDocumentPolicyFromBuilder(chains), null, 2)

export function useDecisionEditor({
  effectiveSelectedDatabaseId,
  selectedDatabaseLabel,
  selectedDecision,
  selectedDecisionPinnedInBinding,
  selectedDecisionRequiresRollover,
  selectedDecisionSupportsDocumentPolicyAuthoring,
  metadataContextFallbackActive,
  rolloverTargetMetadataContext,
  message,
  onDecisionSaved,
}: UseDecisionEditorArgs) {
  const [editorDraft, setEditorDraft] = useState<DecisionEditorState | null>(null)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const openEditor = (_mode: DecisionEditorMode, draft: DecisionEditorState) => {
    setEditorDraft(draft)
    setEditorError(null)
  }

  const closeEditor = () => {
    if (saving) return
    setEditorDraft(null)
    setEditorError(null)
  }

  const resetEditor = () => {
    if (saving) return
    setEditorDraft(null)
    setEditorError(null)
  }

  const openRawImport = () => {
    openEditor('import', {
      mode: 'import',
      decisionTableId: '',
      name: '',
      description: '',
      chains: [],
      rawJson: '',
      activeTab: 'raw',
      isActive: true,
    })
  }

  const handleOpenSelectedDecisionForEdit = () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorDraft(null)
      setEditorError(
        selectedDecisionPinnedInBinding
          ? LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE
          : `This revision uses decision_key "${selectedDecision.decision_key}". /decisions editing supports only document_policy.`
      )
      return
    }
    if (metadataContextFallbackActive) {
      setEditorDraft(null)
      setEditorError(METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE)
      return
    }
    if (selectedDecisionRequiresRollover) {
      setEditorDraft(null)
      setEditorError('This revision is outside the selected target configuration. Use guided rollover to publish a new revision for the current database.')
      return
    }

    try {
      openEditor('revise', buildDraftFromDecision(selectedDecision))
    } catch (error) {
      setEditorDraft(null)
      setEditorError(toErrorMessage(error, 'Selected decision cannot be opened in the editor.'))
    }
  }

  const handleOpenSelectedDecisionForRollover = () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorDraft(null)
      setEditorError(
        selectedDecisionPinnedInBinding
          ? LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE
          : `This revision uses decision_key "${selectedDecision.decision_key}". /decisions rollover supports only document_policy.`
      )
      return
    }
    if (!effectiveSelectedDatabaseId || !selectedDatabaseLabel) {
      setEditorDraft(null)
      setEditorError('Select a target database before starting guided rollover.')
      return
    }

    const targetSummary = buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    })
    if (!targetSummary) {
      setEditorDraft(null)
      setEditorError(METADATA_CONTEXT_ROLLOVER_BLOCKED_MESSAGE)
      return
    }

    try {
      openEditor(
        'rollover',
        buildDraftFromDecision(selectedDecision, {
          mode: 'rollover',
          targetDatabaseId: effectiveSelectedDatabaseId,
          targetSummary,
        }),
      )
    } catch (error) {
      setEditorDraft(null)
      setEditorError(toErrorMessage(error, 'Selected decision cannot be opened as a rollover source.'))
    }
  }

  const handleOpenSelectedDecisionForClone = () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorDraft(null)
      setEditorError(
        selectedDecisionPinnedInBinding
          ? LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE
          : `This revision uses decision_key "${selectedDecision.decision_key}". /decisions clone supports only document_policy.`
      )
      return
    }
    if (metadataContextFallbackActive) {
      setEditorDraft(null)
      setEditorError(METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE)
      return
    }
    if (!effectiveSelectedDatabaseId || !selectedDatabaseLabel) {
      setEditorDraft(null)
      setEditorError('Select a target database before cloning the selected revision.')
      return
    }

    const targetSummary = buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    })
    if (!targetSummary) {
      setEditorDraft(null)
      setEditorError(METADATA_CONTEXT_CLONE_BLOCKED_MESSAGE)
      return
    }

    try {
      openEditor(
        'clone',
        buildDraftFromDecision(selectedDecision, {
          mode: 'clone',
          targetDatabaseId: effectiveSelectedDatabaseId,
          targetSummary,
        }),
      )
    } catch (error) {
      setEditorDraft(null)
      setEditorError(toErrorMessage(error, 'Selected decision cannot be opened as a clone source.'))
    }
  }

  const handleEditorTabChange = (nextTab: DecisionEditorTab) => {
    if (!editorDraft || editorDraft.activeTab === nextTab) return

    if (nextTab === 'raw') {
      try {
        setEditorDraft({ ...editorDraft, activeTab: 'raw', rawJson: buildRawJsonFromChains(editorDraft.chains) })
        setEditorError(null)
        return
      } catch {
        setEditorDraft({ ...editorDraft, activeTab: 'raw' })
        setEditorError(null)
        return
      }
    }

    try {
      const parsed = JSON.parse(editorDraft.rawJson || '{}')
      const chains = documentPolicyToBuilderChains(parsed)
      setEditorDraft({ ...editorDraft, activeTab: 'builder', chains })
      setEditorError(null)
    } catch (error) {
      setEditorError(toErrorMessage(error, 'Failed to parse raw document policy JSON.'))
    }
  }

  const handleSaveDecision = async () => {
    if (!editorDraft) return

    setSaving(true)
    setEditorError(null)

    try {
      const payload = buildDocumentPolicyDecisionPayload({
        database_id: editorDraft.targetDatabaseId ?? effectiveSelectedDatabaseId,
        decision_table_id: editorDraft.decisionTableId,
        name: editorDraft.name,
        description: editorDraft.description,
        chains: buildChainsFromDraft(editorDraft),
        parent_version_id: editorDraft.parentVersionId,
        is_active: editorDraft.isActive,
      })

      const response = await api.postDecisionsCollection(payload, DECISIONS_API_OPTIONS)
      const nextDecisionId = response?.decision?.id ?? null
      message.success(
        editorDraft.mode === 'rollover'
          ? 'Rollover revision created'
          : editorDraft.mode === 'clone'
            ? 'Cloned decision created'
          : editorDraft.mode === 'revise'
            ? 'Decision revision created'
            : 'Decision saved',
      )
      setEditorDraft(null)
      onDecisionSaved(nextDecisionId)
    } catch (error) {
      setEditorError(toErrorMessage(error, 'Failed to save decision.'))
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivateSelected = async () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorError(
        selectedDecisionPinnedInBinding
          ? LEGACY_BOUND_DECISION_READ_ONLY_MESSAGE
          : `This revision uses decision_key "${selectedDecision.decision_key}". /decisions deactivation supports only document_policy.`
      )
      return
    }
    if (metadataContextFallbackActive) {
      setEditorError(METADATA_CONTEXT_ACTION_BLOCKED_MESSAGE)
      return
    }

    setSaving(true)
    setEditorError(null)

    try {
      const payload = buildDocumentPolicyDecisionPayload({
        database_id: effectiveSelectedDatabaseId,
        decision_table_id: selectedDecision.decision_table_id,
        name: selectedDecision.name,
        description: selectedDecision.description ?? '',
        chains: buildChainsFromDraft(buildDraftFromDecision(selectedDecision)),
        parent_version_id: selectedDecision.id,
        is_active: false,
      })

      await api.postDecisionsCollection(payload, DECISIONS_API_OPTIONS)
      message.warning('Decision deactivated')
      onDecisionSaved(selectedDecision.id)
    } catch (error) {
      setEditorError(toErrorMessage(error, 'Failed to deactivate decision.'))
    } finally {
      setSaving(false)
    }
  }

  return {
    editorDraft,
    editorError,
    saving,
    setEditorDraft,
    setEditorError,
    openEditor,
    openRawImport,
    closeEditor,
    resetEditor,
    handleOpenSelectedDecisionForEdit,
    handleOpenSelectedDecisionForRollover,
    handleOpenSelectedDecisionForClone,
    handleEditorTabChange,
    handleSaveDecision,
    handleDeactivateSelected,
  }
}
