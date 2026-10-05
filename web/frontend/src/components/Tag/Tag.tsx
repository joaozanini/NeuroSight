import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './Tag.module.css'

interface TagProps {
  // pill: etiquetas dos estímulos ("paisagem") e perfil ("Pesquisador");
  // rounded: identificadores ao lado do título ("P-014", "Imagem").
  shape?: 'pill' | 'rounded'
  size?: 'sm' | 'md'
  // Com onRemove a etiqueta ganha um botão para tirá-la (campo de etiquetas).
  onRemove?: () => void
  removeLabel?: string
  className?: string
  children: ReactNode
}

export default function Tag({ shape = 'pill', size = 'sm', onRemove, removeLabel, className, children }: TagProps) {
  return (
    <span className={cx(styles.tag, styles[shape], styles[size], onRemove && styles.removable, className)}>
      {children}
      {onRemove && (
        <button type="button" className={styles.remove} onClick={onRemove} aria-label={removeLabel ?? 'Remover'}>
          <X size={14} strokeWidth={2.5} aria-hidden />
        </button>
      )}
    </span>
  )
}
