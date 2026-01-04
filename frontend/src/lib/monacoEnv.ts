import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import JsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'

type MonacoEnvironment = {
  getWorker: (moduleId: string, label: string) => Worker
}

const globalScope = self as unknown as { MonacoEnvironment?: MonacoEnvironment }

if (!globalScope.MonacoEnvironment) {
  globalScope.MonacoEnvironment = {
    getWorker(_moduleId, label) {
      if (label === 'json') {
        return new JsonWorker()
      }
      return new EditorWorker()
    },
  }
}

