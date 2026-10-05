import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import styles from './RadioCard.module.css'

interface RadioCardGroupProps {
  legend: ReactNode
  hint?: ReactNode
  error?: ReactNode
  // inline: opções lado a lado, quebrando linha (W07 "Sexo"); stack: uma por linha (W20 "Perfil").
  layout?: 'inline' | 'stack'
  className?: string
  children: ReactNode
}

export default function RadioCardGroup({ legend, hint, error, layout = 'inline', className, children }: RadioCardGroupProps) {
  return (
    <fieldset className={cx(styles.group, className)} aria-invalid={error ? true : undefined}>
      <legend className={styles.legend}>{legend}</legend>
      <div className={cx(styles.options, layout === 'stack' ? styles.stack : styles.inline)}>{children}</div>
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : (
        hint && <p className={styles.hint}>{hint}</p>
      )}
    </fieldset>
  )
}
