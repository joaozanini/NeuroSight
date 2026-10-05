import { forwardRef } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import styles from './RadioCard.module.css'

export interface RadioCardProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  description?: ReactNode
  // option (W18, W20): borda clara, e a opção marcada ganha contorno e fundo azuis.
  // control (W07): caixa com a borda dos campos; só o botão de rádio indica a escolha.
  appearance?: 'option' | 'control'
}

// Opção de um grupo de rádio desenhada como cartão clicável. Use dentro de RadioCardGroup.
const RadioCard = forwardRef<HTMLInputElement, RadioCardProps>(function RadioCard(
  { label, description, appearance = 'option', className, ...rest },
  ref,
) {
  return (
    <label
      className={cx(
        styles.card,
        appearance === 'option' ? styles.option : styles.control,
        description ? styles.withDescription : undefined,
        rest.disabled && styles.disabled,
        className,
      )}
    >
      <input ref={ref} type="radio" className={styles.radio} {...rest} />
      <span className={styles.text}>
        <span className={styles.label}>{label}</span>
        {description && <span className={styles.description}>{description}</span>}
      </span>
    </label>
  )
})

export default RadioCard
