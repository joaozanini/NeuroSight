import type { HTMLAttributes, ReactNode } from 'react'
import { cx } from '../../lib/cx'
import styles from './Card.module.css'

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode
  description?: ReactNode
  // Ações no canto do cabeçalho (ex.: "Editar informações").
  actions?: ReactNode
  // md: 24 px; lg: 28 px (cartões de formulário do assistente); none: o conteúdo cuida do espaço.
  padding?: 'none' | 'md' | 'lg'
  as?: 'section' | 'div' | 'article'
}

export default function Card({
  title,
  description,
  actions,
  padding = 'md',
  as: Tag = 'section',
  className,
  children,
  ...rest
}: CardProps) {
  const hasHeader = Boolean(title || description || actions)
  return (
    <Tag className={cx(styles.card, styles[padding], className)} {...rest}>
      {hasHeader && (
        <header className={styles.header}>
          <div className={styles.heading}>
            {title && <h2 className={styles.title}>{title}</h2>}
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      {children}
    </Tag>
  )
}
