import { Check } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './Stepper.module.css'

interface StepperProps {
  steps: string[]
  // Índice (a partir de 0) da etapa atual; as anteriores aparecem como concluídas.
  current: number
  className?: string
}

// Etapas do assistente de nova sessão (W13): Paciente, Informações, Estímulos, Revisão.
export default function Stepper({ steps, current, className }: StepperProps) {
  return (
    <ol className={cx(styles.stepper, className)} aria-label="Etapas">
      {steps.map((label, index) => {
        const state = index < current ? 'done' : index === current ? 'current' : 'pending'
        return (
          <li key={label} className={cx(styles.step, styles[state])} aria-current={state === 'current' ? 'step' : undefined}>
            <span className={styles.marker} aria-hidden>
              {state === 'done' ? <Check size={16} strokeWidth={3} /> : index + 1}
            </span>
            <span className={styles.label}>
              {label}
              {state === 'done' && <span className="sr-only"> (concluída)</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
