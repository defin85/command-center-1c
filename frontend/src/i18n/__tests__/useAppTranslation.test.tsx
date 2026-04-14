import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  usePoolFactualTranslation,
  usePoolsTranslation,
  useSystemStatusTranslation,
  useWorkflowTranslation,
} from '../useAppTranslation'
import { changeLanguage, ensureNamespaces, i18n } from '../runtime'

describe('useAppTranslation', () => {
  beforeEach(async () => {
    await changeLanguage('en')
    i18n.removeResourceBundle('en', 'systemStatus')
    i18n.removeResourceBundle('ru', 'systemStatus')
  })

  afterEach(async () => {
    await ensureNamespaces('ru', 'systemStatus')
    await ensureNamespaces('en', 'systemStatus')
    await ensureNamespaces('ru', 'pools')
    await ensureNamespaces('en', 'pools')
    await ensureNamespaces('ru', 'poolFactual')
    await ensureNamespaces('en', 'poolFactual')
    await ensureNamespaces('ru', 'workflows')
    await ensureNamespaces('en', 'workflows')
    await changeLanguage('ru')
  })

  it('waits for lazy namespace catalogs before reporting ready', async () => {
    const { result } = renderHook(() => useSystemStatusTranslation())

    expect(result.current.ready).toBe(false)

    await waitFor(() => expect(result.current.ready).toBe(true))

    expect(result.current.t(($) => $.header.title)).toBe('System status')
  })

  it('exposes pools and workflows translations once their route namespaces are loaded', async () => {
    await ensureNamespaces('en', 'pools')
    await ensureNamespaces('en', 'poolFactual')
    await ensureNamespaces('en', 'workflows')

    const poolsHook = renderHook(() => usePoolsTranslation())
    const poolFactualHook = renderHook(() => usePoolFactualTranslation())
    const workflowsHook = renderHook(() => useWorkflowTranslation())

    expect(poolsHook.result.current.ready).toBe(true)
    expect(poolFactualHook.result.current.ready).toBe(true)
    expect(workflowsHook.result.current.ready).toBe(true)

    expect(poolsHook.result.current.t('executionPacks.page.title')).toBe('Execution Packs')
    expect(poolFactualHook.result.current.t('page.title')).toBe('Pool Factual Monitoring')
    expect(workflowsHook.result.current.t('list.page.title')).toBe('Workflow Scheme Library')
  })
})
