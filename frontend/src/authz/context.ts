import { createContext } from 'react'

export type AccessLevel = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'

const ACCESS_RANK: Record<AccessLevel, number> = {
  VIEW: 1,
  OPERATE: 2,
  MANAGE: 3,
  ADMIN: 4,
}

export const normalizeLevel = (value?: string | null): AccessLevel | null => {
  if (!value) return null
  if (value === 'VIEW' || value === 'OPERATE' || value === 'MANAGE' || value === 'ADMIN') {
    return value
  }
  return null
}

export const hasLevel = (current: AccessLevel | null | undefined, required: AccessLevel): boolean => {
  if (!current) return false
  return ACCESS_RANK[current] >= ACCESS_RANK[required]
}

export type AuthzContextValue = {
  isStaff: boolean
  isLoading: boolean
  canDatabase: (databaseId: string | null | undefined, required: AccessLevel) => boolean
  canCluster: (clusterId: string | null | undefined, required: AccessLevel) => boolean
  canTemplate: (templateId: string | null | undefined, required: AccessLevel) => boolean
  canAnyDatabase: (required: AccessLevel) => boolean
  canAnyCluster: (required: AccessLevel) => boolean
  canAnyTemplate: (required: AccessLevel) => boolean
  getDatabaseLevel: (databaseId: string | null | undefined) => AccessLevel | null
  getClusterLevel: (clusterId: string | null | undefined) => AccessLevel | null
  getTemplateLevel: (templateId: string | null | undefined) => AccessLevel | null
}

export const AuthzContext = createContext<AuthzContextValue | null>(null)
