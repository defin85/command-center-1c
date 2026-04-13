import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { resolveLocalizedApiErrorMessage } from '../errorMessages'
import { changeLanguage } from '../runtime'

describe('localized API error messages', () => {
  beforeEach(async () => {
    await changeLanguage('ru')
  })

  afterEach(async () => {
    await changeLanguage('ru')
  })

  it('maps known problem codes through the canonical i18n catalog', () => {
    expect(resolveLocalizedApiErrorMessage({ code: 'POOL_WORKFLOW_BINDING_REQUIRED' })).toBe(
      'Перед продолжением выберите workflow binding.',
    )
  })

  it('falls back to a generic localized message plus diagnostic detail for unknown codes', async () => {
    await changeLanguage('en')

    expect(resolveLocalizedApiErrorMessage({
      code: 'UNMAPPED_ERROR',
      detail: 'backend detail',
    })).toBe('Something went wrong. Please try again. backend detail')
  })

  it('uses transport and status fallbacks when no problem-code mapping exists', async () => {
    await changeLanguage('en')

    expect(resolveLocalizedApiErrorMessage({})).toBe('Network error. Check your connection and try again.')
    expect(resolveLocalizedApiErrorMessage({ status: 503 })).toBe(
      'Service temporarily unavailable. Please try again.',
    )
  })
})
