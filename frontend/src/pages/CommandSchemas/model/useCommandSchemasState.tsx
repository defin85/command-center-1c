import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAdminSupportTranslation } from '@/i18n'

import type { DriverCommandParamV2, DriverCommandV2 } from '../../../api/driverCommands'
import {
  getCommandSchemasEditorView,
  type CommandSchemaDriver,
  type CommandSchemaIssue,
  type CommandSchemasDiffItem,
  type CommandSchemasOverridesCatalogV2,
  type CommandSchemaVersionListItem,
} from '../../../api/commandSchemas'
import {
  buildEmptyOverrides,
  deepCopy,
  deepMergeObject,
  displayCommandId,
  groupKeyForCommand,
  normalizeOverridesCatalog,
  safeCommandsById,
  safeOverridesById,
  safeOverridesDriverSchema,
  safeText,
  type CommandListItem,
} from '../commandSchemasUtils'
import type { CommandSchemasEditorTab, CommandSchemasMode, CommandSchemasSideTab, CommandSchemasValidateSummary } from './types'

export function useCommandSchemasState() {
  const { t } = useAdminSupportTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeMode = (searchParams.get('mode') || '').trim().toLowerCase() === 'raw' ? 'raw' : 'guided'
  const routeDriver = (() => {
    const raw = (searchParams.get('driver') || '').trim().toLowerCase()
    return raw === 'cli' ? 'cli' : 'ibcmd'
  })()
  const routeCommandId = (searchParams.get('command') || '').trim()
  const failedLoadCommandSchemasText = t(($) => $.commandSchemas.actions.failedLoadCommandSchemas)

  const [mode, setMode] = useState<CommandSchemasMode>(() => routeMode)

  const [activeDriver, setActiveDriver] = useState<CommandSchemaDriver>(() => routeDriver)

  const [rawDirty, setRawDirty] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<Awaited<ReturnType<typeof getCommandSchemasEditorView>> | null>(null)

  const [serverOverrides, setServerOverrides] = useState<CommandSchemasOverridesCatalogV2>(buildEmptyOverrides('ibcmd'))
  const [draftOverrides, setDraftOverrides] = useState<CommandSchemasOverridesCatalogV2>(buildEmptyOverrides('ibcmd'))
  const [selectedCommandId, setSelectedCommandId] = useState<string>(() => routeCommandId)

  const [search, setSearch] = useState('')
  const [riskFilter, setRiskFilter] = useState<'any' | 'safe' | 'dangerous'>('any')
  const [scopeFilter, setScopeFilter] = useState<'any' | 'per_database' | 'global'>('any')
  const [onlyModified, setOnlyModified] = useState(false)
  const [hideDisabled, setHideDisabled] = useState(false)

  const [activeEditorTab, setActiveEditorTab] = useState<CommandSchemasEditorTab>('basics')
  const [activeSideTab, setActiveSideTab] = useState<CommandSchemasSideTab>('preview')

  const [saveOpen, setSaveOpen] = useState(false)
  const [saveReason, setSaveReason] = useState('')
  const [saving, setSaving] = useState(false)

  const [importItsOpen, setImportItsOpen] = useState(false)
  const [importItsReason, setImportItsReason] = useState('')
  const [importItsFile, setImportItsFile] = useState<File | null>(null)
  const [importingIts, setImportingIts] = useState(false)

  const [rollbackOpen, setRollbackOpen] = useState(false)
  const [rollbackReason, setRollbackReason] = useState('')
  const [rollbackLoading, setRollbackLoading] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)
  const [rollbackVersions, setRollbackVersions] = useState<CommandSchemaVersionListItem[]>([])
  const [rollbackVersion, setRollbackVersion] = useState<string>('')

  const [promoteOpen, setPromoteOpen] = useState(false)
  const [promoteReason, setPromoteReason] = useState('')
  const [promoting, setPromoting] = useState(false)

  const [previewMode, setPreviewMode] = useState<'guided' | 'manual'>('guided')
  const [previewConnectionText, setPreviewConnectionText] = useState('{}')
  const [previewConnectionError, setPreviewConnectionError] = useState<string | null>(null)
  const [previewParams, setPreviewParams] = useState<Record<string, unknown>>({})
  const [previewArgsText, setPreviewArgsText] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [previewArgv, setPreviewArgv] = useState<string[]>([])
  const [previewArgvMasked, setPreviewArgvMasked] = useState<string[]>([])

  const [diffLoading, setDiffLoading] = useState(false)
  const [diffError, setDiffError] = useState<string | null>(null)
  const [diffItems, setDiffItems] = useState<CommandSchemasDiffItem[]>([])

  const [validateLoading, setValidateLoading] = useState(false)
  const [validateError, setValidateError] = useState<string | null>(null)
  const [validateIssues, setValidateIssues] = useState<CommandSchemaIssue[]>([])
  const [validateSummary, setValidateSummary] = useState<CommandSchemasValidateSummary | null>(null)

  const [driverSchemaText, setDriverSchemaText] = useState('{}')
  const [driverSchemaTextError, setDriverSchemaTextError] = useState<string | null>(null)
  const [copyLatestDriverSchemaLoading, setCopyLatestDriverSchemaLoading] = useState(false)

  const fetchView = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getCommandSchemasEditorView(activeDriver, mode)
      setView(data)

      const normalizedServer = normalizeOverridesCatalog(activeDriver, data.catalogs?.overrides)
      setServerOverrides(normalizedServer)
      setDraftOverrides(deepCopy(normalizedServer))
      setDriverSchemaText(JSON.stringify(safeOverridesDriverSchema(normalizedServer), null, 2))
      setDriverSchemaTextError(null)

      setActiveEditorTab('basics')
      setActiveSideTab('preview')
      setPreviewConnectionText('{}')
      setPreviewConnectionError(null)
      setPreviewParams({})
      setPreviewArgsText('')
      setPreviewArgv([])
      setPreviewArgvMasked([])
      setPreviewError(null)
      setDiffItems([])
      setDiffError(null)
      setValidateIssues([])
      setValidateError(null)
      setValidateSummary(null)
    } catch (err) {
      const text = err instanceof Error ? err.message : failedLoadCommandSchemasText
      setError(text)
    } finally {
      setLoading(false)
    }
  }, [activeDriver, failedLoadCommandSchemasText, mode])

  useEffect(() => {
    void fetchView()
  }, [fetchView])

  useEffect(() => {
    if (mode !== routeMode) {
      setMode(routeMode)
    }
  }, [mode, routeMode])

  useEffect(() => {
    if (activeDriver !== routeDriver) {
      setActiveDriver(routeDriver)
    }
  }, [activeDriver, routeDriver])

  const routeEffectiveCommandsById = useMemo(
    () => safeCommandsById(view?.catalogs?.effective?.catalog),
    [view],
  )
  const routeEffectiveCommandIds = useMemo(
    () => Object.keys(routeEffectiveCommandsById).sort(),
    [routeEffectiveCommandsById],
  )

  useEffect(() => {
    if (!view || view.driver !== activeDriver) {
      return
    }

    const firstId = routeEffectiveCommandIds[0] ?? ''
    setSelectedCommandId((prev) => {
      if (routeCommandId && routeEffectiveCommandsById[routeCommandId]) {
        return routeCommandId
      }
      return prev && routeEffectiveCommandsById[prev] ? prev : firstId
    })
  }, [activeDriver, routeCommandId, routeEffectiveCommandIds, routeEffectiveCommandsById, view])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    next.set('driver', activeDriver)
    next.set('mode', mode)
    if (selectedCommandId) {
      next.set('command', selectedCommandId)
    } else {
      next.delete('command')
    }
    if (next.toString() === searchParams.toString()) {
      return
    }
    setSearchParams(next, { replace: true })
  }, [activeDriver, mode, searchParams, selectedCommandId, setSearchParams])

  const baseCatalog = view?.catalogs?.base
  const baseCommandsById = useMemo(() => safeCommandsById(baseCatalog), [baseCatalog])
  const overridesById = useMemo(() => safeOverridesById(draftOverrides), [draftOverrides])
  const overridesDriverSchema = useMemo(() => safeOverridesDriverSchema(draftOverrides), [draftOverrides])

  const draftEffectiveCommandsById = useMemo(() => {
    const out: Record<string, DriverCommandV2> = {}
    const ids = new Set<string>([
      ...Object.keys(baseCommandsById),
      ...Object.keys(overridesById),
    ])

    for (const id of ids) {
      const baseCommand = baseCommandsById[id]
      const patch = overridesById[id]

      if (!patch) {
        if (baseCommand) {
          out[id] = baseCommand
        }
        continue
      }

      const merged: Record<string, unknown> = baseCommand ? (deepCopy(baseCommand) as unknown as Record<string, unknown>) : {}
      deepMergeObject(merged, patch as unknown as Record<string, unknown>)
      out[id] = merged as unknown as DriverCommandV2
    }

    return out
  }, [baseCommandsById, overridesById])

  const dirty = useMemo(() => JSON.stringify(serverOverrides) !== JSON.stringify(draftOverrides), [serverOverrides, draftOverrides])
  const hasUnsavedChanges = mode === 'raw' ? rawDirty : dirty

  const canPromoteLatest = useMemo(() => {
    if (!view) return false
    const approved = safeText(view.base?.approved_version).trim()
    const latest = safeText(view.base?.latest_version).trim()
    return Boolean(latest) && approved !== latest
  }, [view])

  const selectedEffective = selectedCommandId ? draftEffectiveCommandsById[selectedCommandId] : undefined
  const selectedBase = selectedCommandId ? baseCommandsById[selectedCommandId] : undefined
  const selectedPatch = selectedCommandId ? overridesById[selectedCommandId] : undefined

  const commands: CommandListItem[] = useMemo(() => {
    const query = search.trim().toLowerCase()
    const items: CommandListItem[] = []

    for (const [id, cmd] of Object.entries(draftEffectiveCommandsById)) {
      const label = safeText(cmd?.label).trim() || id
      const description = safeText(cmd?.description).trim()
      const scope = safeText(cmd?.scope).trim().toLowerCase()
      const risk = safeText(cmd?.risk_level).trim().toLowerCase()
      const disabled = Boolean(cmd?.disabled)
      const hasOverrides = Boolean(overridesById[id])

      const paramsByName = (cmd?.params_by_name && typeof cmd.params_by_name === 'object')
        ? (cmd.params_by_name as Record<string, DriverCommandParamV2>)
        : {}
      const paramsText = Object.entries(paramsByName)
        .map(([name, schema]) => `${name} ${safeText(schema?.flag)}`)
        .join(' ')

      const displayId = displayCommandId(activeDriver, id)
      const searchText = `${displayId} ${id} ${label} ${description} ${paramsText}`.toLowerCase()

      if (query && !searchText.includes(query)) {
        continue
      }
      if (riskFilter !== 'any' && risk !== riskFilter) {
        continue
      }
      if (scopeFilter !== 'any' && scope !== scopeFilter) {
        continue
      }
      if (onlyModified && !hasOverrides) {
        continue
      }
      if (hideDisabled && disabled) {
        continue
      }

      items.push({
        id,
        display_id: displayId,
        label,
        description,
        scope,
        risk_level: risk,
        disabled,
        has_overrides: hasOverrides,
        search_text: searchText,
      })
    }

    items.sort((a, b) => a.display_id.localeCompare(b.display_id))
    return items
  }, [activeDriver, draftEffectiveCommandsById, hideDisabled, onlyModified, overridesById, riskFilter, scopeFilter, search])

  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandListItem[]> = {}
    for (const item of commands) {
      const key = groupKeyForCommand(activeDriver, item.id)
      if (!groups[key]) {
        groups[key] = []
      }
      groups[key].push(item)
    }
    const keys = Object.keys(groups).sort()
    return { keys, groups }
  }, [activeDriver, commands])

  const overridesCounts = useMemo(() => {
    const commandIds = Object.keys(overridesById)
    let paramsCount = 0
    let permissionsCount = 0
    for (const commandId of commandIds) {
      const patch = overridesById[commandId]
      if (patch?.permissions) {
        permissionsCount += 1
      }
      const paramsByName = (patch?.params_by_name && typeof patch.params_by_name === 'object')
        ? (patch.params_by_name as Record<string, unknown>)
        : {}
      paramsCount += Object.keys(paramsByName).length
    }
    const driverSchemaCount = Object.keys(overridesDriverSchema).length > 0 ? 1 : 0
    return { commands: commandIds.length, params: paramsCount, permissions: permissionsCount, driver_schema: driverSchemaCount }
  }, [overridesById, overridesDriverSchema])

  const issuesForSelected = useMemo(() => {
    if (!selectedCommandId) return []
    return validateIssues.filter((issue) => issue.command_id === selectedCommandId || issue.command_id === displayCommandId(activeDriver, selectedCommandId))
  }, [activeDriver, selectedCommandId, validateIssues])

  const globalIssues = useMemo(() => validateIssues.filter((issue) => !issue.command_id), [validateIssues])

  return {
    mode,
    setMode,
    activeDriver,
    setActiveDriver,
    rawDirty,
    setRawDirty,
    loading,
    error,
    view,
    fetchView,
    serverOverrides,
    draftOverrides,
    setDraftOverrides,
    selectedCommandId,
    setSelectedCommandId,
    selectedEffective,
    selectedBase,
    selectedPatch,
    search,
    setSearch,
    riskFilter,
    setRiskFilter,
    scopeFilter,
    setScopeFilter,
    onlyModified,
    setOnlyModified,
    hideDisabled,
    setHideDisabled,
    activeEditorTab,
    setActiveEditorTab,
    activeSideTab,
    setActiveSideTab,
    saveOpen,
    setSaveOpen,
    saveReason,
    setSaveReason,
    saving,
    setSaving,
    importItsOpen,
    setImportItsOpen,
    importItsReason,
    setImportItsReason,
    importItsFile,
    setImportItsFile,
    importingIts,
    setImportingIts,
    rollbackOpen,
    setRollbackOpen,
    rollbackReason,
    setRollbackReason,
    rollbackLoading,
    setRollbackLoading,
    rollingBack,
    setRollingBack,
    rollbackVersions,
    setRollbackVersions,
    rollbackVersion,
    setRollbackVersion,
    promoteOpen,
    setPromoteOpen,
    promoteReason,
    setPromoteReason,
    promoting,
    setPromoting,
    previewMode,
    setPreviewMode,
    previewConnectionText,
    setPreviewConnectionText,
    previewConnectionError,
    setPreviewConnectionError,
    previewParams,
    setPreviewParams,
    previewArgsText,
    setPreviewArgsText,
    previewLoading,
    setPreviewLoading,
    previewError,
    setPreviewError,
    previewArgv,
    setPreviewArgv,
    previewArgvMasked,
    setPreviewArgvMasked,
    diffLoading,
    setDiffLoading,
    diffError,
    setDiffError,
    diffItems,
    setDiffItems,
    validateLoading,
    setValidateLoading,
    validateError,
    setValidateError,
    validateIssues,
    setValidateIssues,
    validateSummary,
    setValidateSummary,
    driverSchemaText,
    setDriverSchemaText,
    driverSchemaTextError,
    setDriverSchemaTextError,
    copyLatestDriverSchemaLoading,
    setCopyLatestDriverSchemaLoading,
    overridesCounts,
    dirty,
    hasUnsavedChanges,
    canPromoteLatest,
    commands,
    groupedCommands,
    baseCommandsById,
    overridesById,
    issuesForSelected,
    globalIssues,
  }
}

export type CommandSchemasState = ReturnType<typeof useCommandSchemasState>
