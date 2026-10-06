import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../App'
import { mockApi, reply } from '../../test/api'
import { ADMIN, RESEARCHER } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'

const LOGGED_OUT = reply(401, { detail: 'não autenticado' })

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('W01 Login', () => {
  it('valida os campos antes de enviar', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /me': LOGGED_OUT })
    renderWithProviders(<App />, { route: '/login' })
    await user.click(await screen.findByRole('button', { name: 'Entrar' }))
    expect(screen.getByText('Informe o e-mail.')).toBeInTheDocument()
    expect(screen.getByText('Informe a senha.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('E-mail'), 'ana@')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(screen.getByText('Informe um e-mail válido.')).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/login')).toHaveLength(0)
  })

  it('mostra o erro do servidor sem sair da tela', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /me': LOGGED_OUT, 'POST /auth/login': reply(401, { detail: 'e-mail ou senha incorretos' }) })
    renderWithProviders(<App />, { route: '/login' })
    await user.type(await screen.findByLabelText('E-mail'), 'ana.souza@exemplo.com')
    await user.type(screen.getByLabelText('Senha'), 'errada')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha incorretos.')
    expect(screen.getByRole('heading', { level: 1, name: 'Entrar' })).toBeInTheDocument()
  })

  it('entra e volta para a página pedida', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /me': LOGGED_OUT, 'POST /auth/login': RESEARCHER })
    renderWithProviders(<App />, { route: '/login?next=%2Fpacientes' })
    await user.type(await screen.findByLabelText('E-mail'), 'ana.souza@exemplo.com')
    await user.type(screen.getByLabelText('Senha'), 'Senha#forte1')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Pacientes' })).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/login')[0].body).toEqual({ email: 'ana.souza@exemplo.com', password: 'Senha#forte1' })
  })

  it('ignora um ?next= para outro site', async () => {
    mockApi({ 'GET /me': ADMIN })
    renderWithProviders(<App />, { route: '/login?next=%2F%2Fmalicioso.com' })
    expect(await screen.findByRole('heading', { level: 1, name: /^Olá, / })).toBeInTheDocument()
  })

  it('leva o e-mail digitado para o "Esqueci minha senha"', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /me': LOGGED_OUT })
    renderWithProviders(<App />, { route: '/login' })
    await user.type(await screen.findByLabelText('E-mail'), 'ana.souza@exemplo.com')
    await user.click(screen.getByRole('link', { name: 'Esqueci minha senha' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Esqueceu a senha?' })).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveValue('ana.souza@exemplo.com')
  })
})

describe('W02 Esqueci minha senha', () => {
  it('confirma o envio e permite enviar de novo', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /me': LOGGED_OUT, 'POST /auth/forgot': undefined })
    renderWithProviders(<App />, { route: '/esqueci-senha' })
    expect(await screen.findByRole('link', { name: 'Voltar para o login' })).toHaveAttribute('href', '/login')
    await user.type(screen.getByLabelText('E-mail'), 'ana.souza@exemplo.com')
    await user.click(screen.getByRole('button', { name: 'Enviar link' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Confira seu e-mail' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar para o login' })).toHaveAttribute('href', '/login')
    await user.click(screen.getByRole('button', { name: 'Enviar de novo' }))
    expect(await screen.findByText(/um novo link chega em instantes/)).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/forgot').map((c) => c.body)).toEqual([
      { email: 'ana.souza@exemplo.com' },
      { email: 'ana.souza@exemplo.com' },
    ])
  })
})

describe('W03 Definir nova senha', () => {
  it('link inválido oferece pedir outro', async () => {
    mockApi({ 'GET /me': LOGGED_OUT, 'GET /auth/link': reply(404, { detail: 'este link é inválido ou expirou' }) })
    renderWithProviders(<App />, { route: '/redefinir-senha?token=velho' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Link inválido ou expirado' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Pedir um novo link' })).toHaveAttribute('href', '/esqueci-senha')
  })

  it('convite: marca as regras, confere a confirmação e entra no sistema', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': LOGGED_OUT,
      'GET /auth/link': { kind: 'invite', name: 'Igor Mendes', email: 'igor.mendes@exemplo.com' },
      'POST /auth/accept-invite': { ...RESEARCHER, name: 'Igor Mendes' },
    })
    renderWithProviders(<App />, { route: '/aceitar-convite?token=abc' })
    expect(await screen.findByText('Olá, Igor. Crie uma senha para começar a usar o sistema.')).toBeInTheDocument()
    expect(api.callsTo('GET', '/auth/link')[0].query.get('kind')).toBe('invite')

    await user.type(screen.getByLabelText('Senha'), 'Senha123')
    expect(screen.getByText('Pelo menos um símbolo, como ! ou #').parentElement).toHaveTextContent('(pendente)')
    await user.type(screen.getByLabelText('Confirmar senha'), 'Senha123')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(screen.getByText('A senha ainda não atende a todas as regras.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Senha'), '!')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(screen.getByText('As senhas não conferem.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Confirmar senha'), '!')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(await screen.findByRole('heading', { level: 1, name: /^Olá, / })).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/accept-invite')[0].body).toEqual({ token: 'abc', password: 'Senha123!' })
    expect(screen.getByText('Senha criada. Boas-vindas ao NeuroSight!')).toBeInTheDocument()
  })
})
