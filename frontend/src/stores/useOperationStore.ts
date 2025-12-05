import { create } from 'zustand'
import type { UIBatchOperation } from '../utils/operationTransforms'

/**
 * Legacy Operation interface for backward compatibility.
 * @deprecated Use UIBatchOperation from operationTransforms instead.
 */
export interface Operation {
  id: string
  type: string
  status: string
  database: string
  payload: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  created_at: string
  updated_at: string
}

interface OperationStore {
  operations: UIBatchOperation[]
  loading: boolean
  error: string | null
  setOperations: (operations: UIBatchOperation[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useOperationStore = create<OperationStore>((set) => ({
  operations: [],
  loading: false,
  error: null,
  setOperations: (operations) => set({ operations }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}))
