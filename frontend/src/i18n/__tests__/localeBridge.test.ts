import enUS from 'antd/locale/en_US'
import ruRU from 'antd/locale/ru_RU'
import { describe, expect, it } from 'vitest'

import { antdLocaleByAppLocale } from '../localeBridge'

describe('antd locale bridge', () => {
  it('maps public app locales to the approved Ant Design locale packs', () => {
    expect(antdLocaleByAppLocale.ru).toBe(ruRU)
    expect(antdLocaleByAppLocale.en).toBe(enUS)
  })
})
