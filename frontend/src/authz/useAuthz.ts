import { useContext } from 'react'

import { AuthzContext } from './context'

export const useAuthz = () => {
  const context = useContext(AuthzContext)
  if (!context) {
    throw new Error('useAuthz must be used within AuthzProvider')
  }
  return context
}

