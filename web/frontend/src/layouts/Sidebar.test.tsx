import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ROUTER_FUTURE } from '../test/render'
import Sidebar from './Sidebar'

function renderAt(path: string, props: Parameters<typeof Sidebar>[0] = {}) {
  return render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
      <Sidebar {...props} />
    </MemoryRouter>,
  )
}

describe('Sidebar', () => {
  it('lista os itens do menu e marca o da página atual', () => {
    renderAt('/pacientes/p1')
    const nav = screen.getByRole('navigation', { name: 'Menu principal' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(['Início', 'Sessões', 'Pacientes', 'Estímulos'])
    expect(within(nav).getByRole('link', { name: 'Pacientes' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Início' })).not.toHaveAttribute('aria-current')
  })

  it('Início só fica ativo na raiz', () => {
    renderAt('/')
    expect(screen.getByRole('link', { name: 'Início' })).toHaveAttribute('aria-current', 'page')
  })

  it('mostra Administração só com a permissão, ativa em qualquer aba', () => {
    renderAt('/admin/auditoria', { showAdmin: true })
    expect(screen.getByRole('link', { name: 'Administração' })).toHaveAttribute('aria-current', 'page')
  })

  it('mostra o selo de sessões ativas', () => {
    renderAt('/', { sessionsBadge: 2 })
    expect(screen.getByRole('link', { name: /Sessões\s*2 em andamento ou aguardando dados/ })).toBeInTheDocument()
  })

  it('rodapé com o perfil e o Sair quando há usuário', async () => {
    const user = userEvent.setup()
    const onLogout = vi.fn()
    renderAt('/perfil', { user: { name: 'Ana Souza', roleLabel: 'Pesquisador' }, onLogout })
    const profile = screen.getByRole('link', { name: /Ana Souza\s*Pesquisador/ })
    expect(profile).toHaveAttribute('href', '/perfil')
    expect(profile).toHaveAttribute('aria-current', 'page')
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    expect(onLogout).toHaveBeenCalled()
  })

  it('sem usuário não mostra o rodapé', () => {
    renderAt('/')
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument()
  })
})
