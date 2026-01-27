import { useCallback } from 'react'
import { App, Space, Typography } from 'antd'
import type { UploadProps } from 'antd'
import type { ModalFuncProps } from 'antd'

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
import { safeCatalogDriverSchema } from '../commandSchemasUtils'
import { parseJsonObject, safeText, saveText, deepCopy, safeOverridesDriverSchema } from '../commandSchemasUtils'
import type { CommandSchemasState } from './useCommandSchemasState'

const { Text } = Typography

type State = CommandSchemasState
type BeforeUpload = NonNullable<UploadProps['beforeUpload']>

export function useCommandSchemasActions(state: State) {
  const { message, modal } = App.useApp()

  const confirm = useCallback((config: ModalFuncProps) => {
    modal.confirm(config)
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
    modal.confirm({
      title: 'Discard unsaved changes?',
      content: 'This will reset local overrides to the current active version.',
      okText: 'Discard',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: () => {
        const next = deepCopy(state.serverOverrides)
        state.setDraftOverrides(next)
        state.setDriverSchemaText(JSON.stringify(safeOverridesDriverSchema(next), null, 2))
        state.setDriverSchemaTextError(null)
        message.success('Changes discarded')
      },
    })
  }, [message, modal, state])

  const requestDriverChange = useCallback((nextDriver: State['activeDriver']) => {
    if (nextDriver === state.activeDriver) return

    if (state.saving || state.rollbackLoading || state.rollingBack) {
      message.info('Please wait until the current action finishes')
      return
    }

    if (!state.hasUnsavedChanges) {
      state.setActiveDriver(nextDriver)
      return
    }

    modal.confirm({
      title: 'Unsaved changes',
      content: 'You have unsaved changes. Save or discard them before switching the driver.',
      okText: 'Discard and switch',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: () => {
        state.setActiveDriver(nextDriver)
      },
    })
  }, [message, modal, state])

  const requestRefreshView = useCallback(() => {
    if (state.saving || state.rollingBack) {
      message.info('Please wait until the current action finishes')
      return
    }

    if (!state.hasUnsavedChanges) {
      void state.fetchView()
      return
    }

    modal.confirm({
      title: 'Unsaved changes',
      content: 'Refresh will discard your local draft and reload the current active version.',
      okText: 'Discard and refresh',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: () => {
        void state.fetchView()
      },
    })
  }, [message, modal, state])

  const openImportIts = useCallback(() => {
    if (state.saving || state.rollbackLoading || state.rollingBack || state.loading) {
      message.info('Please wait until the current action finishes')
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

    modal.confirm({
      title: 'Unsaved changes',
      content: 'Importing ITS will reload the editor and discard your local draft.',
      okText: 'Discard and continue',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: open,
    })
  }, [message, modal, state])

  const handleImportItsFile = useCallback<BeforeUpload>((file) => {
    state.setImportItsFile(file)
    return false
  }, [state])

  const handleImportIts = useCallback(async () => {
    if (state.importingIts) return

    const reason = saveText(state.importItsReason)
    if (!reason) {
      message.error('Reason is required')
      return
    }
    if (!state.importItsFile) {
      message.error('Select ITS JSON file')
      return
    }

    let itsPayload: Record<string, unknown>
    try {
      const rawText = await state.importItsFile.text()
      const parsed = JSON.parse(rawText) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        message.error('ITS payload must be a JSON object')
        return
      }
      itsPayload = parsed as Record<string, unknown>
    } catch (_err) {
      message.error('Invalid ITS JSON file')
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
        modal.confirm({
          title: 'ITS export quality warning',
          content: (
            <Space direction="vertical">
              <Text>
                This ITS JSON does not include structured <Text code>blocks</Text> (or does not include{' '}
                <Text code>Lang-parameter</Text> command blocks for CLI). Parsing may be degraded.
              </Text>
              <Text type="secondary">
                Re-export with <Text code>python scripts/dev/its-scrape.py --with-blocks --no-raw-text</Text> for best results.
              </Text>
            </Space>
          ),
          okText: 'Import anyway',
          okButtonProps: { danger: true },
          cancelText: 'Cancel',
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        })
      })
      if (!ok) return
    }

    state.setImportingIts(true)
    try {
      await importItsCommandSchemas({ driver: state.activeDriver, its_payload: itsPayload, save: true, reason })
      message.success('ITS imported')
      state.setImportItsOpen(false)
      await state.fetchView()
    } catch (error) {
      const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
      const backendMessage = typeof err?.response?.data?.error === 'string'
        ? err.response?.data?.error
        : err?.response?.data?.error?.message
      message.error(backendMessage || 'Failed to import ITS')
    } finally {
      state.setImportingIts(false)
    }
  }, [message, modal, state])

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
      const text = err instanceof Error ? err.message : 'Failed to load overrides versions'
      message.error(text)
    } finally {
      state.setRollbackLoading(false)
    }
  }, [message, state])

  const openPromote = useCallback(() => {
    if (!state.view) {
      message.error('Editor data is not loaded yet')
      return
    }
    if (!state.canPromoteLatest) {
      message.info('Nothing to promote (approved is already latest)')
      return
    }
    state.setPromoteOpen(true)
    state.setPromoteReason('')
  }, [message, state])

  const handlePromote = useCallback(async () => {
    if (!state.view) return

    const reason = saveText(state.promoteReason)
    if (!reason) {
      message.error('Reason is required')
      return
    }

    const version = safeText(state.view.base?.latest_version).trim()
    if (!version) {
      message.error('Latest base version is not available')
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
      message.success(`Promoted ${version} to approved`)
      state.setPromoteOpen(false)
      await state.fetchView()
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to promote'
      message.error(text)
    } finally {
      state.setPromoting(false)
    }
  }, [message, state])

  const handleRollback = useCallback(async () => {
    if (!state.view) return

    const reason = saveText(state.rollbackReason)
    if (!reason) {
      message.error('Reason is required')
      return
    }
    if (!state.rollbackVersion) {
      message.error('Select version to rollback')
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
      message.success('Rollback applied')
      state.setRollbackOpen(false)
      await state.fetchView()
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        modal.confirm({
          title: 'Conflict',
          content: 'Overrides changed since you opened the editor. Refresh to load the latest active version (local draft will be discarded).',
          okText: 'Refresh (discard local draft)',
          okButtonProps: { danger: true },
          cancelText: 'Keep editing',
          onOk: () => {
            void state.fetchView()
          },
        })
      } else {
        const text = err instanceof Error ? err.message : 'Failed to rollback overrides'
        message.error(text)
      }
    } finally {
      state.setRollingBack(false)
    }
  }, [message, modal, state])

  const openSave = useCallback(() => {
    state.setSaveOpen(true)
    state.setSaveReason('')
  }, [state])

  const handleSave = useCallback(async () => {
    if (!state.view) return

    const reason = saveText(state.saveReason)
    if (!reason) {
      message.error('Reason is required')
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
      message.success('Overrides saved')
      state.setSaveOpen(false)
      await state.fetchView()
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        modal.confirm({
          title: 'Conflict',
          content: 'Overrides changed since you opened the editor. Refresh to load the latest active version (local draft will be discarded).',
          okText: 'Refresh (discard local draft)',
          okButtonProps: { danger: true },
          cancelText: 'Keep editing',
          onOk: () => {
            void state.fetchView()
          },
        })
      } else {
        const text = err instanceof Error ? err.message : 'Failed to save overrides'
        message.error(text)
      }
    } finally {
      state.setSaving(false)
    }
  }, [message, modal, state])

  const loadDiff = useCallback(async () => {
    if (!state.selectedCommandId) return

    state.setDiffLoading(true)
    state.setDiffError(null)
    try {
      const response = await diffCommandSchemas({ driver: state.activeDriver, command_id: state.selectedCommandId, catalog: state.draftOverrides })
      state.setDiffItems(response.changes ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to load diff'
      state.setDiffError(text)
      state.setDiffItems([])
    } finally {
      state.setDiffLoading(false)
    }
  }, [state])

  const runValidate = useCallback(async () => {
    state.setValidateLoading(true)
    state.setValidateError(null)
    try {
      const response = await validateCommandSchemas({ driver: state.activeDriver, catalog: state.draftOverrides })
      state.setValidateIssues(response.issues ?? [])
      state.setValidateSummary({ ok: Boolean(response.ok), errors: response.errors_count ?? 0, warnings: response.warnings_count ?? 0 })
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to validate'
      state.setValidateError(text)
      state.setValidateIssues([])
      state.setValidateSummary(null)
    } finally {
      state.setValidateLoading(false)
    }
  }, [state])

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
        state.setPreviewError('Invalid connection JSON: expected a JSON object')
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
      const text = err instanceof Error ? err.message : 'Failed to build preview'
      state.setPreviewError(text)
      state.setPreviewArgv([])
      state.setPreviewArgvMasked([])
    } finally {
      state.setPreviewLoading(false)
    }
  }, [state])

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
      state.setDriverSchemaTextError('Invalid JSON: expected a JSON object')
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
  }, [state])

  const resetDriverSchemaOverrides = useCallback(() => {
    applyDriverSchemaText('{}')
    message.success('Driver schema overrides reset')
  }, [applyDriverSchemaText, message])

  const copyEffectiveDriverSchema = useCallback(() => {
    const effectiveSchema = safeCatalogDriverSchema(state.view?.catalogs?.effective?.catalog)
    applyDriverSchemaText(JSON.stringify(effectiveSchema ?? {}, null, 2))
    message.success('Copied effective driver schema into overrides')
  }, [applyDriverSchemaText, message, state.view])

  const copyLatestBaseDriverSchema = useCallback(async () => {
    if (state.copyLatestDriverSchemaLoading) return
    state.setCopyLatestDriverSchemaLoading(true)
    try {
      const latestView = await getCommandSchemasEditorView(state.activeDriver, 'raw')
      const latestSchema = safeCatalogDriverSchema(latestView.catalogs?.base)
      if (Object.keys(latestSchema).length === 0) {
        message.info('Latest base driver schema is empty')
        return
      }
      applyDriverSchemaText(JSON.stringify(latestSchema, null, 2))
      message.success('Copied latest base driver schema into overrides')
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to load latest base catalog'
      message.error(text)
    } finally {
      state.setCopyLatestDriverSchemaLoading(false)
    }
  }, [applyDriverSchemaText, message, state])

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
