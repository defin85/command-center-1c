/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import {
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from 'react'

type AntdModule = typeof import('antd')
type NameSegment = string | number
type NamePath = NameSegment | NameSegment[]

type AppProps = {
  children?: ReactNode
}

type ButtonProps = {
  children?: ReactNode
  danger?: boolean
  disabled?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
}

type FormRule = {
  message?: ReactNode
  required?: boolean
  validator?: (_rule: unknown, value: unknown) => Promise<void> | void
}

type FormApi = {
  clearFieldError: (name: NamePath) => void
  getFieldError: (name: NamePath) => string | null
  getFieldValue: (name: NamePath) => unknown
  getVersion: () => number
  registerField: (name: NamePath, rules?: FormRule[]) => void
  setFieldValue: (name: NamePath, value: unknown) => void
  setFieldsValue: (values: Record<string, unknown>) => void
  subscribe: (listener: () => void) => () => void
  validateFields: () => Promise<Record<string, unknown>>
}

type FormContextValue = {
  form: FormApi
  version: number
}

type FormProps = {
  children?: ReactNode
  form?: FormApi
}

type FormItemProps = {
  children?: ReactNode
  help?: ReactNode
  htmlFor?: string
  label?: ReactNode
  name?: NamePath
  rules?: FormRule[]
  style?: CSSProperties
}

type FormListField = {
  key: string
  name: number
}

type FormListOps = {
  add: (value?: unknown) => void
  remove: (index: number) => void
}

type FormListProps = {
  children: (fields: FormListField[], ops: FormListOps) => ReactNode
  name: string
}

type InputProps = {
  'aria-label'?: string
  'data-testid'?: string
  disabled?: boolean
  id?: string
  list?: string
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  value?: string
}

type InputNumberProps = {
  disabled?: boolean
  id?: string
  max?: number
  min?: number
  onChange?: (value: number | null) => void
  placeholder?: string
  style?: CSSProperties
  value?: number | null
}

type SpaceProps = {
  children?: ReactNode
  style?: CSSProperties
}

type ParagraphProps = {
  children?: ReactNode
  style?: CSSProperties
  type?: 'secondary' | 'success' | 'warning' | 'danger'
}

type TitleProps = {
  children?: ReactNode
  level?: 1 | 2 | 3 | 4 | 5
  style?: CSSProperties
}

const noop = () => undefined

const FormContext = createContext<FormContextValue | null>(null)
const ListPathContext = createContext<NameSegment[] | null>(null)

function normalizePath(name: NamePath): NameSegment[] {
  return Array.isArray(name) ? name : [name]
}

function mergePath(basePath: NameSegment[] | null, name: NamePath | undefined): NameSegment[] | null {
  if (name === undefined) {
    return null
  }
  const localPath = normalizePath(name)
  return basePath ? [...basePath, ...localPath] : localPath
}

function pathKey(path: NameSegment[]) {
  return path.join('.')
}

function getAtPath(source: unknown, path: NameSegment[]) {
  return path.reduce<unknown>((current, segment) => {
    if (current == null || typeof current !== 'object') {
      return undefined
    }
    return (current as Record<NameSegment, unknown>)[segment]
  }, source)
}

function setAtPath(source: unknown, path: NameSegment[], value: unknown): unknown {
  if (path.length === 0) {
    return value
  }

  const [head, ...tail] = path
  const isIndex = typeof head === 'number'
  const nextSource = source == null
    ? (isIndex ? [] : {})
    : Array.isArray(source)
      ? [...source]
      : { ...(source as Record<NameSegment, unknown>) }

  const currentChild = (nextSource as Record<NameSegment, unknown>)[head]
  ;(nextSource as Record<NameSegment, unknown>)[head] = tail.length === 0
    ? value
    : setAtPath(currentChild, tail, value)

  return nextSource
}

function coerceErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  return 'Validation failed'
}

function isEmptyValue(value: unknown) {
  return value === undefined || value === null || value === ''
}

function getOriginalOnChange(child: ReactNode) {
  if (!isValidElement(child)) {
    return undefined
  }
  return (child as ReactElement<Record<string, unknown>>).props.onChange
}

function createMockForm(): FormApi {
  const listeners = new Set<() => void>()
  const fields = new Map<string, { path: NameSegment[]; rules?: FormRule[] }>()
  let values: Record<string, unknown> = {}
  let errors = new Map<string, string>()
  let version = 0

  const emit = () => {
    version += 1
    listeners.forEach((listener) => listener())
  }

  return {
    clearFieldError: (name) => {
      errors.delete(pathKey(normalizePath(name)))
      emit()
    },
    getFieldError: (name) => errors.get(pathKey(normalizePath(name))) ?? null,
    getFieldValue: (name) => getAtPath(values, normalizePath(name)),
    getVersion: () => version,
    registerField: (name, rules) => {
      const path = normalizePath(name)
      fields.set(pathKey(path), { path, rules })
    },
    setFieldValue: (name, value) => {
      const path = normalizePath(name)
      values = setAtPath(values, path, value) as Record<string, unknown>
      errors.delete(pathKey(path))
      emit()
    },
    setFieldsValue: (nextValues) => {
      Object.entries(nextValues).forEach(([key, value]) => {
        values = setAtPath(values, [key], value) as Record<string, unknown>
        errors.delete(pathKey([key]))
      })
      emit()
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    validateFields: async () => {
      const nextErrors = new Map<string, string>()

      for (const { path, rules } of fields.values()) {
        const value = getAtPath(values, path)
        for (const rule of rules ?? []) {
          if (rule.required && isEmptyValue(value)) {
            nextErrors.set(pathKey(path), String(rule.message ?? 'Required'))
            break
          }
          if (rule.validator) {
            try {
              await rule.validator({}, value)
            } catch (error) {
              nextErrors.set(pathKey(path), coerceErrorMessage(error))
              break
            }
          }
        }
      }

      errors = nextErrors
      emit()

      if (errors.size > 0) {
        throw new Error('Validation failed')
      }

      return values
    },
  }
}

export function createDatabaseIbcmdConnectionProfileModalAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => ({
      message: {
        error: noop,
        info: noop,
        success: noop,
        warning: noop,
      },
      modal: {},
    }),
  })

  const MockButton = ({
    children,
    danger,
    disabled,
    onClick,
  }: ButtonProps) => (
    <button
      type="button"
      data-button-danger={danger ? 'true' : undefined}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )

  const MockFormRoot = ({
    children,
    form,
  }: FormProps) => {
    const fallbackFormRef = useRef<FormApi | null>(null)
    if (!fallbackFormRef.current) {
      fallbackFormRef.current = createMockForm()
    }

    const resolvedForm = form ?? fallbackFormRef.current
    const [version, setVersion] = useState(resolvedForm.getVersion())

    useEffect(() => {
      setVersion(resolvedForm.getVersion())
      return resolvedForm.subscribe(() => {
        setVersion(resolvedForm.getVersion())
      })
    }, [resolvedForm])

    return (
      <FormContext.Provider value={{ form: resolvedForm, version }}>
        <form data-form-version={version}>{children}</form>
      </FormContext.Provider>
    )
  }

  const MockFormItem = ({
    children,
    help,
    htmlFor,
    label,
    name,
    rules,
    style,
  }: FormItemProps) => {
    const formContext = useContext(FormContext)
    const form = formContext?.form ?? null
    const listPath = useContext(ListPathContext)
    const fullPath = useMemo(() => mergePath(listPath, name), [listPath, name])

    if (form && fullPath) {
      form.registerField(fullPath, rules)
    }

    const currentValue = form && fullPath ? form.getFieldValue(fullPath) : undefined
    const error = form && fullPath ? form.getFieldError(fullPath) : null

    let content = children
    if (form && fullPath && isValidElement(children)) {
      const element = children as ReactElement<Record<string, unknown>>
      const originalOnChange = getOriginalOnChange(children)
      content = cloneElement(element, {
        value: currentValue ?? '',
        'aria-label': element.props['aria-label'] ?? (typeof label === 'string' ? label : undefined),
        onChange: (...args: unknown[]) => {
          const firstArg = args[0] as { target?: { value?: unknown } } | undefined
          const nextValue = firstArg?.target ? firstArg.target.value : args[0]
          form.setFieldValue(fullPath, nextValue)
          originalOnChange?.(...args)
        },
      })
    }

    return (
      <div className="ant-form-item" style={style}>
        {label ? <label htmlFor={htmlFor}>{label}</label> : null}
        {content}
        {help ? <div>{help}</div> : null}
        {error ? <div>{error}</div> : null}
      </div>
    )
  }

  const MockFormList = ({
    children,
    name,
  }: FormListProps) => {
    const formContext = useContext(FormContext)
    const form = formContext?.form ?? null
    const basePath = normalizePath(name)
    const values = form?.getFieldValue(basePath)
    const rows = Array.isArray(values) ? values : []
    const fields = rows.map((_, index) => ({ key: `${index}`, name: index }))

    const ops: FormListOps = {
      add: (value) => {
        if (!form) {
          return
        }
        const currentRows = Array.isArray(form.getFieldValue(basePath)) ? [...(form.getFieldValue(basePath) as unknown[])] : []
        currentRows.push(value ?? {})
        form.setFieldValue(basePath, currentRows)
      },
      remove: (index) => {
        if (!form) {
          return
        }
        const currentRows = Array.isArray(form.getFieldValue(basePath)) ? [...(form.getFieldValue(basePath) as unknown[])] : []
        currentRows.splice(index, 1)
        form.setFieldValue(basePath, currentRows)
      },
    }

    return (
      <ListPathContext.Provider value={basePath}>
        {children(fields, ops)}
      </ListPathContext.Provider>
    )
  }

  const MockForm = Object.assign(MockFormRoot, {
    Item: MockFormItem,
    List: MockFormList,
    useForm: () => {
      const formRef = useRef<FormApi | null>(null)
      if (!formRef.current) {
        formRef.current = createMockForm()
      }
      return [formRef.current] as const
    },
  })

  const MockInput = ({
    'aria-label': ariaLabel,
    'data-testid': dataTestId,
    disabled,
    id,
    list,
    onChange,
    placeholder,
    value,
  }: InputProps) => {
    const [internalValue, setInternalValue] = useState(value ?? '')

    useEffect(() => {
      setInternalValue(value ?? '')
    }, [value])

    return (
      <input
        aria-label={ariaLabel}
        data-testid={dataTestId}
        disabled={disabled}
        id={id}
        list={list}
        onChange={(event) => {
          setInternalValue(event.target.value)
          onChange?.(event)
        }}
        placeholder={placeholder}
        value={internalValue}
      />
    )
  }

  const MockInputNumber = ({
    disabled,
    id,
    max,
    min,
    onChange,
    placeholder,
    style,
    value,
  }: InputNumberProps) => {
    const [internalValue, setInternalValue] = useState<string>(value == null ? '' : String(value))

    useEffect(() => {
      setInternalValue(value == null ? '' : String(value))
    }, [value])

    return (
      <input
        disabled={disabled}
        id={id}
        max={max}
        min={min}
        onChange={(event) => {
          setInternalValue(event.target.value)
          if (event.target.value === '') {
            onChange?.(null)
            return
          }
          onChange?.(Number(event.target.value))
        }}
        placeholder={placeholder}
        style={style}
        type="number"
        value={internalValue}
      />
    )
  }

  const MockSpace = ({ children, style }: SpaceProps) => <div style={style}>{children}</div>
  const MockCompact = ({ children, style }: SpaceProps) => <div style={style}>{children}</div>
  const MockParagraph = ({ children, style, type }: ParagraphProps) => <p style={style} data-text-type={type}>{children}</p>
  const MockTitle = ({ children, level = 1, style }: TitleProps) => {
    const Tag = `h${level}` as const
    return <Tag style={style}>{children}</Tag>
  }

  const MockTypography = {
    ...actual.Typography,
    Paragraph: MockParagraph,
    Title: MockTitle,
  }

  const MockInputRoot = Object.assign(MockInput, {
    TextArea: MockInput,
  })

  const MockSpaceRoot = Object.assign(MockSpace, {
    Compact: MockCompact,
  })

  return {
    ...actual,
    App: MockApp,
    Button: MockButton,
    Form: MockForm,
    Input: MockInputRoot,
    InputNumber: MockInputNumber,
    Space: MockSpaceRoot,
    Typography: MockTypography,
  }
}
