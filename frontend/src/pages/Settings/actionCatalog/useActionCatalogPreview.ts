import { useCallback, useState } from 'react'

import { apiClient } from '../../../api/client'
import type { PlainObject } from '../actionCatalogTypes'
import { isPlainObject } from '../actionCatalogUtils'

export type ActionCatalogPreviewState = {
  open: boolean
  title: string
  loading: boolean
  error: string | null
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

    setPreviewModal({ open: true, title: `Preview: ${String(action.id ?? 'action')}`, loading: true, error: null, payload: null })
    try {
      const response = await apiClient.post('/api/v2/ui/execution-plan/preview/', {
        executor,
        database_ids: [],
      })
      setPreviewModal((current) => ({ ...current, loading: false, payload: response.data as unknown }))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'preview failed'
      setPreviewModal((current) => ({ ...current, loading: false, error: msg }))
    }
  }, [actionsEditable, draftParsed])

  return { previewModal, closePreview, openPreview }
}

