import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import type { FieldMessages } from './describedBy'
import styles from './Field.module.css'

interface FieldProps extends FieldMessages {
  id: string
  label?: ReactNode
  // Esconde o rótulo visualmente sem tirá-lo dos leitores de tela (ex.: busca com placeholder).
  hideLabel?: boolean
  className?: string
  children: ReactNode
}

// Rótulo, campo e dica ou erro logo abaixo, como nos formulários dos protótipos.
export default function Field({ id, label, hideLabel = false, hint, error, className, children }: FieldProps) {
  return (
    <div className={cx(styles.field, className)}>
      {label && (
        <label htmlFor={id} className={cx(styles.label, hideLabel && 'sr-only')}>
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p id={`${id}-error`} className={styles.error}>
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className={styles.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  )
}
