import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import type { BadgeTone } from '../../lib/status'
import styles from './Badge.module.css'

interface BadgeProps {
  tone: BadgeTone
  // Ponto à esquerda, como em "Em andamento".
  dot?: boolean
  // sm: selo pequeno ao lado de um nome (ex.: "Você" na lista de usuários).
  size?: 'md' | 'sm'
  className?: string
  children: ReactNode
}

export default function Badge({ tone, dot = false, size = 'md', className, children }: BadgeProps) {
  return (
    <span className={cx(styles.badge, styles[tone], size === 'sm' && styles.sm, className)}>
      {dot && <span className={styles.dot} aria-hidden />}
      {children}
    </span>
  )
}
