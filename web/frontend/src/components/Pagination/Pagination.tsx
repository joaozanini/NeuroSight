import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { formatNumber } from '../../lib/format'
import Button from '../Button/Button'
import styles from './Pagination.module.css'

interface PaginationProps {
  // Página atual, começando em 1.
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  // Complemento do total: "Mostrando 1 a 8 de 14 usuários".
  noun?: string
  // Observação abaixo do total ("Usuários não são excluídos, só desativados...").
  note?: ReactNode
  className?: string
}

// "Mostrando 1 a 8 de 15" com Anterior e Próxima, como embaixo das listas.
export default function Pagination({ page, pageSize, total, onPageChange, noun, note, className }: PaginationProps) {
  if (total <= 0) return null
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const first = (page - 1) * pageSize + 1
  const last = Math.min(total, page * pageSize)
  return (
    <nav className={cx(styles.pagination, className)} aria-label="Paginação">
      <div className={styles.summary}>
        <p className={cx(styles.count, note ? styles.countStrong : undefined)} aria-live="polite">
          Mostrando {formatNumber(first)} a {formatNumber(last)} de {formatNumber(total)}
          {noun ? ` ${noun}` : ''}
        </p>
        {note && <p className={styles.note}>{note}</p>}
      </div>
      <div className={styles.buttons}>
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Anterior
        </Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Próxima
        </Button>
      </div>
    </nav>
  )
}
