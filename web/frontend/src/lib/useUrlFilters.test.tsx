import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { ROUTER_FUTURE } from '../test/render'
import { useUrlFilters } from './useUrlFilters'

function Probe() {
  const [, update] = useUrlFilters()
  const location = useLocation()
  return (
    <>
      <button
        onClick={() => {
          update({ tipo: null })
          update({ etiqueta: 'água' })
        }}
      >
        duas mudanças
      </button>
      <button onClick={() => update({ pagina: 1, q: '' })}>primeira página</button>
      <output>{location.search}</output>
    </>
  )
}

describe('filtros na URL', () => {
  it('mudanças seguidas, antes de a tela renderizar de novo, não se sobrescrevem', () => {
    render(
      <MemoryRouter initialEntries={['/estimulos?tipo=videos&pagina=2&q=mar']} future={ROUTER_FUTURE}>
        <Probe />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'duas mudanças' }))
    expect(screen.getByRole('status')).toHaveTextContent('?pagina=2&q=mar&etiqueta=%C3%A1gua')
    fireEvent.click(screen.getByRole('button', { name: 'primeira página' }))
    expect(screen.getByRole('status')).toHaveTextContent(/^\?etiqueta=%C3%A1gua$/)
  })
})
