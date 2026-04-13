import { Select } from 'antd'
import { useRbacTranslation } from '../../../i18n'

type Option = { label: string; value: number }

export function RbacPrincipalPicker(props: {
  principalType: 'user' | 'role'
  value?: number
  onChange?: (value: number | undefined) => void
  allowClear?: boolean
  disabled?: boolean
  width?: number
  userOptions: Option[]
  userLoading?: boolean
  onUserSearch?: (value: string) => void
  roleOptions: Option[]
  placeholderUser?: string
  placeholderRole?: string
}) {
  const width = props.width ?? 240
  const { t } = useRbacTranslation()

  if (props.principalType === 'user') {
    return (
      <Select
        style={{ width }}
        placeholder={props.placeholderUser ?? t(($) => $.permissions.principalUser)}
        allowClear={props.allowClear}
        disabled={props.disabled}
        value={props.value}
        onChange={(value) => props.onChange?.(typeof value === 'number' ? value : undefined)}
        showSearch
        filterOption={false}
        onSearch={props.onUserSearch}
        options={props.userOptions}
        loading={props.userLoading}
      />
    )
  }

  return (
    <Select
      style={{ width }}
      placeholder={props.placeholderRole ?? t(($) => $.permissions.principalRole)}
      allowClear={props.allowClear}
      disabled={props.disabled}
      value={props.value}
      onChange={(value) => props.onChange?.(typeof value === 'number' ? value : undefined)}
      options={props.roleOptions}
      showSearch
      optionFilterProp="label"
    />
  )
}
