const errors = {
  notification: {
    title: 'Request error',
  },
  transport: {
    network: 'Network error. Check your connection and try again.',
  },
  status: {
    '403': 'Access denied. You do not have permission for this action.',
    '404': 'Resource not found.',
    '500': 'Server error. Please try again later.',
    '502': 'Service temporarily unavailable. Please try again.',
    '503': 'Service temporarily unavailable. Please try again.',
    '504': 'Service temporarily unavailable. Please try again.',
  },
  problem: {
    SESSION_EXPIRED: 'Session expired. Please sign in again.',
    POOL_WORKFLOW_BINDING_REQUIRED: 'Select a workflow binding before continuing.',
    unspecific: 'Something went wrong. Please try again.',
  },
} as const

export default errors
