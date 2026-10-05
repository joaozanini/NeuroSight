import { LoaderCircle } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './Spinner.module.css'

interface SpinnerProps {
  size?: number
  className?: string
  // Texto para leitores de tela; sem ele o indicador é decorativo.
  label?: string
}

export default function Spinner({ size = 20, className, label }: SpinnerProps) {
  return (
    <span className={cx(styles.spinner, className)} role={label ? 'status' : undefined}>
      <LoaderCircle size={size} aria-hidden />
      {label && <span className="sr-only">{label}</span>}
    </span>
  )
}
