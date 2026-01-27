import { useCommandSchemasActions } from './model/useCommandSchemasActions'
import { useCommandSchemasState } from './model/useCommandSchemasState'

export function useCommandSchemasPageModel() {
  const state = useCommandSchemasState()
  const actions = useCommandSchemasActions(state)
  return { ...state, ...actions }
}

export type CommandSchemasPageModel = ReturnType<typeof useCommandSchemasPageModel>

