import { CommandSchemasPageView } from './CommandSchemasPageView'
import { useCommandSchemasPageModel } from './useCommandSchemasPageModel'

export function CommandSchemasPage() {
  const model = useCommandSchemasPageModel()
  return <CommandSchemasPageView model={model} />
}

export default CommandSchemasPage

