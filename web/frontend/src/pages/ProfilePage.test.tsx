import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import { mockApi, reply } from '../test/api'
import { RESEARCHER } from '../test/fixtures'
import { renderWithProviders } from '../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('W05 Meu perfil', () => {
  it('mostra os dados da conta só para leitura', async () => {
    mockApi({ 'GET /me': RESEARCHER })
    renderWithProviders(<App />, { route: '/perfil' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Meu perfil' })).toBeInTheDocument()
    expect(screen.getByText('ana.souza@exemplo.com')).toBeInTheDocument()
    expect(screen.getByText('Nome, e-mail e perfil são definidos pelo administrador. Para corrigir algum dado, fale com ele.')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Nome' })).not.toBeInTheDocument()
  })

  it('senha atual errada aparece no campo; a troca certa limpa o formulário', async () => {
    const user = userEvent.setup()
    let attempts = 0
    const api = mockApi({
      'GET /me': RESEARCHER,
      'PUT /me/password': () => (++attempts === 1 ? reply(400, { detail: 'a senha atual está incorreta' }) : undefined),
    })
    renderWithProviders(<App />, { route: '/perfil' })
    await user.type(await screen.findByLabelText('Senha atual'), 'errada')
    await user.type(screen.getByLabelText('Nova senha'), 'Nova#senha9')
    await user.type(screen.getByLabelText('Confirmar nova senha'), 'Nova#senha9')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(await screen.findByText('A senha atual está incorreta.')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Senha atual'))
    await user.type(screen.getByLabelText('Senha atual'), 'Senha#forte1')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(await screen.findByText('Senha alterada.')).toBeInTheDocument()
    expect(screen.getByLabelText('Senha atual')).toHaveValue('')
    expect(api.callsTo('PUT', '/me/password')[1].body).toEqual({ current_password: 'Senha#forte1', new_password: 'Nova#senha9' })
  })
})
