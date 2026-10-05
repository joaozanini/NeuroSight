import { forwardRef, useId } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cx } from '../../lib/cx'
import Field from '../Field/Field'
import { describedBy } from '../Field/describedBy'
import styles from '../Field/Field.module.css'

export type ControlSize = 'lg' | 'md' | 'sm'

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: ReactNode
  hideLabel?: boolean
  hint?: ReactNode
  error?: ReactNode
  // lg (52 px) nos formulários, md (48 px) em busca e filtros, sm (44 px) dentro de cartões.
  size?: ControlSize
  leadingIcon?: LucideIcon
  // Elemento à direita, dentro da caixa (ex.: botão de mostrar a senha).
  trailing?: ReactNode
  fieldClassName?: string
}

const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  {
    id,
    label,
    hideLabel,
    hint,
    error,
    size = 'lg',
    leadingIcon: LeadingIcon,
    trailing,
    fieldClassName,
    className,
    type = 'text',
    'aria-describedby': extraDescribedBy,
    ...rest
  },
  ref,
) {
  const autoId = useId()
  const inputId = id ?? autoId
  const describedByIds = [describedBy(inputId, { hint, error }), extraDescribedBy].filter(Boolean).join(' ')
  const input = (
    <input
      ref={ref}
      id={inputId}
      type={type}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedByIds || undefined}
      className={cx(
        styles.control,
        size !== 'lg' && styles[size],
        LeadingIcon && styles.withLeading,
        trailing ? styles.withTrailing : undefined,
        className,
      )}
      {...rest}
    />
  )
  return (
    <Field id={inputId} label={label} hideLabel={hideLabel} hint={hint} error={error} className={fieldClassName}>
      {LeadingIcon || trailing ? (
        <div className={styles.adorned}>
          {LeadingIcon && (
            <span className={styles.leading}>
              <LeadingIcon size={20} aria-hidden />
            </span>
          )}
          {input}
          {trailing && <span className={styles.trailing}>{trailing}</span>}
        </div>
      ) : (
        input
      )}
    </Field>
  )
})

export default TextField
