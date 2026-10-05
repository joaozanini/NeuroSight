import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pagination from './Pagination'

describe('Pagination', () => {
  it('mostra a faixa atual e desliga Anterior na primeira página', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(<Pagination page={1} pageSize={8} total={15} onPageChange={onPageChange} />)
    expect(screen.getByText('Mostrando 1 a 8 de 15')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Próxima' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('desliga Próxima na última página e usa o separador de milhar e o complemento', () => {
    render(<Pagination page={125} pageSize={10} total={1248} noun="registros" note="Os registros são só leitura." onPageChange={() => undefined} />)
    expect(screen.getByText('Mostrando 1.241 a 1.248 de 1.248 registros')).toBeInTheDocument()
    expect(screen.getByText('Os registros são só leitura.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Próxima' })).toBeDisabled()
  })

  it('não aparece sem resultados', () => {
    const { container } = render(<Pagination page={1} pageSize={8} total={0} onPageChange={() => undefined} />)
    expect(container).toBeEmptyDOMElement()
  })
})
