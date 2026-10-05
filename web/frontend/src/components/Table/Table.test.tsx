import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import Table from './Table'
import type { Column } from './Table'

interface Row {
  code: string
  name: string
}

const columns: Column<Row>[] = [
  { key: 'code', header: 'Código', render: (r) => r.code },
  { key: 'name', header: 'Nome', render: (r) => r.name },
  { key: 'actions', header: 'Ações', align: 'right', render: () => 'Editar' },
]

describe('Table', () => {
  it('desenha cabeçalho e linhas', () => {
    render(<Table caption="Pacientes" columns={columns} rows={[{ code: 'P-014', name: 'Mariana Alves' }]} rowKey={(r) => r.code} />)
    const table = screen.getByRole('table', { name: 'Pacientes' })
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Código', 'Nome', 'Ações'])
    expect(within(table).getByRole('row', { name: /P-014 Mariana Alves Editar/ })).toBeInTheDocument()
  })

  it('mostra o estado vazio e o carregando', () => {
    const { rerender } = render(<Table columns={columns} rows={[]} rowKey={(r: Row) => r.code} empty="Nenhum paciente encontrado." />)
    expect(screen.getByText('Nenhum paciente encontrado.')).toBeInTheDocument()
    rerender(<Table columns={columns} rows={[]} rowKey={(r: Row) => r.code} loading />)
    expect(screen.getByRole('table')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('Carregando')
  })
})
