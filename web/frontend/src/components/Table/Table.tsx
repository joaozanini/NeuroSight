import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import Spinner from '../Spinner/Spinner'
import styles from './Table.module.css'

export interface Column<T> {
  key: string
  header: ReactNode
  render: (row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
  width?: string | number
  className?: string
}

interface TableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  // Descrição para leitores de tela (ex.: "Pacientes cadastrados").
  caption?: string
  loading?: boolean
  empty?: ReactNode
  className?: string
}

// Tabela dos protótipos: cartão branco, cabeçalho cinza-claro e linhas de 56 px.
export default function Table<T>({ columns, rows, rowKey, caption, loading = false, empty, className }: TableProps<T>) {
  const alignClass = (align?: Column<T>['align']) => (align === 'right' ? styles.right : align === 'center' ? styles.center : undefined)
  let body: ReactNode
  if (loading) {
    body = (
      <tr>
        <td colSpan={columns.length} className={styles.state}>
          <Spinner label="Carregando" /> Carregando…
        </td>
      </tr>
    )
  } else if (rows.length === 0) {
    body = (
      <tr>
        <td colSpan={columns.length} className={styles.state}>
          {empty ?? 'Nada para mostrar.'}
        </td>
      </tr>
    )
  } else {
    body = rows.map((row) => (
      <tr key={rowKey(row)}>
        {columns.map((col) => (
          <td key={col.key} className={cx(alignClass(col.align), col.className)}>
            {col.render(row)}
          </td>
        ))}
      </tr>
    ))
  }

  return (
    <div className={cx(styles.card, className)}>
      <div className={styles.scroll}>
        <table className={styles.table} aria-busy={loading || undefined}>
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} scope="col" className={alignClass(col.align)} style={col.width !== undefined ? { width: col.width } : undefined}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    </div>
  )
}
