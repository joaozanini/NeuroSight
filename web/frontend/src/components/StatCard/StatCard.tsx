import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import Sparkline from './Sparkline'
import styles from './StatCard.module.css'

export interface StatDelta {
  // Texto já formatado ("+1", "+19%"); a seta vem de `direction`.
  text: string
  direction?: 'up' | 'down'
}

interface StatCardProps {
  label: string
  value: ReactNode
  series?: number[]
  // warning: série e destaque em laranja (ex.: "Aguardando dados").
  tone?: 'primary' | 'warning'
  footer?: ReactNode
  delta?: StatDelta
  // Texto em destaque no lugar da variação (ex.: "em envio").
  highlight?: ReactNode
  className?: string
}

// Cartão de KPI do Início (W04): rótulo, número, sparkline e rodapé com a variação.
export default function StatCard({ label, value, series, tone = 'primary', footer, delta, highlight, className }: StatCardProps) {
  const color = tone === 'warning' ? 'var(--color-attention)' : 'var(--color-primary)'
  return (
    <section className={cx(styles.card, className)} aria-label={label}>
      <div className={styles.top}>
        <p className={styles.label}>{label}</p>
        {series && <Sparkline values={series} color={color} width={92} />}
      </div>
      <p className={styles.value}>{value}</p>
      {(footer || delta || highlight) && (
        <div className={styles.footer}>
          <span className={styles.footerText}>{footer}</span>
          {delta && (
            <span className={styles.delta}>
              {delta.text}
              {delta.direction && (
                <svg width="10" height="8" viewBox="0 0 10 8" aria-label={delta.direction === 'up' ? 'subiu' : 'caiu'} role="img">
                  <path d={delta.direction === 'up' ? 'M5 0 10 8H0Z' : 'M5 8 0 0h10Z'} fill="currentColor" />
                </svg>
              )}
            </span>
          )}
          {highlight && <span className={styles.highlight}>{highlight}</span>}
        </div>
      )}
    </section>
  )
}
