import { forwardRef, useId } from 'react'
import type { ReactNode, SelectHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'
import { cx } from '../../lib/cx'
import Field from '../Field/Field'
import { describedBy } from '../Field/describedBy'
import fieldStyles from '../Field/Field.module.css'
import type { ControlSize } from '../TextField/TextField'
import styles from './Select.module.css'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: ReactNode
  hideLabel?: boolean
  hint?: ReactNode
  error?: ReactNode
  options: SelectOption[]
  // Os filtros dos protótipos usam md (48 px), como a busca.
  size?: ControlSize
  fieldClassName?: string
}

// Select nativo (acessível e com a lista do sistema), só com a caixa no estilo dos campos.
const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { id, label, hideLabel, hint, error, options, size = 'md', fieldClassName, className, ...rest },
  ref,
) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <Field id={selectId} label={label} hideLabel={hideLabel} hint={hint} error={error} className={fieldClassName}>
      <div className={styles.wrap}>
        <select
          ref={ref}
          id={selectId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(selectId, { hint, error })}
          className={cx(fieldStyles.control, size !== 'lg' && fieldStyles[size], styles.select, className)}
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown size={18} strokeWidth={2.25} className={styles.chevron} aria-hidden />
      </div>
    </Field>
  )
})

export default Select
