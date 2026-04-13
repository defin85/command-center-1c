import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useSystemStatusTranslation } from '../useAppTranslation'
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
    await changeLanguage('ru')
  })

  it('waits for lazy namespace catalogs before reporting ready', async () => {
    const { result } = renderHook(() => useSystemStatusTranslation())

    expect(result.current.ready).toBe(false)

    await waitFor(() => expect(result.current.ready).toBe(true))

    expect(result.current.t(($) => $.header.title)).toBe('System status')
  })
})
