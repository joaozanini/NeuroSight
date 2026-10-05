import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import BackLink from './BackLink'
import styles from './PageHeader.module.css'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  back?: { to: string; label: string }
  // Selo ou etiqueta ao lado do título ("Concluída", "P-014", "Imagem").
  badge?: ReactNode
  // Botões à direita, alinhados à base do título e subtítulo.
  actions?: ReactNode
  className?: string
}

export default function PageHeader({ title, subtitle, back, badge, actions, className }: PageHeaderProps) {
  return (
    <header className={cx(styles.header, className)}>
      {back && <BackLink to={back.to} label={back.label} />}
      <div className={styles.row}>
        <div className={styles.heading}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>{title}</h1>
            {badge}
          </div>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </header>
  )
}
