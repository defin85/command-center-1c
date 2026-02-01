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
  })

  const closePreview = useCallback(() => {
    setPreviewModal({ open: false, title: 'Preview', loading: false, error: null, payload: null })
  }, [])

  const openPreview = useCallback(async (pos: number) => {
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

    const hasIbcmdConnection = (conn: unknown): boolean => {
      if (!isPlainObject(conn)) return false
      const c = conn as PlainObject
      const hasRemote = typeof c.remote === 'string' && c.remote.trim().length > 0
      const hasPid = typeof c.pid === 'number'
      const hasOffline = isPlainObject(c.offline)
      return hasRemote || hasPid || hasOffline
    }

    setPreviewModal({ open: true, title: `Preview: ${String(action.id ?? 'action')}`, loading: true, error: null, payload: null })
    try {
      const previewExecutor: PlainObject = (
        executor.kind === 'ibcmd_cli' && !hasIbcmdConnection((executor as PlainObject).connection)
          ? { ...executor, connection: { offline: {} } }
          : executor
      )
      const response = await apiClient.post('/api/v2/ui/execution-plan/preview/', {
        executor: previewExecutor,
        database_ids: [],
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
  }, [actionsEditable, draftParsed])

  return { previewModal, closePreview, openPreview }
}
