import enUS from 'antd/locale/en_US'
import ruRU from 'antd/locale/ru_RU'

import type { AppLocale } from './constants'

export const antdLocaleByAppLocale = {
  ru: ruRU,
  en: enUS,
} as const satisfies Record<AppLocale, typeof ruRU>
