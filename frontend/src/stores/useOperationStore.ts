import { create } from 'zustand'
import { Operation } from '../api/adapters/operations'

interface OperationStore {
  operations: Operation[]
  loading: boolean
  error: string | null
  setOperations: (operations: Operation[]) => void
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
