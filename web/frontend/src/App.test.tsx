import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import App from './App'
import { APP_SCREENS, AUTH_SCREENS, FULLSCREEN_SCREENS } from './routes'
import { renderWithProviders } from './test/render'

const sample = (path: string) => path.replace(':sessionId', 's1').replace(':patientId', 'p1').replace(':stimulusId', 'e1').replace(':userId', 'u1')

describe('rotas', () => {
  it.each(APP_SCREENS.map((s) => [s.path, s] as const))('%s abre o placeholder dentro do menu lateral', (path, screenRoute) => {
    renderWithProviders(<App />, { route: sample(path) })
    expect(screen.getByRole('heading', { level: 1, name: screenRoute.title })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Menu principal' })).toBeInTheDocument()
    expect(screen.getByText(`Segue o protótipo ${screenRoute.prototypes.join(' e ')}`, { exact: false })).toBeInTheDocument()
    expect(document.title).toBe(`${screenRoute.title} · NeuroSight`)
  })

  it.each(AUTH_SCREENS.map((s) => [s.path, s] as const))('%s abre no layout de acesso, sem menu', (path, screenRoute) => {
    renderWithProviders(<App />, { route: path })
    expect(screen.getByRole('heading', { level: 1, name: screenRoute.title })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Menu principal' })).not.toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: 'Sobre o NeuroSight' })).toHaveTextContent('Rastreamento ocular e emocional com Meta Quest Pro')
  })

  it('o controle ao vivo é em tela cheia, sem menu', () => {
    renderWithProviders(<App />, { route: sample(FULLSCREEN_SCREENS[0].path) })
    expect(screen.getByRole('heading', { level: 1, name: 'Controle da sessão ao vivo' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Menu principal' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Detalhes da sessão' })).toHaveAttribute('href', '/sessoes/s1')
  })

  it('o link de voltar usa os parâmetros da rota', () => {
    renderWithProviders(<App />, { route: '/sessoes/abc/analise' })
    expect(screen.getByRole('link', { name: 'Detalhes da sessão' })).toHaveAttribute('href', '/sessoes/abc')
  })

  it('/admin leva para Usuários, com as três abas', () => {
    renderWithProviders(<App />, { route: '/admin' })
    const tabs = screen.getByRole('navigation', { name: 'Administração' })
    expect(tabs).toHaveTextContent('UsuáriosPerfis e permissõesAuditoria')
    expect(screen.getByRole('link', { name: 'Usuários' })).toHaveAttribute('aria-current', 'page')
  })

  it('rota desconhecida mostra a página não encontrada', () => {
    renderWithProviders(<App />, { route: '/nao/existe' })
    expect(screen.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar para o início' })).toHaveAttribute('href', '/')
  })
})
