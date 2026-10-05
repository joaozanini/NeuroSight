import type { ReactNode } from 'react'
import { CircleAlert } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './FormAlert.module.css'

interface FormAlertProps {
  className?: string
  children: ReactNode
}

// Erro do formulário inteiro, acima do botão ("E-mail ou senha incorretos."). Anunciado ao aparecer.
export default function FormAlert({ className, children }: FormAlertProps) {
  return (
    <div className={cx(styles.alert, className)} role="alert">
      <CircleAlert size={20} className={styles.icon} aria-hidden />
      <div>{children}</div>
    </div>
  )
}
