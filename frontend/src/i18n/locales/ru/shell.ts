const shell = {
  skipToContent: 'Перейти к содержимому',
  appName: 'CommandCenter1C',
  notifications: {
    requestError: 'Ошибка запроса',
  },
  bootstrap: {
    failedTitle: 'Не удалось загрузить shell bootstrap',
    fallbackMessage: 'Не удалось получить обязательный runtime context shell.',
  },
  locale: {
    label: 'Язык',
    options: {
      ru: 'Русский',
      en: 'English',
    },
  },
  tenant: {
    activeLabel: 'Активный tenant',
    staffBadge: 'Staff',
  },
  stream: {
    title: 'Поток баз данных',
    tag: {
      connecting: 'Подключение…',
      connected: 'Подключён',
      fallback: 'Fallback',
    },
    buttonLabel: {
      connecting: 'Поток: подключение…',
      connected: 'Поток: подключён',
      fallback: 'Поток: fallback',
    },
    tooltip: {
      connected: 'Онлайн-обновления включены',
      unavailable: 'Live stream недоступен',
    },
    retryIn: 'Повтор через {{seconds}}с',
  },
  navigation: {
    dashboard: 'Dashboard',
    systemStatus: 'System Status',
    clusters: 'Clusters',
    databases: 'Databases',
    extensions: 'Extensions',
    operations: 'Operations',
    artifacts: 'Artifacts',
    workflows: 'Workflows',
    templates: 'Templates',
    decisions: 'Decisions',
    poolCatalog: 'Pool Catalog',
    poolTopologyTemplates: 'Pool Topology Templates',
    poolExecutionPacks: 'Pool Execution Packs',
    poolMasterData: 'Pool Master Data',
    poolRuns: 'Pool Runs',
    poolFactual: 'Pool Factual',
    poolTemplates: 'Pool Templates',
    serviceMesh: 'Service Mesh',
    rbac: 'RBAC',
    users: 'Users',
    dlq: 'DLQ',
    runtimeSettings: 'Runtime Settings',
    commandSchemas: 'Command Schemas',
    timelineSettings: 'Timeline Settings',
  },
} as const

export default shell
