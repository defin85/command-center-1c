const platform = {
  actions: {
    cancel: 'Cancel',
    confirm: 'Confirm',
    save: 'Save',
  },
  emptyState: {
    noDataAvailable: 'No data available.',
  },
  jsonBlock: {
    copyJson: 'Copy JSON',
  },
  statusBadge: {
    active: 'Active',
    compatible: 'Compatible',
    deactivated: 'Deactivated',
    error: 'Error',
    inactive: 'Inactive',
    incompatible: 'Incompatible',
    pinned: 'Pinned',
    published: 'Published',
    unknown: 'Unknown',
    warning: 'Warning',
  },
} as const

export default platform
