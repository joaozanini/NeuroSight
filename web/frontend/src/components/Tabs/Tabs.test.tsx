import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ROUTER_FUTURE } from '../../test/render'
import Segmented from '../Segmented/Segmented'
import Tabs from './Tabs'

describe('Tabs', () => {
  it('em modo de rotas marca a aba da URL atual', () => {
    render(
      <MemoryRouter initialEntries={['/admin/permissoes']} future={ROUTER_FUTURE}>
        <Tabs
          ariaLabel="Administração"
          items={[
            { label: 'Usuários', to: '/admin/usuarios' },
            { label: 'Perfis e permissões', to: '/admin/permissoes' },
          ]}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Perfis e permissões' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Usuários' })).not.toHaveAttribute('aria-current')
  })

  it('em modo de painel troca com clique e com as setas', async () => {
    const user = userEvent.setup()
    function Harness() {
      const [value, setValue] = useState('heatmap')
      return (
        <Tabs
          ariaLabel="Visualização"
          value={value}
          onChange={setValue}
          items={[
            { label: 'Mapa de calor', value: 'heatmap' },
            { label: 'Trajetória do olhar', value: 'path' },
          ]}
        />
      )
    }
    render(<Harness />)
    expect(screen.getByRole('tab', { name: 'Mapa de calor' })).toHaveAttribute('aria-selected', 'true')
    await user.click(screen.getByRole('tab', { name: 'Trajetória do olhar' }))
    expect(screen.getByRole('tab', { name: 'Trajetória do olhar' })).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Mapa de calor' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Mapa de calor' })).toHaveFocus()
  })
})

describe('Segmented', () => {
  it('é um grupo de escolha única navegável pelas setas', async () => {
    const user = userEvent.setup()
    function Harness() {
      const [value, setValue] = useState<'all' | 'image' | 'video'>('all')
      return (
        <Segmented
          ariaLabel="Tipo de estímulo"
          value={value}
          onChange={setValue}
          options={[
            { value: 'all', label: 'Todos' },
            { value: 'image', label: 'Imagens' },
            { value: 'video', label: 'Vídeos' },
          ]}
        />
      )
    }
    render(<Harness />)
    expect(screen.getByRole('radio', { name: 'Todos' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('radio', { name: 'Vídeos' }))
    expect(screen.getByRole('radio', { name: 'Vídeos' })).toHaveAttribute('aria-checked', 'true')
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('radio', { name: 'Todos' })).toHaveAttribute('aria-checked', 'true')
  })
})
