import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Alert, App, Button, Card, Checkbox, Divider, Form, Input, Modal, Select, Space, Switch, Tabs, Tag, Typography, Upload } from 'antd'
import type { UploadProps } from 'antd'
import { ReloadOutlined, RollbackOutlined, SaveOutlined, UploadOutlined } from '@ant-design/icons'

import type { DriverCatalogV2, DriverCommandParamV2, DriverCommandV2 } from '../../api/driverCommands'
import {
  diffCommandSchemas,
  getCommandSchemasEditorView,
  importItsCommandSchemas,
  listCommandSchemaVersions,
  previewCommandSchemas,
  rollbackCommandSchemaOverrides,
  updateCommandSchemaOverrides,
  validateCommandSchemas,
  type CommandSchemaCommandPatch,
  type CommandSchemaDriver,
  type CommandSchemaIssue,
  type CommandSchemasDiffItem,
  type CommandSchemasOverridesCatalogV2,
  type CommandSchemaVersionListItem,
} from '../../api/commandSchemas'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'
import { CommandSchemasRawEditor } from './CommandSchemasRawEditor'

const { Title, Text } = Typography

const buildEmptyOverrides = (driver: CommandSchemaDriver): CommandSchemasOverridesCatalogV2 => ({
  catalog_version: 2,
  driver,
  overrides: { commands_by_id: {} },
})

const deepCopy = <T,>(value: T): T => {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch (_err) {
    return value
  }
}

const isPlainObject = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const deepMergeObject = (target: Record<string, unknown>, patch: Record<string, unknown>): void => {
  for (const [key, value] of Object.entries(patch)) {
    const current = target[key]
    if (isPlainObject(value) && isPlainObject(current)) {
      deepMergeObject(current, value)
      continue
    }
    target[key] = value
  }
}

const safeCommandsById = (catalog: DriverCatalogV2 | undefined | null): Record<string, DriverCommandV2> => {
  if (!catalog || typeof catalog !== 'object') return {}
  const commandsById = (catalog as { commands_by_id?: unknown }).commands_by_id
  if (!commandsById || typeof commandsById !== 'object') return {}
  return commandsById as Record<string, DriverCommandV2>
}

const safeOverridesById = (
  catalog: CommandSchemasOverridesCatalogV2 | undefined | null
): Record<string, CommandSchemaCommandPatch> => {
  if (!catalog || typeof catalog !== 'object') return {}
  const overrides = (catalog as { overrides?: unknown }).overrides
  if (!overrides || typeof overrides !== 'object') return {}
  const commandsById = (overrides as { commands_by_id?: unknown }).commands_by_id
  if (!commandsById || typeof commandsById !== 'object') return {}
  return commandsById as Record<string, CommandSchemaCommandPatch>
}

const safeText = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

const normalizeStringList = (raw: unknown): string[] => {
  if (!Array.isArray(raw)) return []
  const out = raw
    .map((item) => safeText(item).trim())
    .filter((item) => item.length > 0)
  return Array.from(new Set(out)).sort()
}

const displayCommandId = (driver: CommandSchemaDriver, commandId: string): string => {
  if (driver === 'ibcmd' && commandId.startsWith('ibcmd.')) {
    return commandId.slice('ibcmd.'.length)
  }
  return commandId
}

const groupKeyForCommand = (driver: CommandSchemaDriver, commandId: string): string => {
  const display = displayCommandId(driver, commandId)
  if (driver === 'cli') {
    return 'CLI'
  }
  const parts = display.split('.').filter((part) => part.length > 0)
  if (parts.length === 0) return 'Other'
  return `${parts[0]}.*`
}

type CommandListItem = {
  id: string
  display_id: string
  label: string
  description: string
  scope: string
  risk_level: string
  disabled: boolean
  has_overrides: boolean
  search_text: string
}

export function CommandSchemasPage() {
  const { message, modal } = App.useApp()
  const [searchParams, setSearchParams] = useSearchParams()

  type CommandSchemasMode = 'guided' | 'raw'

  const [mode, setMode] = useState<CommandSchemasMode>(() => (
    (searchParams.get('mode') || '').trim().toLowerCase() === 'raw' ? 'raw' : 'guided'
  ))

  const [activeDriver, setActiveDriver] = useState<CommandSchemaDriver>(() => {
    const raw = (searchParams.get('driver') || '').trim().toLowerCase()
    return raw === 'cli' ? 'cli' : 'ibcmd'
  })

  const [rawDirty, setRawDirty] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<Awaited<ReturnType<typeof getCommandSchemasEditorView>> | null>(null)

  const [serverOverrides, setServerOverrides] = useState<CommandSchemasOverridesCatalogV2>(buildEmptyOverrides('ibcmd'))
  const [draftOverrides, setDraftOverrides] = useState<CommandSchemasOverridesCatalogV2>(buildEmptyOverrides('ibcmd'))
  const [selectedCommandId, setSelectedCommandId] = useState<string>('')

  const [search, setSearch] = useState('')
  const [riskFilter, setRiskFilter] = useState<'any' | 'safe' | 'dangerous'>('any')
  const [scopeFilter, setScopeFilter] = useState<'any' | 'per_database' | 'global'>('any')
  const [onlyModified, setOnlyModified] = useState(false)
  const [hideDisabled, setHideDisabled] = useState(false)

  const [activeEditorTab, setActiveEditorTab] = useState<'basics' | 'permissions' | 'params' | 'advanced'>('basics')
  const [activeSideTab, setActiveSideTab] = useState<'preview' | 'diff' | 'validate'>('preview')

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

  const [previewMode, setPreviewMode] = useState<'guided' | 'manual'>('guided')
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
  const [validateSummary, setValidateSummary] = useState<{ ok: boolean; errors: number; warnings: number } | null>(null)

  const fetchView = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getCommandSchemasEditorView(activeDriver, mode)
      setView(data)

      const server = data.catalogs?.overrides ?? buildEmptyOverrides(activeDriver)
      setServerOverrides(server)
      setDraftOverrides(deepCopy(server))

      const effectiveCommands = safeCommandsById(data.catalogs?.effective?.catalog)
      const firstId = Object.keys(effectiveCommands).sort()[0] ?? ''
      setSelectedCommandId((prev) => (prev && effectiveCommands[prev] ? prev : firstId))
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
      const text = err instanceof Error ? err.message : 'Failed to load command schemas'
      setError(text)
    } finally {
      setLoading(false)
    }
  }, [activeDriver, mode])

  useEffect(() => {
    void fetchView()
  }, [fetchView])

  useEffect(() => {
    setSearchParams({ driver: activeDriver, mode }, { replace: true })
  }, [activeDriver, mode, setSearchParams])

  const baseCatalog = view?.catalogs?.base

  const baseCommandsById = useMemo(() => safeCommandsById(baseCatalog), [baseCatalog])
  const overridesById = useMemo(() => safeOverridesById(draftOverrides), [draftOverrides])

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
    return { commands: commandIds.length, params: paramsCount, permissions: permissionsCount }
  }, [overridesById])

  const setCommandPatch = useCallback((commandId: string, updater: (patch: CommandSchemaCommandPatch) => void) => {
    setDraftOverrides((prev) => {
      const next = deepCopy(prev)
      const commandsById = next.overrides.commands_by_id
      const current = commandsById[commandId] ?? {}
      const patch = deepCopy(current)
      updater(patch)
      if (Object.keys(patch).length === 0) {
        delete commandsById[commandId]
      } else {
        commandsById[commandId] = patch
      }
      return next
    })
  }, [])

  const resetCommandPatch = useCallback((commandId: string) => {
    setDraftOverrides((prev) => {
      const next = deepCopy(prev)
      delete next.overrides.commands_by_id[commandId]
      return next
    })
  }, [])

  const discardChanges = useCallback(() => {
    modal.confirm({
      title: 'Discard unsaved changes?',
      content: 'This will reset local overrides to the current active version.',
      okText: 'Discard',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: () => {
        setDraftOverrides(deepCopy(serverOverrides))
        message.success('Changes discarded')
      },
    })
  }, [message, modal, serverOverrides])

  const requestDriverChange = useCallback((nextDriver: CommandSchemaDriver) => {
    if (nextDriver === activeDriver) {
      return
    }

    if (saving || rollbackLoading || rollingBack) {
      message.info('Please wait until the current action finishes')
      return
    }

    if (!hasUnsavedChanges) {
      setActiveDriver(nextDriver)
      return
    }

    modal.confirm({
      title: 'Unsaved changes',
      content: 'You have unsaved changes. Save or discard them before switching the driver.',
      okText: 'Discard and switch',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: () => {
        setActiveDriver(nextDriver)
      },
    })
  }, [activeDriver, hasUnsavedChanges, message, modal, rollbackLoading, rollingBack, saving])

  const requestRefreshView = useCallback(() => {
    if (saving || rollingBack) {
      message.info('Please wait until the current action finishes')
      return
    }

    if (!hasUnsavedChanges) {
      void fetchView()
      return
    }

    modal.confirm({
      title: 'Unsaved changes',
      content: 'Refresh will discard your local draft and reload the current active version.',
      okText: 'Discard and refresh',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: () => {
        void fetchView()
      },
    })
  }, [fetchView, hasUnsavedChanges, message, modal, rollingBack, saving])

  const openImportIts = useCallback(() => {
    if (saving || rollbackLoading || rollingBack || loading) {
      message.info('Please wait until the current action finishes')
      return
    }

    const open = () => {
      setImportItsOpen(true)
      setImportItsReason('')
      setImportItsFile(null)
      setImportingIts(false)
    }

    if (!hasUnsavedChanges) {
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
  }, [hasUnsavedChanges, loading, message, modal, rollbackLoading, rollingBack, saving])

  const handleImportItsFile: UploadProps['beforeUpload'] = (file) => {
    setImportItsFile(file)
    return false
  }

  const handleImportIts = async () => {
    if (importingIts) {
      return
    }

    const reason = saveText(importItsReason)
    if (!reason) {
      message.error('Reason is required')
      return
    }
    if (!importItsFile) {
      message.error('Select ITS JSON file')
      return
    }

    let itsPayload: Record<string, unknown>
    try {
      const rawText = await importItsFile.text()
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
        if (!section || typeof section !== 'object') {
          return false
        }
        const blocks = (section as { blocks?: unknown }).blocks
        return Array.isArray(blocks) && blocks.length > 0
      })
    const hasCliCommandBlocks = Array.isArray(sections)
      && sections.some((section) => {
        if (!section || typeof section !== 'object') {
          return false
        }
        const blocks = (section as { blocks?: unknown }).blocks
        if (!Array.isArray(blocks)) {
          return false
        }
        return blocks.some((block) => {
          if (!block || typeof block !== 'object') {
            return false
          }
          const cls = String((block as { class?: unknown }).class ?? '')
          return cls.includes('Lang-parameter')
        })
      })

    if (!hasBlocks || (activeDriver === 'cli' && !hasCliCommandBlocks)) {
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
                Re-export with <Text code>python scripts/dev/its-scrape.py --with-blocks --no-raw-text</Text> for best
                results.
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
      if (!ok) {
        return
      }
    }

    setImportingIts(true)
    try {
      await importItsCommandSchemas({ driver: activeDriver, its_payload: itsPayload, save: true, reason })
      message.success('ITS imported')
      setImportItsOpen(false)
      await fetchView()
    } catch (error) {
      const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
      const backendMessage = typeof err?.response?.data?.error === 'string'
        ? err.response?.data?.error
        : err?.response?.data?.error?.message
      message.error(backendMessage || 'Failed to import ITS')
    } finally {
      setImportingIts(false)
    }
  }

  const openRollback = async () => {
    setRollbackOpen(true)
    setRollbackReason('')
    setRollbackVersion('')
    setRollbackVersions([])
    setRollbackLoading(true)
    setRollingBack(false)
    try {
      const response = await listCommandSchemaVersions(activeDriver, 'overrides', { limit: 200, offset: 0 })
      setRollbackVersions(response.versions ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to load overrides versions'
      message.error(text)
    } finally {
      setRollbackLoading(false)
    }
  }

  const handleRollback = async () => {
    if (!view) {
      return
    }
    const reason = saveText(rollbackReason)
    if (!reason) {
      message.error('Reason is required')
      return
    }
    if (!rollbackVersion) {
      message.error('Select version to rollback')
      return
    }

    setRollingBack(true)
    try {
      await rollbackCommandSchemaOverrides({
        driver: activeDriver,
        version: rollbackVersion,
        reason,
        expected_etag: view.etag,
      })
      message.success('Rollback applied')
      setRollbackOpen(false)
      await fetchView()
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
            void fetchView()
          },
        })
      } else {
        const text = err instanceof Error ? err.message : 'Failed to rollback overrides'
        message.error(text)
      }
    } finally {
      setRollingBack(false)
    }
  }

  const openSave = () => {
    setSaveOpen(true)
    setSaveReason('')
  }

  const handleSave = async () => {
    if (!view) {
      return
    }
    const reason = saveText(saveReason)
    if (!reason) {
      message.error('Reason is required')
      return
    }

    setSaving(true)
    try {
      await updateCommandSchemaOverrides({
        driver: activeDriver,
        catalog: draftOverrides,
        reason,
        expected_etag: view.etag,
      })
      message.success('Overrides saved')
      setSaveOpen(false)
      await fetchView()
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
            void fetchView()
          },
        })
      } else {
        const text = err instanceof Error ? err.message : 'Failed to save overrides'
        message.error(text)
      }
    } finally {
      setSaving(false)
    }
  }

  const loadDiff = async () => {
    if (!selectedCommandId) {
      return
    }
    setDiffLoading(true)
    setDiffError(null)
    try {
      const response = await diffCommandSchemas({ driver: activeDriver, command_id: selectedCommandId, catalog: draftOverrides })
      setDiffItems(response.changes ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to load diff'
      setDiffError(text)
      setDiffItems([])
    } finally {
      setDiffLoading(false)
    }
  }

  const runValidate = async () => {
    setValidateLoading(true)
    setValidateError(null)
    try {
      const response = await validateCommandSchemas({ driver: activeDriver, catalog: draftOverrides })
      setValidateIssues(response.issues ?? [])
      setValidateSummary({ ok: Boolean(response.ok), errors: response.errors_count ?? 0, warnings: response.warnings_count ?? 0 })
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to validate'
      setValidateError(text)
      setValidateIssues([])
      setValidateSummary(null)
    } finally {
      setValidateLoading(false)
    }
  }

  const buildPreview = async () => {
    if (!selectedCommandId) {
      return
    }
    setPreviewLoading(true)
    setPreviewError(null)
    try {
      const additionalArgs = previewArgsText
        .split('\n')
        .map((item) => item.trim())
        .filter((item) => item.length > 0)
      const response = await previewCommandSchemas({
        driver: activeDriver,
        command_id: selectedCommandId,
        mode: previewMode,
        params: previewParams,
        additional_args: additionalArgs,
        catalog: draftOverrides,
      })
      setPreviewArgv(response.argv ?? [])
      setPreviewArgvMasked(response.argv_masked ?? [])
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to build preview'
      setPreviewError(text)
      setPreviewArgv([])
      setPreviewArgvMasked([])
    } finally {
      setPreviewLoading(false)
    }
  }

  const issuesForSelected = useMemo(() => {
    if (!selectedCommandId) return []
    return validateIssues.filter((issue) => issue.command_id === selectedCommandId || issue.command_id === displayCommandId(activeDriver, selectedCommandId))
  }, [activeDriver, selectedCommandId, validateIssues])

  const renderCommandList = () => (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Input.Search
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search id/label/description/flags"
        allowClear
      />
      <Space wrap>
        <Select
          value={riskFilter}
          onChange={(v) => setRiskFilter(v)}
          style={{ width: 140 }}
          options={[
            { value: 'any', label: 'Risk: any' },
            { value: 'safe', label: 'Risk: safe' },
            { value: 'dangerous', label: 'Risk: dangerous' },
          ]}
        />
        <Select
          value={scopeFilter}
          onChange={(v) => setScopeFilter(v)}
          style={{ width: 160 }}
          options={[
            { value: 'any', label: 'Scope: any' },
            { value: 'per_database', label: 'Scope: per_database' },
            { value: 'global', label: 'Scope: global' },
          ]}
        />
        <Checkbox checked={onlyModified} onChange={(e) => setOnlyModified(e.target.checked)}>
          Only modified
        </Checkbox>
        <Checkbox checked={hideDisabled} onChange={(e) => setHideDisabled(e.target.checked)}>
          Hide disabled
        </Checkbox>
      </Space>
      <Text type="secondary">Commands: {commands.length}</Text>

      <div style={{ maxHeight: 720, overflow: 'auto', paddingRight: 6 }}>
        {groupedCommands.keys.map((groupKey) => (
          <div key={groupKey} style={{ marginBottom: 10 }}>
            <Text type="secondary">{groupKey} ({groupedCommands.groups[groupKey].length})</Text>
            <div style={{ marginTop: 6 }}>
              {groupedCommands.groups[groupKey].map((item) => {
                const selected = item.id === selectedCommandId
                return (
                  <div
                    key={item.id}
                    data-testid={`command-schemas-command-${item.id}`}
                    onClick={() => {
                      setSelectedCommandId(item.id)
                      setActiveEditorTab('basics')
                      setActiveSideTab('preview')
                      setPreviewParams({})
                      setPreviewArgsText('')
                      setPreviewArgv([])
                      setPreviewArgvMasked([])
                      setPreviewError(null)
                      setDiffItems([])
                      setDiffError(null)
                    }}
                    style={{
                      cursor: 'pointer',
                      border: '1px solid #f0f0f0',
                      borderRadius: 8,
                      padding: 10,
                      marginBottom: 8,
                      background: selected ? '#e6f4ff' : '#fff',
                    }}
                  >
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Space wrap>
                        <Text strong>{item.display_id}</Text>
                        {item.has_overrides && <Tag color="blue">overrides</Tag>}
                        {item.disabled && <Tag>disabled</Tag>}
                        {item.risk_level === 'dangerous' && <Tag color="red">dangerous</Tag>}
                        {item.scope === 'global' && <Tag color="geekblue">global</Tag>}
                      </Space>
                      {item.description && (
                        <Text type="secondary" ellipsis={{ tooltip: item.description }}>{item.description}</Text>
                      )}
                    </Space>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </Space>
  )

  const renderBasicsEditor = () => {
    if (!selectedCommandId || !selectedEffective) {
      return <Alert type="info" message="Select a command from the list" showIcon />
    }

    const displayId = displayCommandId(activeDriver, selectedCommandId)
    const patch = selectedPatch ?? {}
    const labelOver = Object.prototype.hasOwnProperty.call(patch, 'label')
    const descOver = Object.prototype.hasOwnProperty.call(patch, 'description')
    const scopeOver = Object.prototype.hasOwnProperty.call(patch, 'scope')
    const riskOver = Object.prototype.hasOwnProperty.call(patch, 'risk_level')
    const disabledOver = Object.prototype.hasOwnProperty.call(patch, 'disabled')

    const currentLabel = labelOver ? safeText(patch.label) : safeText(selectedEffective.label)
    const currentDesc = descOver ? safeText(patch.description) : safeText(selectedEffective.description)
    const currentScope = scopeOver ? safeText(patch.scope).toLowerCase() : safeText(selectedEffective.scope).toLowerCase()
    const currentRisk = riskOver ? safeText(patch.risk_level).toLowerCase() : safeText(selectedEffective.risk_level).toLowerCase()
    const currentDisabled = disabledOver ? Boolean(patch.disabled) : Boolean(selectedEffective.disabled)

    const baseRisk = safeText(selectedBase?.risk_level).toLowerCase()
    const baseDisabled = Boolean(selectedBase?.disabled)

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space align="baseline" wrap style={{ justifyContent: 'space-between', width: '100%' }}>
          <Space direction="vertical" size={0}>
            <Text type="secondary">Command id</Text>
            <Text code>{displayId}</Text>
          </Space>
          <Button onClick={() => resetCommandPatch(selectedCommandId)} disabled={!selectedPatch}>
            Reset command
          </Button>
        </Space>

        <Divider style={{ margin: '8px 0' }} />

        <Form layout="vertical">
          <Space wrap style={{ width: '100%' }}>
            <div style={{ flex: 1, minWidth: 260 }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Text>Label</Text>
                <Space size="small">
                  <Text type="secondary">Override</Text>
                  <Switch
                    data-testid="command-schemas-basics-label-override"
                    size="small"
                    checked={labelOver}
                    onChange={(checked) => {
                      setCommandPatch(selectedCommandId, (p) => {
                        if (checked) {
                          p.label = safeText(selectedEffective.label).trim() || selectedCommandId
                        } else {
                          delete p.label
                        }
                      })
                    }}
                  />
                </Space>
              </Space>
              <Input
                data-testid="command-schemas-basics-label-input"
                value={currentLabel}
                disabled={!labelOver}
                onChange={(e) => setCommandPatch(selectedCommandId, (p) => { p.label = e.target.value })}
              />
            </div>

            <div style={{ width: 220 }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Text>Scope</Text>
                <Space size="small">
                  <Text type="secondary">Override</Text>
                  <Switch
                    size="small"
		                    checked={scopeOver}
		                    onChange={(checked) => {
		                      setCommandPatch(selectedCommandId, (p) => {
		                        if (checked) {
		                          p.scope = selectedEffective.scope
		                        } else {
		                          delete p.scope
		                        }
		                      })
		                    }}
		                  />
                </Space>
              </Space>
		              <Select
		                value={currentScope || undefined}
		                disabled={!scopeOver}
	                onChange={(value) => setCommandPatch(selectedCommandId, (p) => { p.scope = value as DriverCommandV2['scope'] })}
	                options={[
	                  { value: 'per_database', label: 'per_database' },
	                  { value: 'global', label: 'global' },
	                ]}
	              />
            </div>

            <div style={{ width: 220 }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Text>Risk</Text>
                <Space size="small">
                  <Text type="secondary">Override</Text>
	                  <Switch
	                    size="small"
		                    checked={riskOver}
		                    onChange={(checked) => {
                          if (checked) {
		                        setCommandPatch(selectedCommandId, (p) => {
                                p.risk_level = selectedEffective.risk_level
		                        })
                            return
                          }

                          const beforeRisk = currentRisk
                          const afterRisk = baseRisk
                          const beforeKnown = beforeRisk === 'safe' || beforeRisk === 'dangerous'
                          const afterKnown = afterRisk === 'safe' || afterRisk === 'dangerous'

                          if (beforeKnown && afterKnown && beforeRisk !== afterRisk) {
                            const nextRisk = afterRisk as DriverCommandV2['risk_level']
                            const title = nextRisk === 'dangerous' ? 'Confirm risk level: dangerous' : 'Confirm risk level: safe'
                            const content = nextRisk === 'dangerous'
                              ? `You are setting risk_level to "dangerous" for ${displayId}. This may require additional approvals.`
                              : `You are setting risk_level to "safe" for ${displayId}. Make sure this is correct.`
                            modal.confirm({
                              title,
                              content,
                              okText: 'Apply',
                              cancelText: 'Cancel',
                              onOk: () => {
                                setCommandPatch(selectedCommandId, (p) => {
                                  delete p.risk_level
                                })
                              },
                            })
                            return
                          }

		                      setCommandPatch(selectedCommandId, (p) => {
                              delete p.risk_level
		                      })
		                    }}
		                  />
	                </Space>
	              </Space>
		              <Select
		                value={currentRisk || undefined}
		                disabled={!riskOver}
		                onChange={(value) => {
                      const nextRisk = value as DriverCommandV2['risk_level']
                      const prevRisk = currentRisk
                      if (nextRisk && (prevRisk === 'safe' || prevRisk === 'dangerous') && prevRisk !== nextRisk) {
                        const title = nextRisk === 'dangerous' ? 'Confirm risk level: dangerous' : 'Confirm risk level: safe'
                        const content = nextRisk === 'dangerous'
                          ? `You are setting risk_level to "dangerous" for ${displayId}. This may require additional approvals.`
                          : `You are setting risk_level to "safe" for ${displayId}. Make sure this is correct.`
                        modal.confirm({
                          title,
                          content,
                          okText: 'Apply',
                          cancelText: 'Cancel',
                          onOk: () => {
                            setCommandPatch(selectedCommandId, (p) => { p.risk_level = nextRisk })
                          },
                        })
                        return
                      }
                      setCommandPatch(selectedCommandId, (p) => { p.risk_level = nextRisk })
                    }}
		                options={[
		                  { value: 'safe', label: 'safe' },
		                  { value: 'dangerous', label: 'dangerous' },
		                ]}
		              />
            </div>

            <div style={{ width: 220 }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Text>Disabled</Text>
                <Space size="small">
                  <Text type="secondary">Override</Text>
	                  <Switch
	                    size="small"
	                    checked={disabledOver}
	                    onChange={(checked) => {
                        if (checked) {
	                      setCommandPatch(selectedCommandId, (p) => {
	                          p.disabled = Boolean(selectedEffective.disabled)
	                      })
                          return
                        }

                        const beforeDisabled = currentDisabled
                        const afterDisabled = baseDisabled
                        if (beforeDisabled && !afterDisabled) {
                          modal.confirm({
                            title: 'Enable disabled command?',
                            content: `You are enabling ${displayId}. This may expose a previously disabled operation.`,
                            okText: 'Enable',
                            cancelText: 'Cancel',
                            onOk: () => {
                              setCommandPatch(selectedCommandId, (p) => {
                                delete p.disabled
                              })
                            },
                          })
                          return
                        }

	                      setCommandPatch(selectedCommandId, (p) => {
                            delete p.disabled
	                      })
	                    }}
	                  />
	                </Space>
	              </Space>
	              <Switch
	                checked={currentDisabled}
	                disabled={!disabledOver}
	                onChange={(checked) => {
                    if (currentDisabled && !checked) {
                      modal.confirm({
                        title: 'Enable disabled command?',
                        content: `You are enabling ${displayId}. This may expose a previously disabled operation.`,
                        okText: 'Enable',
                        cancelText: 'Cancel',
                        onOk: () => {
                          setCommandPatch(selectedCommandId, (p) => { p.disabled = checked })
                        },
                      })
                      return
                    }
                    setCommandPatch(selectedCommandId, (p) => { p.disabled = checked })
                  }}
	              />
            </div>
          </Space>

          <div style={{ marginTop: 12 }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Text>Description</Text>
              <Space size="small">
                <Text type="secondary">Override</Text>
                <Switch
                  size="small"
                  checked={descOver}
                  onChange={(checked) => {
                    setCommandPatch(selectedCommandId, (p) => {
                      if (checked) {
                        p.description = safeText(selectedEffective.description)
                      } else {
                        delete p.description
                      }
                    })
                  }}
                />
              </Space>
            </Space>
            <Input.TextArea
              value={currentDesc}
              disabled={!descOver}
              onChange={(e) => setCommandPatch(selectedCommandId, (p) => { p.description = e.target.value })}
              rows={4}
            />
          </div>
        </Form>

        {selectedBase && (
          <Text type="secondary">
            Base label: {safeText(selectedBase.label).trim() || '-'}; scope: {safeText(selectedBase.scope)}; risk: {safeText(selectedBase.risk_level)}
          </Text>
        )}
      </Space>
    )
  }

  const renderPermissionsEditor = () => {
    if (!selectedCommandId || !selectedEffective) {
      return <Alert type="info" message="Select a command from the list" showIcon />
    }

    const displayId = displayCommandId(activeDriver, selectedCommandId)
    const patch = selectedPatch ?? {}
    const permissionsOver = Object.prototype.hasOwnProperty.call(patch, 'permissions')
    const basePermissionsRaw = (selectedBase?.permissions && typeof selectedBase.permissions === 'object')
      ? (selectedBase.permissions as Record<string, unknown>)
      : {}
    const effectivePermissionsRaw = (selectedEffective.permissions && typeof selectedEffective.permissions === 'object')
      ? (selectedEffective.permissions as Record<string, unknown>)
      : {}

    const baseAllowedRoles = normalizeStringList(basePermissionsRaw.allowed_roles)
    const baseDeniedRoles = normalizeStringList(basePermissionsRaw.denied_roles)
    const baseAllowedEnvs = normalizeStringList(basePermissionsRaw.allowed_envs)
    const baseDeniedEnvs = normalizeStringList(basePermissionsRaw.denied_envs)
    const baseMinDbLevel = safeText(basePermissionsRaw.min_db_level).toLowerCase() || ''

    const allowedRoles = normalizeStringList(effectivePermissionsRaw.allowed_roles)
    const deniedRoles = normalizeStringList(effectivePermissionsRaw.denied_roles)
    const allowedEnvs = normalizeStringList(effectivePermissionsRaw.allowed_envs)
    const deniedEnvs = normalizeStringList(effectivePermissionsRaw.denied_envs)
    const minDbLevel = safeText(effectivePermissionsRaw.min_db_level).toLowerCase() || ''

    const permissionsChangedFromBase = (
      JSON.stringify(allowedRoles) !== JSON.stringify(baseAllowedRoles)
      || JSON.stringify(deniedRoles) !== JSON.stringify(baseDeniedRoles)
      || JSON.stringify(allowedEnvs) !== JSON.stringify(baseAllowedEnvs)
      || JSON.stringify(deniedEnvs) !== JSON.stringify(baseDeniedEnvs)
      || minDbLevel !== baseMinDbLevel
    )

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {permissionsChangedFromBase && (
          <Alert
            type="warning"
            showIcon
            message="Permissions/env constraints changed"
            description="You changed who can run the command and/or in which environments. Review carefully."
          />
        )}
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Space direction="vertical" size={0}>
            <Text strong>Permissions</Text>
            <Text type="secondary">Optional constraints for roles/envs and min DB level.</Text>
          </Space>
          <Space size="small">
            <Text type="secondary">Override</Text>
	            <Switch
	              size="small"
	              checked={permissionsOver}
	              onChange={(checked) => {
                  if (checked) {
                    setCommandPatch(selectedCommandId, (p) => {
                      p.permissions = {
                        allowed_roles: allowedRoles,
                        denied_roles: deniedRoles,
                        allowed_envs: allowedEnvs,
                        denied_envs: deniedEnvs,
                        min_db_level: (minDbLevel === 'operate' || minDbLevel === 'manage' || minDbLevel === 'admin')
                          ? (minDbLevel as 'operate' | 'manage' | 'admin')
                          : undefined,
                      }
                    })
                    return
                  }

                  const changed = permissionsChangedFromBase
                  if (changed) {
                    modal.confirm({
                      title: 'Permissions/env constraints changed',
                      content: `This will change permissions/env constraints for ${displayId}.`,
                      okText: 'Apply',
                      cancelText: 'Cancel',
                      onOk: () => {
                        setCommandPatch(selectedCommandId, (p) => {
                          delete p.permissions
                        })
                      },
                    })
                    return
                  }

                  setCommandPatch(selectedCommandId, (p) => {
                    delete p.permissions
                  })
	              }}
	            />
	          </Space>
	        </Space>

        <Form layout="vertical">
          <Form.Item label="Allowed roles">
            <Select
              mode="tags"
              value={allowedRoles}
              disabled={!permissionsOver}
              onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                if (!p.permissions) p.permissions = {}
                p.permissions.allowed_roles = value
              })}
              tokenSeparators={[',']}
              placeholder="e.g. staff, operators"
            />
          </Form.Item>
          <Form.Item label="Denied roles">
            <Select
              mode="tags"
              value={deniedRoles}
              disabled={!permissionsOver}
              onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                if (!p.permissions) p.permissions = {}
                p.permissions.denied_roles = value
              })}
              tokenSeparators={[',']}
              placeholder="e.g. guests"
            />
          </Form.Item>
          <Form.Item label="Allowed envs">
            <Select
              mode="tags"
              value={allowedEnvs}
              disabled={!permissionsOver}
              onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                if (!p.permissions) p.permissions = {}
                p.permissions.allowed_envs = value
              })}
              tokenSeparators={[',']}
              placeholder="e.g. prod, stage"
            />
          </Form.Item>
          <Form.Item label="Denied envs">
            <Select
              mode="tags"
              value={deniedEnvs}
              disabled={!permissionsOver}
              onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                if (!p.permissions) p.permissions = {}
                p.permissions.denied_envs = value
              })}
              tokenSeparators={[',']}
              placeholder="e.g. dev"
            />
          </Form.Item>
          <Form.Item label="Min DB level">
            <Select
              value={minDbLevel || undefined}
              disabled={!permissionsOver}
              onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                if (!p.permissions) p.permissions = {}
                p.permissions.min_db_level = (value || undefined) as 'operate' | 'manage' | 'admin' | undefined
              })}
              allowClear
              options={[
                { value: 'operate', label: 'operate' },
                { value: 'manage', label: 'manage' },
                { value: 'admin', label: 'admin' },
              ]}
            />
          </Form.Item>
        </Form>
      </Space>
    )
  }

  const renderParamsEditor = () => {
    if (!selectedCommandId || !selectedEffective) {
      return <Alert type="info" message="Select a command from the list" showIcon />
    }

    const effectiveParams = (selectedEffective.params_by_name && typeof selectedEffective.params_by_name === 'object')
      ? (selectedEffective.params_by_name as Record<string, DriverCommandParamV2>)
      : {}
    const patchParamsByName = (selectedPatch?.params_by_name && typeof selectedPatch.params_by_name === 'object')
      ? (selectedPatch.params_by_name as Record<string, Partial<DriverCommandParamV2>>)
      : {}

    const names = Object.keys(effectiveParams).sort()
    if (names.length === 0) {
      return <Alert type="info" showIcon message="No params for this command" />
    }

    return (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {names.map((name) => {
          const effectiveParam = effectiveParams[name]
          const baseParam = selectedBase?.params_by_name && typeof selectedBase.params_by_name === 'object'
            ? (selectedBase.params_by_name as Record<string, DriverCommandParamV2>)[name]
            : undefined
          const paramOver = Object.prototype.hasOwnProperty.call(patchParamsByName, name)
          const patchParam = paramOver ? patchParamsByName[name] : {}

          const currentKind = paramOver ? safeText(patchParam.kind) : safeText(effectiveParam.kind)
          const currentRequired = paramOver ? Boolean(patchParam.required) : Boolean(effectiveParam.required)
          const currentExpects = paramOver ? Boolean(patchParam.expects_value) : Boolean(effectiveParam.expects_value)
          const currentFlag = paramOver ? safeText(patchParam.flag) : safeText(effectiveParam.flag)
          const currentPosition = paramOver ? Number(patchParam.position) : Number(effectiveParam.position)
          const currentEnum = paramOver ? normalizeStringList(patchParam.enum) : normalizeStringList(effectiveParam.enum)

          return (
            <Card
              key={name}
              size="small"
              title={<Space wrap><Text code>{name}</Text>{effectiveParam.required && <Tag color="red">required</Tag>}</Space>}
              extra={(
                <Space size="small">
                  <Text type="secondary">Override</Text>
                  <Switch
                    size="small"
                    checked={paramOver}
                    onChange={(checked) => {
                      setCommandPatch(selectedCommandId, (p) => {
                        if (!p.params_by_name) p.params_by_name = {}
                        if (checked) {
                          p.params_by_name[name] = deepCopy(baseParam ?? effectiveParam)
                        } else {
                          delete p.params_by_name[name]
                          if (Object.keys(p.params_by_name).length === 0) {
                            delete p.params_by_name
                          }
                        }
                      })
                    }}
                  />
                </Space>
              )}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space wrap>
                  <div style={{ width: 220 }}>
                    <Text type="secondary">Kind</Text>
                    <Select
                      value={currentKind || undefined}
                      disabled={!paramOver}
                      onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                        if (!p.params_by_name) p.params_by_name = {}
                        if (!p.params_by_name[name]) p.params_by_name[name] = {}
                        p.params_by_name[name].kind = value as 'flag' | 'positional'
                      })}
                      options={[
                        { value: 'flag', label: 'flag' },
                        { value: 'positional', label: 'positional' },
                      ]}
                    />
                  </div>
                  <div style={{ width: 220 }}>
                    <Text type="secondary">Required</Text>
                    <Switch
                      checked={currentRequired}
                      disabled={!paramOver}
                      onChange={(checked) => setCommandPatch(selectedCommandId, (p) => {
                        if (!p.params_by_name) p.params_by_name = {}
                        if (!p.params_by_name[name]) p.params_by_name[name] = {}
                        p.params_by_name[name].required = checked
                      })}
                    />
                  </div>
                  <div style={{ width: 220 }}>
                    <Text type="secondary">Expects value</Text>
                    <Switch
                      checked={currentExpects}
                      disabled={!paramOver}
                      onChange={(checked) => setCommandPatch(selectedCommandId, (p) => {
                        if (!p.params_by_name) p.params_by_name = {}
                        if (!p.params_by_name[name]) p.params_by_name[name] = {}
                        p.params_by_name[name].expects_value = checked
                      })}
                    />
                  </div>
                </Space>

                {currentKind === 'flag' && (
                  <div style={{ width: 340 }}>
                    <Text type="secondary">Flag</Text>
                    <Input
                      value={currentFlag}
                      disabled={!paramOver}
                      onChange={(e) => setCommandPatch(selectedCommandId, (p) => {
                        if (!p.params_by_name) p.params_by_name = {}
                        if (!p.params_by_name[name]) p.params_by_name[name] = {}
                        p.params_by_name[name].flag = e.target.value
                      })}
                      placeholder="--flag"
                    />
                  </div>
                )}

                {currentKind === 'positional' && (
                  <div style={{ width: 220 }}>
                    <Text type="secondary">Position</Text>
                    <Input
                      value={Number.isFinite(currentPosition) ? String(currentPosition) : ''}
                      disabled={!paramOver}
                      onChange={(e) => {
                        const raw = e.target.value.trim()
                        const num = raw ? Number(raw) : NaN
                        setCommandPatch(selectedCommandId, (p) => {
                          if (!p.params_by_name) p.params_by_name = {}
                          if (!p.params_by_name[name]) p.params_by_name[name] = {}
                          p.params_by_name[name].position = Number.isFinite(num) ? num : undefined
                        })
                      }}
                      placeholder="1"
                    />
                  </div>
                )}

                <div style={{ width: '100%' }}>
                  <Text type="secondary">Enum</Text>
                  <Select
                    mode="tags"
                    value={currentEnum}
                    disabled={!paramOver}
                    onChange={(value) => setCommandPatch(selectedCommandId, (p) => {
                      if (!p.params_by_name) p.params_by_name = {}
                      if (!p.params_by_name[name]) p.params_by_name[name] = {}
                      p.params_by_name[name].enum = value
                    })}
                    tokenSeparators={[',']}
                    placeholder="Allowed values (optional)"
                  />
                </div>
              </Space>
            </Card>
          )
        })}
      </Space>
    )
  }

  const renderAdvancedEditor = () => {
    if (!selectedCommandId) {
      return <Alert type="info" showIcon message="Select a command from the list" />
    }
    const patch = overridesById[selectedCommandId] ?? {}
    const base = selectedBase ?? {}
    const effective = selectedEffective ?? {}

    return (
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Card size="small" title="Command patch (draft overrides)">
          <LazyJsonCodeEditor
            value={JSON.stringify(patch, null, 2)}
            onChange={() => {}}
            height={260}
            path={`command-schemas-${activeDriver}-${selectedCommandId}-patch.json`}
          />
        </Card>
        <Card size="small" title="Base command (read-only)">
          <LazyJsonCodeEditor
            value={JSON.stringify(base, null, 2)}
            onChange={() => {}}
            height={260}
            path={`command-schemas-${activeDriver}-${selectedCommandId}-base.json`}
          />
        </Card>
        <Card size="small" title="Effective command (read-only)">
          <LazyJsonCodeEditor
            value={JSON.stringify(effective, null, 2)}
            onChange={() => {}}
            height={260}
            path={`command-schemas-${activeDriver}-${selectedCommandId}-effective.json`}
          />
        </Card>
      </Space>
    )
  }

  const renderSidePanel = () => {
    if (!selectedCommandId || !selectedEffective) {
      return <Alert type="info" message="Select a command to preview/diff" showIcon />
    }

    const paramsByName = (selectedEffective.params_by_name && typeof selectedEffective.params_by_name === 'object')
      ? (selectedEffective.params_by_name as Record<string, DriverCommandParamV2>)
      : {}

    const paramNames = Object.keys(paramsByName).sort()

    return (
      <Tabs
        activeKey={activeSideTab}
        onChange={(key) => setActiveSideTab(key as 'preview' | 'diff' | 'validate')}
        items={[
          {
            key: 'preview',
            label: 'Preview',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Space wrap>
                  <Select
                    value={previewMode}
                    onChange={(v) => setPreviewMode(v)}
                    style={{ width: 140 }}
                    options={[
                      { value: 'guided', label: 'guided' },
                      { value: 'manual', label: 'manual' },
                    ]}
                  />
                  <Button onClick={buildPreview} loading={previewLoading}>
                    Build argv
                  </Button>
                </Space>

                {paramNames.length > 0 && (
                  <Card size="small" title="Params">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
	                      {paramNames.map((name) => {
	                        const schema = paramsByName[name]
	                        const expectsValue = Boolean(schema.expects_value)
	                        const kind = safeText(schema.kind)
	                        const isRequired = Boolean(schema.required)
	                        const isSensitive = Boolean(schema.sensitive)
	                        const enumValues = normalizeStringList(schema.enum)
	                        const currentValue = previewParams[name]

                        const setValue = (value: unknown) => {
                          setPreviewParams((prev) => ({ ...prev, [name]: value }))
                        }

                        return (
                          <div key={name}>
	                            <Space wrap>
	                              <Text code>{name}</Text>
	                              {isRequired && <Tag color="red">required</Tag>}
	                              {isSensitive && <Tag color="orange">sensitive</Tag>}
	                              {kind === 'flag' && safeText(schema.flag) && <Tag>{safeText(schema.flag)}</Tag>}
	                              {kind === 'positional' && Number.isFinite(Number(schema.position)) && (
	                                <Tag>pos {Number(schema.position)}</Tag>
	                              )}
	                            </Space>
                            <div style={{ marginTop: 6 }}>
                              {!expectsValue ? (
                                <Switch
                                  checked={Boolean(currentValue)}
                                  onChange={(checked) => setValue(checked)}
                                />
                              ) : enumValues.length > 0 ? (
                                <Select
                                  value={safeText(currentValue) || undefined}
                                  onChange={(v) => setValue(v)}
                                  style={{ width: '100%' }}
                                  options={enumValues.map((v) => ({ value: v, label: v }))}
                                  allowClear
                                />
	                              ) : isSensitive ? (
	                                <Input.Password
	                                  value={safeText(currentValue)}
	                                  onChange={(e) => setValue(e.target.value)}
	                                  placeholder="value"
	                                />
	                              ) : (
	                                <Input
	                                  value={safeText(currentValue)}
	                                  onChange={(e) => setValue(e.target.value)}
	                                  placeholder="value"
	                                />
	                              )}
	                            </div>
	                          </div>
	                        )
	                      })}
                    </Space>
                  </Card>
                )}

                <Card size="small" title="Additional args (one per line)">
                  <Input.TextArea
                    value={previewArgsText}
                    onChange={(e) => setPreviewArgsText(e.target.value)}
                    rows={4}
                    placeholder="--extra\n--flag=value"
                  />
                </Card>

                {previewError && <Alert type="warning" showIcon message="Preview error" description={previewError} />}

                <Card size="small" title="argv">
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    {previewArgv.length === 0 ? (
                      <Text type="secondary">No preview yet</Text>
                    ) : (
                      previewArgv.map((line, idx) => <Text key={idx} code>{line}</Text>)
                    )}
                  </Space>
                </Card>
                <Card size="small" title="argv_masked">
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    {previewArgvMasked.length === 0 ? (
                      <Text type="secondary">No preview yet</Text>
                    ) : (
                      previewArgvMasked.map((line, idx) => <Text key={idx} code>{line}</Text>)
                    )}
                  </Space>
                </Card>
              </Space>
            ),
          },
          {
            key: 'diff',
            label: 'Diff',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button onClick={loadDiff} loading={diffLoading}>
                  Load diff (base to effective)
                </Button>
                {diffError && <Alert type="warning" showIcon message="Diff error" description={diffError} />}
                <div style={{ maxHeight: 620, overflow: 'auto' }}>
                  <Card size="small" title={`Changes (${diffItems.length})`}>
                    {diffItems.length === 0 ? (
                      <Text type="secondary">No changes</Text>
                    ) : (
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left', padding: '6px 8px' }}>Path</th>
                              <th style={{ textAlign: 'left', padding: '6px 8px' }}>Base</th>
                              <th style={{ textAlign: 'left', padding: '6px 8px' }}>Effective</th>
                            </tr>
                          </thead>
                          <tbody>
                            {diffItems.map((row) => (
                              <tr key={row.path}>
                                <td style={{ padding: '6px 8px', verticalAlign: 'top' }}><Text code>{row.path}</Text></td>
                                <td style={{ padding: '6px 8px', verticalAlign: 'top' }}>
                                  {row.base_present ? <Text>{safeText(JSON.stringify(row.base))}</Text> : <Text type="secondary">-</Text>}
                                </td>
                                <td style={{ padding: '6px 8px', verticalAlign: 'top' }}>
                                  {row.effective_present ? <Text>{safeText(JSON.stringify(row.effective))}</Text> : <Text type="secondary">-</Text>}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </div>
              </Space>
            ),
          },
          {
            key: 'validate',
            label: 'Validate',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Button onClick={runValidate} loading={validateLoading}>
                  Validate effective catalog
                </Button>
                {validateError && <Alert type="warning" showIcon message="Validation error" description={validateError} />}
                {validateSummary && (
                  <Alert
                    type={validateSummary.ok ? 'success' : 'warning'}
                    showIcon
                    message={validateSummary.ok ? 'OK' : 'Validation failed'}
                    description={`errors=${validateSummary.errors}, warnings=${validateSummary.warnings}`}
                  />
                )}
                <Card size="small" title={`Issues for selected command (${issuesForSelected.length})`}>
                  {issuesForSelected.length === 0 ? (
                    <Text type="secondary">No issues</Text>
                  ) : (
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      {issuesForSelected.map((issue, idx) => (
                        <Alert
                          key={`${issue.code}-${idx}`}
                          type={issue.severity === 'error' ? 'error' : 'warning'}
                          showIcon
                          message={`${issue.code}: ${issue.message}`}
                          description={issue.path ? <Text code>{issue.path}</Text> : undefined}
                        />
                      ))}
                    </Space>
                  )}
                </Card>
              </Space>
            ),
          },
        ]}
      />
    )
  }

  return (
    <div data-testid="command-schemas-page">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <Title level={2} style={{ marginBottom: 0 }}>Command Schemas</Title>
          <Text type="secondary">Human-oriented editor for driver command schemas (MinIO artifacts).</Text>
        </div>
        <Space wrap>
          <Space size="small" align="center">
            <Text type="secondary">Mode</Text>
            <Switch
              checked={mode === 'raw'}
              onChange={(checked) => setMode(checked ? 'raw' : 'guided')}
              checkedChildren="Raw"
              unCheckedChildren="Guided"
              disabled={loading}
            />
          </Space>
          <Button data-testid="command-schemas-refresh" onClick={requestRefreshView} loading={loading} icon={<ReloadOutlined />}>
            Refresh
          </Button>
          <Button
            data-testid="command-schemas-import-its-open"
            onClick={openImportIts}
            disabled={loading || saving || rollingBack || rollbackLoading}
            icon={<UploadOutlined />}
          >
            Import ITS...
          </Button>
          <Button data-testid="command-schemas-rollback-open" onClick={openRollback} disabled={!view} icon={<RollbackOutlined />}>
            Rollback...
          </Button>
          {mode === 'guided' && (
            <Button data-testid="command-schemas-save-open" type="primary" icon={<SaveOutlined />} onClick={openSave} disabled={!view || !dirty || saving}>
              Save...
            </Button>
          )}
        </Space>
      </div>

      {mode === 'guided' && dirty && (
        <div data-testid="command-schemas-unsaved-banner" style={{ position: 'sticky', top: 0, zIndex: 20, background: '#fff' }}>
          <Alert
            type="warning"
            showIcon
            message="Unsaved changes"
            description={`commands=${overridesCounts.commands}, params=${overridesCounts.params}, permissions=${overridesCounts.permissions}`}
            action={(
              <Space>
                <Button size="small" onClick={discardChanges} disabled={saving}>
                  Discard
                </Button>
                <Button size="small" type="primary" onClick={openSave} disabled={saving}>
                  Save...
                </Button>
              </Space>
            )}
          />
        </div>
      )}

      {error && (
        <Alert type="warning" message="Failed to load command schemas" description={error} showIcon />
      )}

      <Tabs
        activeKey={activeDriver}
        onChange={(key) => requestDriverChange(key as CommandSchemaDriver)}
        items={[
          { key: 'ibcmd', label: 'IBCMD' },
          { key: 'cli', label: 'CLI' },
        ]}
      />

      {view && (
        <Alert
          type="info"
          showIcon
          message="Versions"
          description={(
            <Space direction="vertical" size={2}>
              <Text type="secondary">Base approved: {view.base.approved_version ?? '-'}</Text>
              <Text type="secondary">Base latest: {view.base.latest_version ?? '-'}</Text>
              <Text type="secondary">Overrides active: {view.overrides.active_version ?? '-'}</Text>
              <Text type="secondary">ETag: {view.etag}</Text>
            </Space>
          )}
        />
      )}

      {mode === 'guided' ? (
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
              {renderCommandList()}
            </Card>

            <Card
              size="small"
              title={selectedCommandId ? `Editor: ${displayCommandId(activeDriver, selectedCommandId)}` : 'Editor'}
            >
              <Tabs
                activeKey={activeEditorTab}
                onChange={(key) => setActiveEditorTab(key as 'basics' | 'permissions' | 'params' | 'advanced')}
                items={[
                  { key: 'basics', label: 'Basics', children: renderBasicsEditor() },
                  { key: 'permissions', label: 'Permissions', children: renderPermissionsEditor() },
                  { key: 'params', label: 'Params', children: renderParamsEditor() },
                  { key: 'advanced', label: 'Advanced', children: renderAdvancedEditor() },
                ]}
              />
            </Card>

            <Card size="small" title="Preview / Diff / Validate">
              {renderSidePanel()}
            </Card>
          </div>

          <Modal
            title="Save overrides"
            open={saveOpen}
            onCancel={() => setSaveOpen(false)}
            onOk={handleSave}
            okText="Save"
            okButtonProps={{ disabled: !saveReason.trim() || saving, 'data-testid': 'command-schemas-save-confirm' }}
            cancelButtonProps={{ disabled: saving }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Alert
                type="info"
                showIcon
                message="Summary"
                description={`commands=${overridesCounts.commands}, params=${overridesCounts.params}, permissions=${overridesCounts.permissions}`}
              />
              <Text type="secondary">Reason (required)</Text>
              <Input.TextArea
                data-testid="command-schemas-save-reason"
                value={saveReason}
                onChange={(e) => setSaveReason(e.target.value)}
                placeholder="Why are you changing command schemas?"
                rows={4}
              />
            </Space>
          </Modal>
        </>
      ) : (
        <CommandSchemasRawEditor
          driver={activeDriver}
          view={view}
          disabled={loading || importingIts || rollbackLoading || rollingBack}
          onReload={fetchView}
          onDirtyChange={setRawDirty}
        />
      )}

      <Modal
        title={`Import ITS JSON (${activeDriver.toUpperCase()})`}
        open={importItsOpen}
        onCancel={() => setImportItsOpen(false)}
        onOk={handleImportIts}
        okText="Import"
        okButtonProps={{
          disabled: importingIts || !importItsFile || !importItsReason.trim(),
          loading: importingIts,
          'data-testid': 'command-schemas-import-its-confirm',
        }}
        cancelButtonProps={{ disabled: importingIts }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="ITS export"
            description={(
              <Space direction="vertical">
                <Text>Export ITS JSON via scripts/dev/its-scrape.py and upload it here to build base catalog.</Text>
                <Text type="secondary">
                  Recommended: <Text code>python scripts/dev/its-scrape.py --with-blocks --no-raw-text</Text>
                </Text>
              </Space>
            )}
          />
          <Text type="secondary">ITS JSON file</Text>
          <Upload
            accept=".json,application/json"
            showUploadList={false}
            beforeUpload={handleImportItsFile}
            disabled={importingIts}
          >
            <Button icon={<UploadOutlined />} data-testid="command-schemas-import-its-file">
              Select file...
            </Button>
          </Upload>
          {importItsFile && (
            <Text type="secondary">Selected: {importItsFile.name}</Text>
          )}
          <Text type="secondary">Reason (required)</Text>
          <Input.TextArea
            data-testid="command-schemas-import-its-reason"
            value={importItsReason}
            onChange={(e) => setImportItsReason(e.target.value)}
            placeholder="Why import ITS?"
            rows={4}
            disabled={importingIts}
          />
        </Space>
      </Modal>

      <Modal
        title="Rollback overrides"
        open={rollbackOpen}
        onCancel={() => setRollbackOpen(false)}
        onOk={handleRollback}
        okText="Rollback"
        okButtonProps={{
          disabled: rollbackLoading || rollingBack || !rollbackVersion || !rollbackReason.trim(),
          'data-testid': 'command-schemas-rollback-confirm',
        }}
        cancelButtonProps={{ disabled: rollbackLoading || rollingBack }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="secondary">Version</Text>
          <Select
            data-testid="command-schemas-rollback-version"
            value={rollbackVersion || undefined}
            onChange={setRollbackVersion}
            loading={rollbackLoading}
            disabled={rollingBack}
            options={rollbackVersions.map((v) => {
              const reasonText = safeText(v.metadata?.['reason']).trim()
              return {
                value: v.version,
                label: `${v.version}${v.created_at ? ` (${v.created_at})` : ''}${v.created_by ? ` by ${v.created_by}` : ''}${reasonText ? ` - ${reasonText}` : ''}`,
              }
            })}
            placeholder="Select overrides version"
            showSearch
            optionFilterProp="label"
          />
          <Text type="secondary">Reason (required)</Text>
          <Input.TextArea
            data-testid="command-schemas-rollback-reason"
            value={rollbackReason}
            onChange={(e) => setRollbackReason(e.target.value)}
            placeholder="Why rollback?"
            rows={4}
            disabled={rollingBack}
          />
        </Space>
      </Modal>
      </Space>
    </div>
  )
}

const saveText = (value: string): string => value.trim()

export default CommandSchemasPage
