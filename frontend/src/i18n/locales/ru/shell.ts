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
    dashboard: 'Панель управления',
    systemStatus: 'Статус системы',
    clusters: 'Кластеры',
    databases: 'Базы',
    extensions: 'Расширения',
    operations: 'Операции',
    artifacts: 'Артефакты',
    workflows: 'Workflow-схемы',
    templates: 'Шаблоны операций',
    decisions: 'Политики решений',
    poolCatalog: 'Каталог пулов',
    poolTopologyTemplates: 'Шаблоны топологий пулов',
    poolExecutionPacks: 'Пакеты выполнения пулов',
    poolMasterData: 'Master Data пулов',
    poolRuns: 'Запуски пулов',
    poolFactual: 'Факты пулов',
    poolTemplates: 'Шаблоны схем пулов',
    serviceMesh: 'Сервисная шина',
    rbac: 'RBAC',
    users: 'Пользователи',
    dlq: 'DLQ',
    runtimeSettings: 'Настройки runtime',
    commandSchemas: 'Схемы команд',
    timelineSettings: 'Настройки timeline',
  },
} as const

export default shell
