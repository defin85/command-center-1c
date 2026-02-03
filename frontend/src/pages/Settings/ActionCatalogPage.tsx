import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Space, Spin, Tag, Typography } from 'antd'

import { useMe } from '../../api/queries/me'
import { getEffectiveRuntimeSettings, updateRuntimeSettingOverride } from '../../api/runtimeSettings'
import type { ActionCatalogMode, ActionFormValues, PlainObject } from './actionCatalogTypes'
import {
  buildActionFromForm,
  buildActionRows,
  computeDiff,
  deepCopy,
  deriveActionFormValues,
  ensureUniqueId,
  extractBackendErrors,
  getCatalogActions,
  isPlainObject,
  normalizeActionId,
  parseJson,
  parseSaveErrorHint,
  safeJsonStringify,
  upsertCatalogActions,
} from './actionCatalogUtils'
import { ActionCatalogEditorModal } from './actionCatalog/ActionCatalogEditorModal'
import { ActionCatalogPreviewModal } from './actionCatalog/ActionCatalogPreviewModal'
import { ActionCatalogTabs } from './actionCatalog/ActionCatalogTabs'
import { validateActionCatalogDraft } from './actionCatalog/actionCatalogValidation'
import { useActionCatalogColumns } from './actionCatalog/useActionCatalogColumns'
import { useActionCatalogPreview } from './actionCatalog/useActionCatalogPreview'

const { Title, Text } = Typography

const ACTION_CATALOG_KEY = 'ui.action_catalog'
const DISABLED_ACTIONS_STORAGE_KEY = 'action-catalog.disabled-actions.v1'
const RESERVED_EXTENSIONS_CAPABILITIES = new Set(['extensions.list', 'extensions.sync'])

export function ActionCatalogPage() {
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)

  const [mode, setMode] = useState<ActionCatalogMode>('guided')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [serverRaw, setServerRaw] = useState<string | null>(null)
  const [draftRaw, setDraftRaw] = useState<string>('{}')
  const [settingDescription, setSettingDescription] = useState<string | null>(null)
  const [settingSource, setSettingSource] = useState<string | null>(null)
  const [disabledActions, setDisabledActions] = useState<PlainObject[]>([])
  const [saveErrors, setSaveErrors] = useState<string[]>([])
  const [saveErrorsDraftActionIds, setSaveErrorsDraftActionIds] = useState<Array<string | null> | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saving, setSaving] = useState(false)

  const [editorOpen, setEditorOpen] = useState(false)
  const [editorTitle, setEditorTitle] = useState('Edit action')
  const [editingPos, setEditingPos] = useState<number | null>(null)
  const [editingBase, setEditingBase] = useState<PlainObject | null>(null)
  const [editorValues, setEditorValues] = useState<ActionFormValues | null>(null)

  const [form] = Form.useForm<ActionFormValues>()

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DISABLED_ACTIONS_STORAGE_KEY)
      if (!raw) {
        setDisabledActions([])
        return
      }
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed)) {
        setDisabledActions(parsed.filter(isPlainObject))
      } else {
        setDisabledActions([])
      }
    } catch (_err) {
      setDisabledActions([])
    }
  }, [])

  useEffect(() => {
    try {
      sessionStorage.setItem(DISABLED_ACTIONS_STORAGE_KEY, JSON.stringify(disabledActions))
    } catch (_err) {
      // ignore storage errors
    }
  }, [disabledActions])

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSaveErrors([])
    setSaveErrorsDraftActionIds(null)
    setSaveSuccess(false)
    try {
      const settings = await getEffectiveRuntimeSettings()
      const entry = settings.find((item) => item.key === ACTION_CATALOG_KEY)
      if (!entry) {
        setError(`RuntimeSetting ${ACTION_CATALOG_KEY} не найден`)
        setServerRaw(null)
        setDraftRaw('{}')
        setSettingDescription(null)
        setSettingSource(null)
        return
      }
      const raw = safeJsonStringify(entry.value)
      setServerRaw(raw)
      setDraftRaw(raw)
      setSettingDescription(entry.description || null)
      setSettingSource(entry.source || null)
    } catch (_err) {
      setError('Не удалось загрузить ui.action_catalog')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isStaff) return
    void loadCatalog()
  }, [isStaff, loadCatalog])

  const dirty = useMemo(() => (
    serverRaw !== null && draftRaw !== serverRaw
  ), [draftRaw, serverRaw])

  const serverParsed = useMemo(() => (serverRaw === null ? null : parseJson(serverRaw)), [serverRaw])
  const draftParsed = useMemo(() => parseJson(draftRaw), [draftRaw])
  const draftIsValidJson = draftParsed !== null
  const actionRows = useMemo(() => buildActionRows(draftParsed), [draftParsed])

  const rawValidation = useMemo(() => validateActionCatalogDraft(draftParsed), [draftParsed])

  const saveErrorHints = useMemo(() => {
    return saveErrors.map((msg) => parseSaveErrorHint(msg, saveErrorsDraftActionIds))
  }, [saveErrors, saveErrorsDraftActionIds])

  const saveErrorsByActionPos = useMemo(() => {
    const map = new Map<number, string[]>()
    for (const item of saveErrorHints) {
      const pos = item.action_pos
      if (typeof pos !== 'number') continue
      const existing = map.get(pos) ?? []
      existing.push(item.message)
      map.set(pos, existing)
    }
    return map
  }, [saveErrorHints])

  const diffItems = useMemo(() => {
    if (!dirty) return []
    if (serverParsed === null || draftParsed === null) return []
    return computeDiff(serverParsed, draftParsed)
  }, [dirty, draftParsed, serverParsed])

  const diffSummary = useMemo(() => {
    const summary = { added: 0, removed: 0, changed: 0 }
    for (const item of diffItems) {
      summary[item.kind] += 1
    }
    return summary
  }, [diffItems])

  const canSave = Boolean(
    isStaff
    && dirty
    && rawValidation.ok
    && isPlainObject(draftParsed)
    && !saving
  )

  const handleSave = useCallback(async () => {
    if (saving) return
    setSaveSuccess(false)
    setSaveErrors([])
    setSaveErrorsDraftActionIds(null)
    setError(null)

    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setSaveErrors(['Draft must be a JSON object'])
      return
    }
    if (parsed.catalog_version !== 1) {
      setSaveErrors(['catalog_version must be 1'])
      return
    }

    const actionIdsByPos: Array<string | null> = []
    const extensions = parsed.extensions
    const actions = isPlainObject(extensions) ? (extensions.actions as unknown) : null
    if (Array.isArray(actions)) {
      for (const item of actions) {
        actionIdsByPos.push(isPlainObject(item) ? normalizeActionId((item as PlainObject).id) : null)
      }
    }
    setSaveErrorsDraftActionIds(actionIdsByPos)
    setSaving(true)
    try {
      const updated = await updateRuntimeSettingOverride(ACTION_CATALOG_KEY, parsed, 'published')
      const nextServerRaw = safeJsonStringify(updated.value)
      setServerRaw(nextServerRaw)
      setDraftRaw(nextServerRaw)
      setSaveSuccess(true)
      setSaveErrors([])
    } catch (err) {
      setSaveErrors(extractBackendErrors(err))
    } finally {
      setSaving(false)
    }
  }, [draftRaw, saving])

  const updateActions = useCallback((updater: (actions: PlainObject[]) => PlainObject[]) => {
    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно применить изменения: draft не является JSON-объектом')
      return
    }
    parsed.catalog_version = 1
    const currentActions = getCatalogActions(parsed)
    const nextActions = updater(deepCopy(currentActions))
    upsertCatalogActions(parsed, nextActions)
    setDraftRaw(safeJsonStringify(parsed))
  }, [draftRaw])

  const openEditor = useCallback((opts: { mode: 'add' | 'edit' | 'copy'; pos?: number }) => {
    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно открыть редактор: draft не является JSON-объектом')
      return
    }
    const actions = getCatalogActions(parsed)
    const pos = typeof opts.pos === 'number' ? opts.pos : null
    const base = (pos !== null && actions[pos]) ? deepCopy(actions[pos]) : null

    const usedIds = new Set(actions.map((a) => (typeof a.id === 'string' ? a.id : '')).filter(Boolean))

    if (opts.mode === 'add') {
      const nextValues = deriveActionFormValues(null)
      setEditorTitle('Add action')
      setEditingPos(null)
      setEditingBase(null)
      setEditorValues(nextValues)
      form.resetFields()
      form.setFieldsValue(nextValues)
      setEditorOpen(true)
      return
    }

    if (!base) {
      setError('Action не найден')
      return
    }

    if (opts.mode === 'edit') {
      const nextValues = deriveActionFormValues(base)
      setEditorTitle('Edit action')
      setEditingPos(pos)
      setEditingBase(base)
      setEditorValues(nextValues)
      form.resetFields()
      form.setFieldsValue(nextValues)
      setEditorOpen(true)
      return
    }

    const copied = deepCopy(base)
    const baseId = typeof copied.id === 'string' ? copied.id : 'action'
    const candidate = `${baseId}.copy`
    copied.id = ensureUniqueId(candidate, usedIds)
    const nextValues = deriveActionFormValues(copied)
    setEditorTitle('Copy action')
    setEditingPos(null)
    setEditingBase(copied)
    setEditorValues(nextValues)
    form.resetFields()
    form.setFieldsValue(nextValues)
    setEditorOpen(true)
  }, [draftRaw, form])

  const closeEditor = useCallback(() => {
    setEditorOpen(false)
    setEditingPos(null)
    setEditingBase(null)
    setEditorValues(null)
    form.resetFields()
  }, [form])

  const submitEditor = useCallback(async () => {
    const values = await form.validateFields()

    const parsed = parseJson(draftRaw)
    if (!isPlainObject(parsed)) {
      setError('Невозможно применить изменения: draft не является JSON-объектом')
      return
    }
    parsed.catalog_version = 1

    const actions = getCatalogActions(parsed)
    const next = buildActionFromForm(editingBase, values)
    const trimmedId = typeof next.id === 'string' ? next.id.trim() : ''

    const usedIds = new Set(
      actions
        .map((a) => (typeof a.id === 'string' ? a.id.trim() : ''))
        .filter(Boolean)
    )

    if (editingPos !== null) {
      const currentId = typeof actions[editingPos]?.id === 'string' ? String(actions[editingPos].id).trim() : ''
      usedIds.delete(currentId)
    }

	    if (!trimmedId || usedIds.has(trimmedId)) {
	      form.setFields([{ name: 'id', errors: ['ID уже используется'] }])
	      return
	    }

	    const reserved = (() => {
	      const cap = typeof next.capability === 'string' ? next.capability.trim() : ''
	      if (cap && RESERVED_EXTENSIONS_CAPABILITIES.has(cap)) return { field: 'capability' as const, value: cap }
	      if (!cap && RESERVED_EXTENSIONS_CAPABILITIES.has(trimmedId)) return { field: 'id' as const, value: trimmedId }
	      return null
	    })()
	    if (reserved) {
	      const conflictPos = actions.findIndex((a, idx) => {
	        if (editingPos !== null && idx === editingPos) return false
	        const aCap = normalizeActionId(a.capability)
	        if (aCap && RESERVED_EXTENSIONS_CAPABILITIES.has(aCap)) return aCap === reserved.value
	        const aId = normalizeActionId(a.id)
	        if (!aCap && aId && RESERVED_EXTENSIONS_CAPABILITIES.has(aId)) return aId === reserved.value
	        return false
	      })
	      if (conflictPos >= 0) {
	        const conflictId = normalizeActionId(actions[conflictPos]?.id) ?? `#${conflictPos + 1}`
	        const message = `Зарезервированная capability уже используется: ${reserved.value} (action.id=${conflictId})`
	        form.setFields([{ name: reserved.field, errors: [message] }])
	        return
	      }
	    }

	    const nextActions = [...actions]
	    if (editingPos !== null) {
	      nextActions[editingPos] = next
	    } else {
      nextActions.push(next)
    }
    upsertCatalogActions(parsed, nextActions)
    setDraftRaw(safeJsonStringify(parsed))
    closeEditor()
  }, [closeEditor, draftRaw, editingBase, editingPos, form])

  const moveAction = useCallback((pos: number, delta: -1 | 1) => {
    updateActions((actions) => {
      const nextPos = pos + delta
      if (nextPos < 0 || nextPos >= actions.length) return actions
      const next = [...actions]
      const tmp = next[pos]
      next[pos] = next[nextPos]
      next[nextPos] = tmp
      return next
    })
  }, [updateActions])

  const disableAction = useCallback((pos: number) => {
    updateActions((actions) => {
      const target = actions[pos]
      if (!target) return actions
      setDisabledActions((current) => [...current, deepCopy(target)])
      return actions.filter((_item, idx) => idx !== pos)
    })
  }, [updateActions])

  const restoreLastDisabled = useCallback(() => {
    setDisabledActions((current) => {
      if (current.length === 0) return current
      const last = deepCopy(current[current.length - 1])
      const remaining = current.slice(0, -1)

      updateActions((actions) => {
        const usedIds = new Set(
          actions
            .map((a) => (typeof a.id === 'string' ? a.id : ''))
            .filter(Boolean)
        )
        const id = typeof last.id === 'string' ? last.id : 'action'
        last.id = ensureUniqueId(id, usedIds)
        return [...actions, last]
      })

      return remaining
    })
  }, [updateActions])

  const actionsEditable = isStaff && draftIsValidJson && isPlainObject(draftParsed)

  const {
    previewModal,
    closePreview,
    openPreview,
    runPreview,
    setPreviewDatabaseIds,
  } = useActionCatalogPreview(actionsEditable, draftParsed)

  const columns = useActionCatalogColumns({
    actionRowsLength: actionRows.length,
    actionsEditable,
    saveErrorsByActionPos,
    moveAction,
    openEditor: ({ mode, pos }) => openEditor({ mode, pos }),
    openPreview: (pos) => void openPreview(pos),
    disableAction,
  })

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <div>
        <Space size="middle" align="center" wrap>
          <Title level={2} style={{ marginBottom: 0 }}>Action Catalog</Title>
          <Text type="secondary">
            RuntimeSetting <Text code>{ACTION_CATALOG_KEY}</Text>
          </Text>
          {dirty && <Tag color="orange">Draft</Tag>}
          {settingSource === 'tenant_override' && <Tag color="blue">Tenant override</Tag>}
          {settingSource === 'global' && <Tag>Global</Tag>}
          {settingSource === 'default' && <Tag>Default</Tag>}
        </Space>
        {settingDescription && (
          <Text type="secondary" style={{ display: 'block' }}>{settingDescription}</Text>
        )}
      </div>

      {error && <Alert type="error" showIcon message={error} />}
      {saveErrors.length > 0 && (
        <Alert
          type="error"
          showIcon
          message="Save failed"
          description={(
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {saveErrorHints.map((item, idx) => (
                <li key={`${idx}:${item.message}`}>
                  <Text>{item.message}</Text>
                  {item.action_id && (
                    <Text type="secondary">{` (action_id=${item.action_id})`}</Text>
                  )}
                </li>
              ))}
            </ul>
          )}
        />
      )}
      {saveSuccess && (
        <Alert
          type="success"
          showIcon
          closable
          message="Saved"
          onClose={() => setSaveSuccess(false)}
        />
      )}

      <Card size="small">
        <Space wrap>
          <Button onClick={loadCatalog} disabled={loading || dirty} data-testid="action-catalog-reload">
            Reload
          </Button>
          <Button
            type="primary"
            onClick={() => void handleSave()}
            disabled={!canSave}
            loading={saving}
            data-testid="action-catalog-save"
          >
            Save
          </Button>
          {dirty && (
            <Text type="secondary">Reload disabled while draft has unsaved changes.</Text>
          )}
        </Space>
      </Card>

      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : (
        <ActionCatalogTabs
          mode={mode}
          onModeChange={setMode}
          actionCatalogKey={ACTION_CATALOG_KEY}
          actionRows={actionRows}
          columns={columns}
          draftIsValidJson={draftIsValidJson}
          dirty={dirty}
          actionsEditable={actionsEditable}
          disabledActionsCount={disabledActions.length}
          saveErrorHints={saveErrorHints}
          onAddAction={() => openEditor({ mode: 'add' })}
          onRestoreLastDisabled={restoreLastDisabled}
          rawValidation={rawValidation}
          diffItems={diffItems}
          diffSummary={diffSummary}
          draftRaw={draftRaw}
          onDraftRawChange={setDraftRaw}
          serverRaw={serverRaw}
        />
      )}

      <ActionCatalogEditorModal
        open={editorOpen}
        title={editorTitle}
        form={form}
        initialValues={editorValues}
        onCancel={closeEditor}
        onApply={() => void submitEditor()}
      />

      <ActionCatalogPreviewModal
        previewModal={previewModal}
        onClose={closePreview}
        onRun={() => void runPreview()}
        onDatabaseIdsChange={setPreviewDatabaseIds}
      />
    </Space>
  )
}
