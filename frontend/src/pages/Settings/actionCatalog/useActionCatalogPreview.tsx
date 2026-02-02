import { useCallback, useState, type ReactNode } from 'react'

import { apiClient } from '../../../api/client'
import type { PlainObject } from '../actionCatalogTypes'
import { isPlainObject } from '../actionCatalogUtils'
import { parseIbcmdCliUiError } from '../../../components/ibcmd/ibcmdCliUiErrors'

export type ActionCatalogPreviewState = {
  open: boolean
  title: string
  loading: boolean
  error: ReactNode | null
  payload: unknown | null
  actionPos: number | null
  executorKind: string | null
  databaseIds: string[]
}

export const useActionCatalogPreview = (
  actionsEditable: boolean,
  draftParsed: unknown
) => {
  const [previewModal, setPreviewModal] = useState<ActionCatalogPreviewState>({
    open: false,
    title: 'Preview',
    loading: false,
    error: null,
    payload: null,
    actionPos: null,
    executorKind: null,
    databaseIds: [],
  })

  const closePreview = useCallback(() => {
    setPreviewModal((current) => ({
      ...current,
      open: false,
      title: 'Preview',
      loading: false,
      error: null,
      payload: null,
      actionPos: null,
      executorKind: null,
      databaseIds: [],
    }))
  }, [])

  const openPreview = useCallback((pos: number) => {
    if (!actionsEditable) return
    const parsed = draftParsed
    if (!parsed || typeof parsed !== 'object') return
    const root = parsed as PlainObject
    const extensions = root.extensions
    if (!isPlainObject(extensions)) return
    const actions = (extensions as PlainObject).actions
    if (!Array.isArray(actions)) return
    const action = actions[pos]
    if (!isPlainObject(action)) return
    const executor = action.executor
    if (!isPlainObject(executor)) return

    const executorKind = typeof executor.kind === 'string' ? executor.kind : null
    setPreviewModal((current) => ({
      ...current,
      open: true,
      title: `Preview: ${String(action.id ?? 'action')}`,
      loading: false,
      error: null,
      payload: null,
      actionPos: pos,
      executorKind,
      databaseIds: [],
    }))
  }, [actionsEditable, draftParsed])

  const setPreviewDatabaseIds = useCallback((databaseIds: string[]) => {
    setPreviewModal((current) => ({ ...current, databaseIds }))
  }, [])

  const runPreview = useCallback(async () => {
    if (!actionsEditable) return
    const pos = previewModal.actionPos
    if (pos === null || pos === undefined) return
    const parsed = draftParsed
    if (!parsed || typeof parsed !== 'object') return
    const root = parsed as PlainObject
    const extensions = root.extensions
    if (!isPlainObject(extensions)) return
    const actions = (extensions as PlainObject).actions
    if (!Array.isArray(actions)) return
    const action = actions[pos]
    if (!isPlainObject(action)) return
    const executor = action.executor
    if (!isPlainObject(executor)) return

    const kind = typeof executor.kind === 'string' ? executor.kind : ''
    const databaseIds = Array.isArray(previewModal.databaseIds) ? previewModal.databaseIds : []
    if (kind === 'ibcmd_cli' && databaseIds.length === 0) {
      setPreviewModal((current) => ({
        ...current,
        error: 'Для Preview ibcmd_cli нужно выбрать базу (или набор баз), так как connection резолвится per database.',
        payload: null,
        loading: false,
      }))
      return
    }

    setPreviewModal((current) => ({ ...current, loading: true, error: null, payload: null }))
    try {
      const response = await apiClient.post('/api/v2/ui/execution-plan/preview/', {
        executor,
        database_ids: databaseIds,
      })
      setPreviewModal((current) => ({ ...current, loading: false, payload: response.data as unknown }))
    } catch (e: unknown) {
      const parsed = parseIbcmdCliUiError(e)
      const fallback: ReactNode = (e instanceof Error ? e.message : 'preview failed')
      const errNode: ReactNode = parsed ? (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>{parsed.title}</div>
          {parsed.content}
        </div>
      ) : fallback
      setPreviewModal((current) => ({ ...current, loading: false, error: errNode }))
    }
  }, [actionsEditable, draftParsed, previewModal.actionPos, previewModal.databaseIds])

  return { previewModal, closePreview, openPreview, runPreview, setPreviewDatabaseIds }
}
