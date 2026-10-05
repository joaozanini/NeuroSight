import { forwardRef, useId } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import styles from './Checkbox.module.css'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  // Texto de apoio abaixo do rótulo (ex.: "Gravar a sessão" na W13).
  description?: ReactNode
  // Rótulo em negrito, quando a caixa é o assunto do bloco.
  strong?: boolean
}

// Caixa de seleção nativa (com accent-color do tema) e rótulo clicável.
const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { id, label, description, strong = false, className, ...rest },
  ref,
) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <div className={cx(styles.checkbox, className)}>
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        className={styles.input}
        aria-describedby={description ? `${inputId}-description` : undefined}
        {...rest}
      />
      <div className={styles.text}>
        <label htmlFor={inputId} className={cx(styles.label, strong && styles.strong)}>
          {label}
        </label>
        {description && (
          <p id={`${inputId}-description`} className={styles.description}>
            {description}
          </p>
        )}
      </div>
    </div>
  )
})

export default Checkbox
