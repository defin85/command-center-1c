const platform = {
  actions: {
    cancel: 'Отмена',
    confirm: 'Подтвердить',
    save: 'Сохранить',
  },
  emptyState: {
    noDataAvailable: 'Нет данных для отображения.',
  },
  jsonBlock: {
    copyJson: 'Скопировать JSON',
  },
  statusBadge: {
    active: 'Активно',
    compatible: 'Совместимо',
    deactivated: 'Деактивировано',
    error: 'Ошибка',
    inactive: 'Неактивно',
    incompatible: 'Несовместимо',
    pinned: 'Закреплено',
    published: 'Опубликовано',
    unknown: 'Неизвестно',
    warning: 'Предупреждение',
  },
} as const

export default platform
