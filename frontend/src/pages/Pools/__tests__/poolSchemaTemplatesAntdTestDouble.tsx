/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import {
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react'

import { createPoolReusableAuthoringAntdTestDouble } from './poolReusableAuthoringAntdTestDouble'

type AntdModule = typeof import('antd')

type AppProps = {
  children?: ReactNode
}

type FormRule = {
  message?: ReactNode
  required?: boolean
}

type FormInstance = {
  getFieldValue: (name: string) => unknown
  registerField: (name: string, rules?: FormRule[]) => void
  resetFields: () => void
  setFieldsValue: (values: Record<string, unknown>) => void
  setFieldValue: (name: string, value: unknown) => void
  subscribe: (listener: () => void) => () => void
  validateFields: () => Promise<Record<string, unknown>>
}

type FormProps = {
  children?: ReactNode
  form?: FormInstance
}

type FormItemProps = {
  children?: ReactNode
  label?: ReactNode
  name?: string
  rules?: FormRule[]
  valuePropName?: 'value' | 'checked'
}

const noop = () => undefined

const FormContext = createContext<FormInstance | null>(null)

function createMockForm(): FormInstance {
  const listeners = new Set<() => void>()
  const values = new Map<string, unknown>()
  const fields = new Map<string, FormRule[] | undefined>()

  const emit = () => {
    listeners.forEach((listener) => listener())
  }

  return {
    getFieldValue: (name) => values.get(name),
    registerField: (name, rules) => {
      fields.set(name, rules)
    },
    resetFields: () => {
      values.clear()
      emit()
    },
    setFieldsValue: (nextValues) => {
      Object.entries(nextValues).forEach(([key, value]) => {
        values.set(key, value)
      })
      emit()
    },
    setFieldValue: (name, value) => {
      values.set(name, value)
      emit()
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    validateFields: async () => {
      for (const [name, rules] of fields.entries()) {
        const value = values.get(name)
        const requiredRule = rules?.find((rule) => rule?.required)
        if (requiredRule && (value === undefined || value === null || value === '')) {
          throw new Error(String(requiredRule.message ?? `${name} is required`))
        }
      }
      return Object.fromEntries(values.entries())
    },
  }
}

function withLabeledControl(
  child: ReactNode,
  label: ReactNode,
  injectedProps: Record<string, unknown>,
) {
  if (!isValidElement(child)) {
    return child
  }

  const element = child as ReactElement<Record<string, unknown>>
  return cloneElement(element, {
    ...injectedProps,
    'aria-label': element.props['aria-label'] ?? (typeof label === 'string' ? label : undefined),
  })
}

function getOriginalOnChange(child: ReactNode) {
  if (!isValidElement(child)) {
    return undefined
  }
  return (child as ReactElement<Record<string, unknown>>).props.onChange
}

export function createPoolSchemaTemplatesAntdTestDouble(actual: AntdModule): AntdModule {
  const shared = createPoolReusableAuthoringAntdTestDouble(actual)

  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => ({
      message: {
        error: noop,
        success: noop,
        warning: noop,
      },
      modal: {},
    }),
  })

  const MockFormRoot = ({
    children,
    form,
  }: FormProps) => {
    const fallbackFormRef = useRef<FormInstance | null>(null)
    if (!fallbackFormRef.current) {
      fallbackFormRef.current = createMockForm()
    }

    const resolvedForm = form ?? fallbackFormRef.current
    const [, setVersion] = useState(0)

    useEffect(() => resolvedForm.subscribe(() => setVersion((version) => version + 1)), [resolvedForm])

    return (
      <FormContext.Provider value={resolvedForm}>
        <form>{children}</form>
      </FormContext.Provider>
    )
  }

  const MockFormItem = ({
    children,
    label,
    name,
    rules,
    valuePropName = 'value',
  }: FormItemProps) => {
    const form = useContext(FormContext)
    const fieldName = name?.trim() ?? ''

    useEffect(() => {
      if (form && fieldName) {
        form.registerField(fieldName, rules)
      }
    }, [fieldName, form, rules])

    const currentValue = fieldName && form ? form.getFieldValue(fieldName) : undefined
    const injectedProps = !fieldName || !form
      ? {}
      : valuePropName === 'checked'
        ? {
          checked: Boolean(currentValue),
          onChange: (...args: unknown[]) => {
            const nextValue = typeof args[0] === 'boolean'
              ? args[0]
              : Boolean((args[0] as { target?: { checked?: boolean } } | undefined)?.target?.checked)
            form.setFieldValue(fieldName, nextValue)
            const originalOnChange = getOriginalOnChange(children)
            originalOnChange?.(...args)
          },
        }
        : {
          value: currentValue ?? '',
          onChange: (...args: unknown[]) => {
            const firstArg = args[0] as { target?: { value?: unknown } } | undefined
            const nextValue = firstArg?.target ? firstArg.target.value : args[0]
            form.setFieldValue(fieldName, nextValue)
            const originalOnChange = getOriginalOnChange(children)
            originalOnChange?.(...args)
          },
        }

    return (
      <div>
        {label ? <label>{label}</label> : null}
        {withLabeledControl(children, label, injectedProps)}
      </div>
    )
  }

  const MockForm = Object.assign(MockFormRoot, {
    Item: MockFormItem,
    useForm: () => {
      const formRef = useRef<FormInstance | null>(null)
      if (!formRef.current) {
        formRef.current = createMockForm()
      }
      return [formRef.current] as const
    },
  })

  return {
    ...shared,
    App: MockApp,
    Form: MockForm,
  }
}
