import { useCallback } from 'react'
import { App, Space, Typography } from 'antd'
import type { UploadProps } from 'antd'
import type { ModalFuncProps } from 'antd'
import { useAdminSupportTranslation } from '@/i18n'

import {
  type CommandSchemaCommandPatch,
  diffCommandSchemas,
  importItsCommandSchemas,
  listCommandSchemaVersions,
  previewCommandSchemas,
  promoteCommandSchemas,
  rollbackCommandSchemaOverrides,
  updateCommandSchemaOverrides,
  validateCommandSchemas,
} from '../../../api/commandSchemas'
import { getCommandSchemasEditorView } from '../../../api/commandSchemas'
import { confirmWithTracking } from '../../../observability/confirmWithTracking'
import { safeCatalogDriverSchema } from '../commandSchemasUtils'
import { parseJsonObject, safeText, saveText, deepCopy, safeOverridesDriverSchema } from '../commandSchemasUtils'
import type { CommandSchemasState } from './useCommandSchemasState'

const { Text } = Typography

type State = CommandSchemasState
type BeforeUpload = NonNullable<UploadProps['beforeUpload']>

export function useCommandSchemasActions(state: State) {
  const { message, modal } = App.useApp()
  const { t } = useAdminSupportTranslation()

  const confirm = useCallback((config: ModalFuncProps) => {
    confirmWithTracking(modal, config)
  }, [modal])

  const setCommandPatch = useCallback((commandId: string, updater: (patch: CommandSchemaCommandPatch) => void) => {
    state.setDraftOverrides((prev) => {
      const next = deepCopy(prev)
      const commandsById = next.overrides.commands_by_id
      const current = commandsById[commandId] ?? {}
      const patch = deepCopy(current) as CommandSchemaCommandPatch
      updater(patch)
      if (Object.keys(patch).length === 0) {
        delete commandsById[commandId]
      } else {
        commandsById[commandId] = patch
      }
      return next
    })
  }, [state])

  const resetCommandPatch = useCallback((commandId: string) => {
    state.setDraftOverrides((prev) => {
      const next = deepCopy(prev)
      delete next.overrides.commands_by_id[commandId]
      return next
    })
  }, [state])

  const discardChanges = useCallback(() => {
    confirm({
      title: t(($) => $.commandSchemas.actions.discardUnsavedTitle),
      content: t(($) => $.commandSchemas.actions.discardUnsavedDescription),
      okText: t(($) => $.commandSchemas.unsaved.discard),
      okButtonProps: { danger: true },
      cancelText: t(($) => $.commandSchemas.basics.cancel),
      onOk: () => {
        const next = deepCopy(state.serverOverrides)
        state.setDraftOverrides(next)
        state.setDriverSchemaText(JSON.stringify(safeOverridesDriverSchema(next), null, 2))
        state.setDriverSchemaTextError(null)
        message.success(t(($) => $.commandSchemas.actions.changesDiscarded))
      },
    })
  }, [confirm, message, state, t])

  const requestDriverChange = useCallback((nextDriver: State['activeDriver']) => {
    if (nextDriver === state.activeDriver) return

    if (state.saving || state.rollbackLoading || state.rollingBack) {
      message.info(t(($) => $.commandSchemas.actions.waitCurrentAction))
      return
    }

    if (!state.hasUnsavedChanges) {
      state.setActiveDriver(nextDriver)
      return
    }

    confirm({
      title: t(($) => $.commandSchemas.actions.unsavedChangesTitle),
      content: t(($) => $.commandSchemas.actions.unsavedChangesDescription),
      okText: t(($) => $.commandSchemas.actions.discardAndSwitch),
      okButtonProps: { danger: true },
      cancelText: t(($) => $.commandSchemas.basics.cancel),
      onOk: () => {
        state.setActiveDriver(nextDriver)
      },
    })
  }, [confirm, message, state, t])

  const requestRefreshView = useCallback(() => {
    if (state.saving || state.rollingBack) {
      message.info(t(($) => $.commandSchemas.actions.waitCurrentAction))
      return
    }

    if (!state.hasUnsavedChanges) {
      void state.fetchView()
      return
    }

    confirm({
      title: t(($) => $.commandSchemas.actions.unsavedChangesTitle),
      content: t(($) => $.commandSchemas.actions.refreshUnsavedDescription),
      okText: t(($) => $.commandSchemas.actions.discardAndRefresh),
      okButtonProps: { danger: true },
      cancelText: t(($) => $.commandSchemas.basics.cancel),
      onOk: () => {
        void state.fetchView()
      },
    })
  }, [confirm, message, state, t])

  const openImportIts = useCallback(() => {
    if (state.saving || state.rollbackLoading || state.rollingBack || state.loading) {
      message.info(t(($) => $.commandSchemas.actions.waitCurrentAction))
      return
    }

    const open = () => {
      state.setImportItsOpen(true)
      state.setImportItsReason('')
      state.setImportItsFile(null)
      state.setImportingIts(false)
    }

    if (!state.hasUnsavedChanges) {
      open()
      return
    }

    confirm({
      title: t(($) => $.commandSchemas.actions.unsavedChangesTitle),
      content: t(($) => $.commandSchemas.actions.importItsUnsavedDescription),
      okText: t(($) => $.commandSchemas.actions.discardAndContinue),
      okButtonProps: { danger: true },
      cancelText: t(($) => $.commandSchemas.basics.cancel),
      onOk: open,
    })
  }, [confirm, message, state, t])

  const handleImportItsFile = useCallback<BeforeUpload>((file) => {
    state.setImportItsFile(file)
    return false
  }, [state])

  const handleImportIts = useCallback(async () => {
    if (state.importingIts) return

    const reason = saveText(state.importItsReason)
    if (!reason) {
      message.error(t(($) => $.commandSchemas.actions.reasonRequired))
      return
    }
    if (!state.importItsFile) {
      message.error(t(($) => $.commandSchemas.actions.selectItsFile))
      return
    }

    let itsPayload: Record<string, unknown>
    try {
      const rawText = await state.importItsFile.text()
      const parsed = JSON.parse(rawText) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        message.error(t(($) => $.commandSchemas.actions.itsPayloadMustBeObject))
        return
      }
      itsPayload = parsed as Record<string, unknown>
    } catch (_err) {
      message.error(t(($) => $.commandSchemas.actions.invalidItsJson))
      return
    }

    const sections = itsPayload.sections
    const hasBlocks = Array.isArray(sections)
      && sections.some((section) => {
        if (!section || typeof section !== 'object') return false
        const blocks = (section as { blocks?: unknown }).blocks
        return Array.isArray(blocks) && blocks.length > 0
      })
    const hasCliCommandBlocks = Array.isArray(sections)
      && sections.some((section) => {
        if (!section || typeof section !== 'object') return false
        const blocks = (section as { blocks?: unknown }).blocks
        if (!Array.isArray(blocks)) return false
        return blocks.some((block) => {
          if (!block || typeof block !== 'object') return false
          const cls = String((block as { class?: unknown }).class ?? '')
          return cls.includes('Lang-parameter')
        })
      })

    if (!hasBlocks || (state.activeDriver === 'cli' && !hasCliCommandBlocks)) {
      const ok = await new Promise<boolean>((resolve) => {
        confirm({
          title: t(($) => $.commandSchemas.actions.itsQualityWarningTitle),
          content: (
            <Space direction="vertical">
              <Text>{t(($) => $.commandSchemas.actions.itsQualityWarningDescription)}</Text>
              <Text type="secondary">{t(($) => $.commandSchemas.actions.itsQualityWarningRecommended, { command: 'python scripts/dev/its-scrape.py --with-blocks --no-raw-text' })}</Text>
            </Space>
          ),
          okText: t(($) => $.commandSchemas.actions.importAnyway),
          okButtonProps: { danger: true },
          cancelText: t(($) => $.commandSchemas.basics.cancel),
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        })
      })
      if (!ok) return
    }

    state.setImportingIts(true)
    try {
      await importItsCommandSchemas({ driver: state.activeDriver, its_payload: itsPayload, save: true, reason })
      message.success(t(($) => $.commandSchemas.actions.itsImported))
      state.setImportItsOpen(false)
      await state.fetchView()
    } catch (error) {
      const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
      const backendMessage = typeof err?.response?.data?.error === 'string'
        ? err.response?.data?.error
        : err?.response?.data?.error?.message
      message.error(backendMessage || t(($) => $.commandSchemas.actions.failedImportIts))
    } finally {
      state.setImportingIts(false)
    }
  }, [confirm, message, state, t])

  const openRollback = useCallback(async () => {
    state.setRollbackOpen(true)
    state.setRollbackReason('')
    state.setRollbackVersion('')
    state.setRollbackVersions([])
    state.setRollbackLoading(true)
    state.setRollingBack(false)
    try {
      const response = await listCommandSchemaVersions(state.activeDriver, 'overrides', { limit: 200, offset: 0 })
      state.setRollbackVersions(response.versions ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedLoadOverridesVersions)
      message.error(text)
    } finally {
      state.setRollbackLoading(false)
    }
  }, [message, state, t])

  const openPromote = useCallback(() => {
    if (!state.view) {
      message.error(t(($) => $.commandSchemas.actions.editorNotLoaded))
      return
    }
    if (!state.canPromoteLatest) {
      message.info(t(($) => $.commandSchemas.actions.nothingToPromote))
      return
    }
    state.setPromoteOpen(true)
    state.setPromoteReason('')
  }, [message, state, t])

  const handlePromote = useCallback(async () => {
    if (!state.view) return

    const reason = saveText(state.promoteReason)
    if (!reason) {
      message.error(t(($) => $.commandSchemas.actions.reasonRequired))
      return
    }

    const version = safeText(state.view.base?.latest_version).trim()
    if (!version) {
      message.error(t(($) => $.commandSchemas.actions.latestBaseVersionUnavailable))
      return
    }

    state.setPromoting(true)
    try {
      await promoteCommandSchemas({
        driver: state.activeDriver,
        version,
        alias: 'approved',
        reason,
      })
      message.success(t(($) => $.commandSchemas.actions.promotedToApproved, { version }))
      state.setPromoteOpen(false)
      await state.fetchView()
    } catch (err) {
      const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedPromote)
      message.error(text)
    } finally {
      state.setPromoting(false)
    }
  }, [message, state, t])

  const handleRollback = useCallback(async () => {
    if (!state.view) return

    const reason = saveText(state.rollbackReason)
    if (!reason) {
      message.error(t(($) => $.commandSchemas.actions.reasonRequired))
      return
    }
    if (!state.rollbackVersion) {
      message.error(t(($) => $.commandSchemas.actions.selectVersionToRollback))
      return
    }

    state.setRollingBack(true)
    try {
      await rollbackCommandSchemaOverrides({
        driver: state.activeDriver,
        version: state.rollbackVersion,
        reason,
        expected_etag: state.view.etag,
      })
      message.success(t(($) => $.commandSchemas.actions.rollbackApplied))
      state.setRollbackOpen(false)
      await state.fetchView()
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        confirm({
          title: t(($) => $.commandSchemas.actions.conflictTitle),
          content: t(($) => $.commandSchemas.actions.conflictDescription),
          okText: t(($) => $.commandSchemas.actions.refreshDiscardLocalDraft),
          okButtonProps: { danger: true },
          cancelText: t(($) => $.commandSchemas.actions.keepEditing),
          onOk: () => {
            void state.fetchView()
          },
        })
      } else {
        const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedRollback)
        message.error(text)
      }
    } finally {
      state.setRollingBack(false)
    }
  }, [confirm, message, state, t])

  const openSave = useCallback(() => {
    state.setSaveOpen(true)
    state.setSaveReason('')
  }, [state])

  const handleSave = useCallback(async () => {
    if (!state.view) return

    const reason = saveText(state.saveReason)
    if (!reason) {
      message.error(t(($) => $.commandSchemas.actions.reasonRequired))
      return
    }

    state.setSaving(true)
    try {
      await updateCommandSchemaOverrides({
        driver: state.activeDriver,
        catalog: state.draftOverrides,
        reason,
        expected_etag: state.view.etag,
      })
      message.success(t(($) => $.commandSchemas.actions.overridesSaved))
      state.setSaveOpen(false)
      await state.fetchView()
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        confirm({
          title: t(($) => $.commandSchemas.actions.conflictTitle),
          content: t(($) => $.commandSchemas.actions.conflictDescription),
          okText: t(($) => $.commandSchemas.actions.refreshDiscardLocalDraft),
          okButtonProps: { danger: true },
          cancelText: t(($) => $.commandSchemas.actions.keepEditing),
          onOk: () => {
            void state.fetchView()
          },
        })
      } else {
        const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedSaveOverrides)
        message.error(text)
      }
    } finally {
      state.setSaving(false)
    }
  }, [confirm, message, state, t])

  const loadDiff = useCallback(async () => {
    if (!state.selectedCommandId) return

    state.setDiffLoading(true)
    state.setDiffError(null)
    try {
      const response = await diffCommandSchemas({ driver: state.activeDriver, command_id: state.selectedCommandId, catalog: state.draftOverrides })
      state.setDiffItems(response.changes ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedLoadDiff)
      state.setDiffError(text)
      state.setDiffItems([])
    } finally {
      state.setDiffLoading(false)
    }
  }, [state, t])

  const runValidate = useCallback(async () => {
    state.setValidateLoading(true)
    state.setValidateError(null)
    try {
      const response = await validateCommandSchemas({ driver: state.activeDriver, catalog: state.draftOverrides })
      state.setValidateIssues(response.issues ?? [])
      state.setValidateSummary({ ok: Boolean(response.ok), errors: response.errors_count ?? 0, warnings: response.warnings_count ?? 0 })
    } catch (err) {
      const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedValidate)
      state.setValidateError(text)
      state.setValidateIssues([])
      state.setValidateSummary(null)
    } finally {
      state.setValidateLoading(false)
    }
  }, [state, t])

  const buildPreview = useCallback(async () => {
    if (!state.selectedCommandId) return

    state.setPreviewLoading(true)
    state.setPreviewError(null)
    try {
      const additionalArgs = state.previewArgsText
        .split('\n')
        .map((item) => item.trim())
        .filter((item) => item.length > 0)

      const connection = state.activeDriver === 'ibcmd' ? parseJsonObject(state.previewConnectionText) : {}
      if (state.activeDriver === 'ibcmd' && !connection) {
        state.setPreviewError(t(($) => $.commandSchemas.actions.invalidConnectionJson))
        state.setPreviewArgv([])
        state.setPreviewArgvMasked([])
        return
      }

      const response = await previewCommandSchemas({
        driver: state.activeDriver,
        command_id: state.selectedCommandId,
        mode: state.previewMode,
        ...(state.activeDriver === 'ibcmd' ? { connection: connection ?? {} } : {}),
        params: state.previewParams,
        additional_args: additionalArgs,
        catalog: state.draftOverrides,
      })
      state.setPreviewArgv(response.argv ?? [])
      state.setPreviewArgvMasked(response.argv_masked ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedBuildPreview)
      state.setPreviewError(text)
      state.setPreviewArgv([])
      state.setPreviewArgvMasked([])
    } finally {
      state.setPreviewLoading(false)
    }
  }, [state, t])

  const selectCommand = useCallback((commandId: string) => {
    state.setSelectedCommandId(commandId)
    state.setActiveEditorTab('basics')
    state.setActiveSideTab('preview')
    state.setPreviewConnectionText('{}')
    state.setPreviewConnectionError(null)
    state.setPreviewParams({})
    state.setPreviewArgsText('')
    state.setPreviewArgv([])
    state.setPreviewArgvMasked([])
    state.setPreviewError(null)
    state.setDiffItems([])
    state.setDiffError(null)
  }, [state])

  const applyDriverSchemaText = useCallback((nextText: string) => {
    state.setDriverSchemaText(nextText)
    const parsed = parseJsonObject(nextText)
    if (!parsed) {
      state.setDriverSchemaTextError(t(($) => $.commandSchemas.actions.invalidConnectionJson))
      return
    }
    state.setDriverSchemaTextError(null)
    state.setDraftOverrides((prev) => ({
      ...prev,
      overrides: {
        ...prev.overrides,
        driver_schema: parsed,
      },
    }))
  }, [state, t])

  const resetDriverSchemaOverrides = useCallback(() => {
    applyDriverSchemaText('{}')
    message.success(t(($) => $.commandSchemas.actions.driverSchemaOverridesReset))
  }, [applyDriverSchemaText, message, t])

  const copyEffectiveDriverSchema = useCallback(() => {
    const effectiveSchema = safeCatalogDriverSchema(state.view?.catalogs?.effective?.catalog)
    applyDriverSchemaText(JSON.stringify(effectiveSchema ?? {}, null, 2))
    message.success(t(($) => $.commandSchemas.actions.copiedEffectiveDriverSchema))
  }, [applyDriverSchemaText, message, state.view, t])

  const copyLatestBaseDriverSchema = useCallback(async () => {
    if (state.copyLatestDriverSchemaLoading) return
    state.setCopyLatestDriverSchemaLoading(true)
    try {
      const latestView = await getCommandSchemasEditorView(state.activeDriver, 'raw')
      const latestSchema = safeCatalogDriverSchema(latestView.catalogs?.base)
      if (Object.keys(latestSchema).length === 0) {
        message.info(t(($) => $.commandSchemas.actions.latestBaseDriverSchemaEmpty))
        return
      }
      applyDriverSchemaText(JSON.stringify(latestSchema, null, 2))
      message.success(t(($) => $.commandSchemas.actions.copiedLatestBaseDriverSchema))
    } catch (err) {
      const text = err instanceof Error ? err.message : t(($) => $.commandSchemas.actions.failedLoadLatestBaseCatalog)
      message.error(text)
    } finally {
      state.setCopyLatestDriverSchemaLoading(false)
    }
  }, [applyDriverSchemaText, message, state, t])

  return {
    confirm,
    setCommandPatch,
    resetCommandPatch,
    discardChanges,
    requestDriverChange,
    requestRefreshView,
    openImportIts,
    handleImportItsFile,
    handleImportIts,
    openRollback,
    openPromote,
    handlePromote,
    handleRollback,
    openSave,
    handleSave,
    loadDiff,
    runValidate,
    buildPreview,
    selectCommand,
    applyDriverSchemaText,
    resetDriverSchemaOverrides,
    copyEffectiveDriverSchema,
    copyLatestBaseDriverSchema,
  }
}
