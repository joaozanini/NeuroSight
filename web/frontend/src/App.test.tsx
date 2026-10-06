import { afterEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { mockApi, reply } from './test/api'
import { ADMIN, RESEARCHER } from './test/fixtures'
import { renderWithProviders } from './test/render'

function loggedAs(me: typeof ADMIN | null, routes: Record<string, unknown> = {}) {
  return mockApi({ 'GET /me': me ?? reply(401, { detail: 'não autenticado' }), ...routes })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('rotas', () => {
  it('/ abre o Início dentro do menu lateral, com o selo de sessões', async () => {
    loggedAs(ADMIN, { 'GET /dashboard/badge': { sessions: 2 } })
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Olá, Carlos' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Menu principal' })
    expect(await within(nav).findByRole('link', { name: /Sessões\s*2 em andamento ou aguardando dados/ })).toBeInTheDocument()
    expect(document.title).toBe('Início · NeuroSight')
  })

  it.each([
    ['/login', 'Entrar'],
    ['/esqueci-senha', 'Esqueceu a senha?'],
    ['/redefinir-senha', 'Link inválido ou expirado'],
    ['/aceitar-convite', 'Link inválido ou expirado'],
  ])('%s abre no layout de acesso, sem menu', async (path, title) => {
    loggedAs(null)
    renderWithProviders(<App />, { route: path })
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Menu principal' })).not.toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: 'Sobre o NeuroSight' })).toHaveTextContent('Rastreamento ocular e emocional com Meta Quest Pro')
  })

  it('sem login, a área interna leva ao login guardando a página', async () => {
    loggedAs(null)
    renderWithProviders(<App />, { route: '/pacientes?q=ana' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Entrar' })).toBeInTheDocument()
  })

  it('o link de voltar usa os parâmetros da rota', async () => {
    loggedAs(ADMIN)
    renderWithProviders(<App />, { route: '/sessoes/abc/analise' })
    expect(await screen.findByRole('link', { name: 'Detalhes da sessão' })).toHaveAttribute('href', '/sessoes/abc')
  })

  it('rota desconhecida mostra a página não encontrada', async () => {
    loggedAs(ADMIN)
    renderWithProviders(<App />, { route: '/nao/existe' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar para o início' })).toHaveAttribute('href', '/')
  })
})

describe('menu e permissões', () => {
  it('o rodapé do menu mostra quem está logado, e Sair volta ao login', async () => {
    const user = userEvent.setup()
    let loggedIn = true
    const api = mockApi({
      'GET /me': () => (loggedIn ? RESEARCHER : reply(401, { detail: 'não autenticado' })),
      'POST /auth/logout': () => {
        loggedIn = false
      },
    })
    renderWithProviders(<App />, { route: '/pacientes' })
    const profile = await screen.findByRole('link', { name: /Ana Souza\s*Pesquisador/ })
    expect(profile).toHaveAttribute('href', '/perfil')
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Entrar' })).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/logout')).toHaveLength(1)
  })

  it('o pesquisador não vê Administração e recebe "Sem acesso" nas rotas dela', async () => {
    loggedAs(RESEARCHER)
    renderWithProviders(<App />, { route: '/admin/usuarios' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Sem acesso' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Menu principal' })
    expect(within(nav).queryByRole('link', { name: 'Administração' })).not.toBeInTheDocument()
  })

  it('/admin leva para Usuários, com as três abas', async () => {
    loggedAs(ADMIN, { 'GET /users': { items: [], total: 0, page: 1, page_size: 8 } })
    renderWithProviders(<App />, { route: '/admin' })
    const tabs = await screen.findByRole('navigation', { name: 'Administração' })
    expect(tabs).toHaveTextContent('UsuáriosPerfis e permissõesAuditoria')
    expect(screen.getByRole('link', { name: 'Usuários' })).toHaveAttribute('aria-current', 'page')
  })

  it('com a permissão da auditoria, o pesquisador vê só essa aba', async () => {
    loggedAs(
      { ...RESEARCHER, permissions: [...RESEARCHER.permissions, 'admin.audit'] },
      {
        'GET /audit': { items: [], total: 0, page: 1, page_size: 10 },
        'GET /audit/filters': { actions: [], entity_types: [], roles: [], users: [] },
      },
    )
    renderWithProviders(<App />, { route: '/admin' })
    const tabs = await screen.findByRole('navigation', { name: 'Administração' })
    expect(within(tabs).getAllByRole('link').map((a) => a.textContent)).toEqual(['Auditoria'])
    expect(screen.getByRole('link', { name: 'Administração' })).toBeInTheDocument()
  })
})
