import { cx } from '../../lib/cx'
import styles from './ProgressBar.module.css'

interface ProgressBarProps {
  // Fração de 0 a 1.
  value: number
  // success: verde, como "12 de 12 carregados" (W14).
  tone?: 'primary' | 'success'
  // sm: 6 px (envio de arquivo); md: 10 px (estímulos no óculos).
  size?: 'sm' | 'md'
  label: string
  className?: string
}

export default function ProgressBar({ value, tone = 'primary', size = 'sm', label, className }: ProgressBarProps) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div
      className={cx(styles.track, styles[size], className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
    >
      <div className={cx(styles.fill, tone === 'success' && styles.success)} style={{ width: `${pct}%` }} />
    </div>
  )
}
