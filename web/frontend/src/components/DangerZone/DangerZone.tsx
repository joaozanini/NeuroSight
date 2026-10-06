import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import Button from '../Button/Button'
import styles from './DangerZone.module.css'

interface DangerZoneProps {
  title: string
  description: ReactNode
  actionLabel?: string
  onAction?: () => void
  disabled?: boolean
  loading?: boolean
  // Botões próprios no lugar da ação única (ex.: "Excluir estímulo" ao lado de "Arquivar estímulo").
  actions?: ReactNode
  // neutral: o cartão de algo que se desfaz ("Reativar paciente"), sem o vermelho.
  tone?: 'danger' | 'neutral'
  className?: string
}

// Cartão de ação irreversível ou sensível, com borda vermelha (W08 "Inativar paciente", W11).
export default function DangerZone({
  title,
  description,
  actionLabel,
  onAction,
  disabled,
  loading,
  actions,
  tone = 'danger',
  className,
}: DangerZoneProps) {
  return (
    <section className={cx(styles.zone, tone === 'neutral' && styles.neutral, className)} aria-label={title}>
      <div className={styles.text}>
        <h2 className={styles.title}>{title}</h2>
        <p className={styles.description}>{description}</p>
      </div>
      {actions ? (
        <div className={styles.actions}>{actions}</div>
      ) : (
        <Button
          variant={tone === 'neutral' ? 'secondary' : 'danger'}
          size="sm"
          onClick={onAction}
          disabled={disabled}
          loading={loading}
        >
          {actionLabel}
        </Button>
      )}
    </section>
  )
}
