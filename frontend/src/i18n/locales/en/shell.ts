const shell = {
  skipToContent: 'Skip to content',
  appName: 'CommandCenter1C',
  notifications: {
    requestError: 'Request error',
  },
  bootstrap: {
    failedTitle: 'Shell bootstrap failed',
    fallbackMessage: 'Unable to load the required shell runtime context.',
  },
  locale: {
    label: 'Language',
    options: {
      ru: 'Русский',
      en: 'English',
    },
  },
  tenant: {
    activeLabel: 'Active tenant',
    staffBadge: 'Staff',
  },
  stream: {
    title: 'Database stream',
    tag: {
      connecting: 'Connecting…',
      connected: 'Connected',
      fallback: 'Fallback',
    },
    buttonLabel: {
      connecting: 'Stream: Connecting…',
      connected: 'Stream: Connected',
      fallback: 'Stream: Fallback',
    },
    tooltip: {
      connected: 'Live updates enabled',
      unavailable: 'Live stream unavailable',
    },
    retryIn: 'Retry in {{seconds}}s',
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
