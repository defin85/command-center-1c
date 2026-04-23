import { useState } from 'react'

import type { DecisionTable } from '../../api/generated/model/decisionTable'
import { getV2 } from '../../api/generated'
import { useDecisionsTranslation } from '../../i18n'
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
  expectDecisionDetailResponse,
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
  const { t } = useDecisionsTranslation()
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
          ? t(($) => $.messages.legacyBoundReadOnly)
          : t(($) => $.messages.unsupportedEdit, { decisionKey: selectedDecision.decision_key })
      )
      return
    }
    if (metadataContextFallbackActive) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.metadataContextActionBlocked))
      return
    }
    if (selectedDecisionRequiresRollover) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.selectedOutsideConfiguration))
      return
    }

    try {
      openEditor('revise', buildDraftFromDecision(selectedDecision))
    } catch (error) {
      setEditorDraft(null)
      setEditorError(toErrorMessage(error, t(($) => $.messages.openEditorFailed)))
    }
  }

  const handleOpenSelectedDecisionForRollover = () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorDraft(null)
      setEditorError(
        selectedDecisionPinnedInBinding
          ? t(($) => $.messages.legacyBoundReadOnly)
          : t(($) => $.messages.unsupportedRollover, { decisionKey: selectedDecision.decision_key })
      )
      return
    }
    if (!effectiveSelectedDatabaseId || !selectedDatabaseLabel) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.selectDatabaseBeforeRollover))
      return
    }

    const targetSummary = buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    })
    if (!targetSummary) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.metadataContextRolloverBlocked))
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
      setEditorError(toErrorMessage(error, t(($) => $.messages.openRolloverFailed)))
    }
  }

  const handleOpenSelectedDecisionForClone = () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorDraft(null)
      setEditorError(
        selectedDecisionPinnedInBinding
          ? t(($) => $.messages.legacyBoundReadOnly)
          : t(($) => $.messages.unsupportedClone, { decisionKey: selectedDecision.decision_key })
      )
      return
    }
    if (metadataContextFallbackActive) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.metadataContextActionBlocked))
      return
    }
    if (!effectiveSelectedDatabaseId || !selectedDatabaseLabel) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.selectDatabaseBeforeClone))
      return
    }

    const targetSummary = buildEditorTargetSummary(rolloverTargetMetadataContext, {
      databaseId: effectiveSelectedDatabaseId,
      databaseLabel: selectedDatabaseLabel,
    })
    if (!targetSummary) {
      setEditorDraft(null)
      setEditorError(t(($) => $.messages.metadataContextCloneBlocked))
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
      setEditorError(toErrorMessage(error, t(($) => $.messages.openCloneFailed)))
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
      setEditorError(toErrorMessage(error, t(($) => $.messages.parseRawJsonFailed)))
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

      const response = expectDecisionDetailResponse(
        await api.postDecisionsCollection(payload, DECISIONS_API_OPTIONS)
      )
      const nextDecisionId = response?.decision?.id ?? null
      message.success(
        editorDraft.mode === 'rollover'
          ? t(($) => $.messages.saveSuccessRollover)
          : editorDraft.mode === 'clone'
            ? t(($) => $.messages.saveSuccessClone)
          : editorDraft.mode === 'revise'
            ? t(($) => $.messages.saveSuccessRevision)
            : t(($) => $.messages.saveSuccess),
      )
      setEditorDraft(null)
      onDecisionSaved(nextDecisionId)
    } catch (error) {
      setEditorError(toErrorMessage(error, t(($) => $.messages.saveFailed)))
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivateSelected = async () => {
    if (!selectedDecision) return
    if (!selectedDecisionSupportsDocumentPolicyAuthoring) {
      setEditorError(
        selectedDecisionPinnedInBinding
          ? t(($) => $.messages.legacyBoundReadOnly)
          : t(($) => $.messages.unsupportedDeactivate, { decisionKey: selectedDecision.decision_key })
      )
      return
    }
    if (metadataContextFallbackActive) {
      setEditorError(t(($) => $.messages.metadataContextActionBlocked))
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
      message.warning(t(($) => $.messages.deactivated))
      onDecisionSaved(selectedDecision.id)
    } catch (error) {
      setEditorError(toErrorMessage(error, t(($) => $.messages.deactivateFailed)))
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
