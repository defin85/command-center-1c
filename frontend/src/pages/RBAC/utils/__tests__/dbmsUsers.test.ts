import { describe, it, expect } from 'vitest'

import { getDbmsAuthTypeLabel, getDbmsPasswordConfiguredLabel, validateDbmsUserId } from '../dbmsUsers'

describe('dbmsUsers utils', () => {
  it('validates user_id for actor vs service mapping', () => {
    expect(validateDbmsUserId(false, null)).toBe('required')
    expect(validateDbmsUserId(false, undefined)).toBe('required')
    expect(validateDbmsUserId(false, 123)).toBe('ok')

    expect(validateDbmsUserId(true, null)).toBe('ok')
    expect(validateDbmsUserId(true, undefined)).toBe('ok')
    expect(validateDbmsUserId(true, 123)).toBe('must_be_empty')
  })

  it('maps auth types to UI labels', () => {
    expect(getDbmsAuthTypeLabel(undefined)).toBe('\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u0430\u044f')
    expect(getDbmsAuthTypeLabel('local')).toBe('\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u0430\u044f')
    expect(getDbmsAuthTypeLabel('service')).toBe('\u0421\u0435\u0440\u0432\u0438\u0441\u043d\u0430\u044f')
    expect(getDbmsAuthTypeLabel('other')).toBe('\u0414\u0440\u0443\u0433\u0430\u044f')
  })

  it('maps password configured flag to UI labels', () => {
    expect(getDbmsPasswordConfiguredLabel(true)).toBe('\u0417\u0430\u0434\u0430\u043d')
    expect(getDbmsPasswordConfiguredLabel(false)).toBe('\u041d\u0435 \u0437\u0430\u0434\u0430\u043d')
  })
})

