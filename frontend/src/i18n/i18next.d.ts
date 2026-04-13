import 'i18next'

import type { AppCatalogSchema } from './resources'

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common'
    resources: AppCatalogSchema
    returnNull: false
    enableSelector: 'optimize'
  }
}
