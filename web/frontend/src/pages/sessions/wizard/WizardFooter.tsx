import type { ReactNode } from 'react'
import styles from './Wizard.module.css'

// Rodapé das etapas: uma divisória e os botões nas pontas (Cancelar/Voltar à esquerda).
export default function WizardFooter({ start, end }: { start: ReactNode; end: ReactNode }) {
  return (
    <div className={styles.footer}>
      <div className={styles.footerStart}>{start}</div>
      <div className={styles.footerEnd}>{end}</div>
    </div>
  )
}
