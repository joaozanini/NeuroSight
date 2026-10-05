import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../App'
import type { UserDetail, UserSummary } from '../../api/users'
import { mockApi, reply } from '../../test/api'
import { ADMIN, ALL_PERMISSIONS } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { periodStart } from './AuditPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const today = new Date()
today.setHours(9, 2, 0, 0)

function user(id: string, name: string, status: UserSummary['status'], role: UserSummary['role'] = 'researcher'): UserSummary {
  const email = `${name.toLowerCase().replace(' ', '.')}@exemplo.com`
  return { id, name, email, role, status, last_login_at: status === 'invited' ? null : today.toISOString(), created_at: '2026-08-12T12:00:00Z' }
}

const USERS = [
  user('u1', 'Carlos Lima', 'active', 'admin'),
  user('u2', 'Ana Souza', 'active'),
  user('u3', 'Igor Mendes', 'invited'),
  user('u8', 'Fernanda Lopes', 'inactive'),
]

function detail(summary: UserSummary): UserDetail {
  return { ...summary, created_by_name: 'Carlos Lima', sessions_as_owner: 2 }
}

const LINK = { email_sent: false, link: 'http://site/aceitar-convite?token=xyz', expires_at: '2026-10-12T18:00:00Z' }

describe('W19 Lista de usuários', () => {
  it('mostra o selo Você e as ações conforme o status', async () => {
    mockApi({ 'GET /me': ADMIN, 'GET /users': { items: USERS, total: 14, page: 1, page_size: 8 } })
    renderWithProviders(<App />, { route: '/admin/usuarios' })
    await screen.findByText('Ana Souza')
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('Você')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Hoje, 09:02')).toBeInTheDocument()
    expect(within(rows[0]).queryByRole('button')).not.toBeInTheDocument()
    expect(within(rows[1]).getByRole('button', { name: 'Desativar' })).toBeInTheDocument()
    expect(within(rows[2]).getByText('Convite pendente')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Nunca acessou')).toBeInTheDocument()
    expect(within(rows[2]).getByRole('button', { name: 'Reenviar convite' })).toBeInTheDocument()
    expect(within(rows[3]).getByRole('button', { name: 'Ativar' })).toBeInTheDocument()
    expect(within(rows[1]).getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/admin/usuarios/u2')
    expect(screen.getByText('Mostrando 1 a 8 de 14 usuários')).toBeInTheDocument()
  })

  it('filtra pela URL e desativa pela linha', async () => {
    const user_ = userEvent.setup()
    const api = mockApi({
      'GET /me': ADMIN,
      'GET /users': { items: USERS, total: 4, page: 1, page_size: 8 },
      'PATCH /users/:id': ({ params, body }) => ({ ...detail(USERS[1]), id: params.id, ...(body as object) }),
    })
    renderWithProviders(<App />, { route: '/admin/usuarios' })
    await user_.selectOptions(await screen.findByLabelText('Status'), 'invited')
    expect(api.callsTo('GET', '/users').at(-1)!.query.get('status')).toBe('invited')

    await user_.click(screen.getAllByRole('button', { name: 'Desativar' })[0])
    expect(await screen.findByText('Acesso de Ana Souza desativado.')).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/users/u2')[0].body).toEqual({ status: 'inactive' })
  })

  it('sem e-mail, o reenvio do convite mostra o link para copiar', async () => {
    const user_ = userEvent.setup()
    mockApi({
      'GET /me': ADMIN,
      'GET /users': { items: USERS, total: 4, page: 1, page_size: 8 },
      'POST /users/:id/resend-invite': LINK,
    })
    renderWithProviders(<App />, { route: '/admin/usuarios' })
    await user_.click(await screen.findByRole('button', { name: 'Reenviar convite' }))
    const dialog = await screen.findByRole('dialog', { name: 'Copie o link do convite' })
    expect(within(dialog).getByRole('textbox', { name: 'Link' })).toHaveValue(LINK.link)
    expect(dialog).toHaveTextContent('entregue para Igor Mendes')
  })
})

describe('W20 Novo e Editar usuário', () => {
  it('novo usuário: valida, cria e mostra o link quando o e-mail não sai', async () => {
    const user_ = userEvent.setup()
    const api = mockApi({
      'GET /me': ADMIN,
      'POST /users': ({ body }) => ({ user: detail({ ...USERS[2], ...(body as object) }), invite: LINK }),
      'GET /users': { items: USERS, total: 4, page: 1, page_size: 8 },
    })
    renderWithProviders(<App />, { route: '/admin/usuarios/novo' })
    expect(await screen.findByRole('heading', { name: 'Como o acesso é liberado' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Pesquisador/ })).toBeChecked()
    await user_.click(screen.getByRole('button', { name: 'Salvar e enviar convite' }))
    expect(screen.getByText('Informe o nome completo.')).toBeInTheDocument()

    await user_.type(screen.getByLabelText('Nome completo'), 'Igor Mendes')
    await user_.type(screen.getByLabelText('E-mail'), 'igor.mendes@exemplo.com')
    await user_.click(screen.getByRole('radio', { name: /Admin/ }))
    await user_.click(screen.getByRole('button', { name: 'Salvar e enviar convite' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('entregue para Igor Mendes')
    expect(api.callsTo('POST', '/users')[0].body).toEqual({ name: 'Igor Mendes', email: 'igor.mendes@exemplo.com', role: 'admin' })
    await user_.click(within(dialog).getAllByRole('button', { name: 'Fechar' })[0])
    expect(await screen.findByRole('heading', { level: 1, name: 'Administração' })).toBeInTheDocument()
  })

  it('e-mail repetido aparece no campo', async () => {
    const user_ = userEvent.setup()
    mockApi({ 'GET /me': ADMIN, 'POST /users': reply(409, { detail: 'já existe um usuário com este e-mail' }) })
    renderWithProviders(<App />, { route: '/admin/usuarios/novo' })
    await user_.type(await screen.findByLabelText('Nome completo'), 'Ana')
    await user_.type(screen.getByLabelText('E-mail'), 'ana.souza@exemplo.com')
    await user_.click(screen.getByRole('button', { name: 'Salvar e enviar convite' }))
    expect(await screen.findByText('Já existe um usuário com este e-mail.')).toBeInTheDocument()
  })

  it('editar: mostra o acesso, salva o status e envia a redefinição', async () => {
    const user_ = userEvent.setup()
    const api = mockApi({
      'GET /me': ADMIN,
      'GET /users/:id': detail(USERS[1]),
      'PATCH /users/:id': detail({ ...USERS[1], status: 'inactive' }),
      'POST /users/:id/send-reset': { ...LINK, email_sent: true, link: null },
      'GET /users': { items: USERS, total: 4, page: 1, page_size: 8 },
    })
    renderWithProviders(<App />, { route: '/admin/usuarios/u2' })
    expect(await screen.findByText('As alterações ficam registradas na auditoria.')).toBeInTheDocument()
    const access = screen.getByRole('complementary', { name: 'Acesso' })
    expect(access).toHaveTextContent('Criado em12/08/2026')
    expect(access).toHaveTextContent('Criado porCarlos Lima')
    expect(access).toHaveTextContent('Sessões como responsável2')

    await user_.click(within(access).getByRole('button', { name: 'Enviar redefinição de senha' }))
    expect(await screen.findByText('Link de redefinição enviado para ana.souza@exemplo.com.')).toBeInTheDocument()

    await user_.click(screen.getByRole('radio', { name: 'Inativo' }))
    await user_.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByText('Alterações salvas.')).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/users/u2')[0].body).toEqual({
      name: 'Ana Souza', email: 'ana.souza@exemplo.com', role: 'researcher', status: 'inactive',
    })
  })

  it('na própria conta, perfil e status ficam travados e não são enviados', async () => {
    const user_ = userEvent.setup()
    const api = mockApi({ 'GET /me': ADMIN, 'GET /users/:id': detail(USERS[0]), 'PATCH /users/:id': detail(USERS[0]), 'GET /users': { items: USERS, total: 4, page: 1, page_size: 8 } })
    renderWithProviders(<App />, { route: '/admin/usuarios/u1' })
    expect(await screen.findByText('Você não pode mudar o próprio perfil.')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Inativo' })).toBeDisabled()
    await user_.clear(screen.getByLabelText('Nome completo'))
    await user_.type(screen.getByLabelText('Nome completo'), 'Carlos A. Lima')
    await user_.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByText('Alterações salvas.')).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/users/u1')[0].body).toEqual({ name: 'Carlos A. Lima', email: 'carlos.lima@exemplo.com' })
  })
})

const MATRIX = {
  roles: [
    { id: 'admin', label: 'Admin', description: '' },
    { id: 'researcher', label: 'Pesquisador', description: '' },
  ],
  groups: [
    { label: 'Pacientes', permissions: [{ id: 'patients.deactivate', label: 'Inativar pacientes', description: null }] },
    {
      label: 'Administração',
      permissions: [
        { id: 'admin.users', label: 'Gerenciar usuários', description: null },
        { id: 'admin.audit', label: 'Consultar a auditoria', description: null },
      ],
    },
  ],
  grants: { admin: ALL_PERMISSIONS, researcher: [] },
  locked: { admin: ['admin.permissions', 'admin.users'] },
}

describe('W21 Perfis e permissões', () => {
  it('trava as do Admin, liga os botões só com mudanças e salva a matriz', async () => {
    const user_ = userEvent.setup()
    const api = mockApi({
      'GET /me': ADMIN,
      'GET /permissions': MATRIX,
      'PUT /permissions': ({ body }) => ({ ...MATRIX, grants: (body as { grants: object }).grants }),
    })
    renderWithProviders(<App />, { route: '/admin/permissoes' })
    const locked = await screen.findByRole('checkbox', { name: 'Admin: Gerenciar usuários (sempre marcada)' })
    expect(locked).toBeChecked()
    expect(locked).toBeDisabled()
    expect(screen.getByText('Todas as alterações estão salvas.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar permissões' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Descartar' })).toBeDisabled()

    const audit = screen.getByRole('checkbox', { name: 'Pesquisador: Consultar a auditoria' })
    await user_.click(audit)
    expect(screen.getByText('Há alterações não salvas.')).toBeInTheDocument()
    await user_.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(audit).not.toBeChecked()

    await user_.click(audit)
    await user_.click(screen.getByRole('button', { name: 'Salvar permissões' }))
    expect(await screen.findByText('Permissões salvas.')).toBeInTheDocument()
    expect(api.callsTo('PUT', '/permissions')[0].body).toEqual({ grants: { admin: ALL_PERMISSIONS, researcher: ['admin.audit'] } })
    expect(screen.getByText('Todas as alterações estão salvas.')).toBeInTheDocument()
  })
})

const FILTERS = {
  actions: [
    { value: 'login', label: 'Login' },
    { value: 'visibility_change', label: 'Mudança de visibilidade' },
  ],
  entity_types: [
    { value: 'session', label: 'Sessão' },
    { value: 'system', label: 'Sistema' },
  ],
  roles: [{ value: 'admin', label: 'Admin' }],
  users: [{ value: 'u1', label: 'Carlos Lima' }],
}

const ENTRY = {
  id: 7,
  created_at: '2026-09-29T17:31:07Z',
  user_id: 'u1',
  user_name: 'Carlos Lima',
  user_role: 'admin',
  action: 'visibility_change',
  entity_type: 'session',
  entity_id: 's15',
  entity_label: 'Rostos neutros e expressivos, paciente P-015',
  ip: '10.0.4.12',
}

describe('W22 Auditoria e W23 Detalhes', () => {
  it('lista, filtra e abre o detalhe com o que mudou', async () => {
    const user_ = userEvent.setup()
    const api = mockApi({
      'GET /me': ADMIN,
      'GET /audit/filters': FILTERS,
      'GET /audit': { items: [ENTRY], total: 1248, page: 1, page_size: 10 },
      'GET /audit/:id': {
        ...ENTRY,
        user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0 Safari/537.36',
        changes: [
          { field: 'visibility', label: 'Visibilidade', before: 'Só o responsável', after: 'Pesquisadores escolhidos' },
          { field: 'shared', label: 'Pesquisadores com acesso', before: null, after: 'Bruno Castro' },
        ],
      },
    })
    renderWithProviders(<App />, { route: '/admin/auditoria' })
    await screen.findByText('Rostos neutros e expressivos, paciente P-015')
    const row = screen.getAllByRole('row')[1]
    expect(await within(row).findByText('Mudança de visibilidade')).toBeInTheDocument()
    expect(row).toHaveTextContent('SessãoRostos neutros e expressivos, paciente P-015')
    expect(screen.getByText('Mostrando 1 a 10 de 1.248 registros')).toBeInTheDocument()
    expect(api.callsTo('GET', '/audit')[0].query.get('since')).toBe(periodStart('7d'))
    expect(screen.getByRole('link', { name: 'Exportar CSV' }).getAttribute('href')).toMatch(/^\/api\/v1\/audit\/export\.csv\?since=.+&tz=/)

    await user_.selectOptions(screen.getByLabelText('Ação'), 'login')
    expect(api.callsTo('GET', '/audit').at(-1)!.query.get('action')).toBe('login')

    await user_.click(within(row).getByRole('button', { name: /Detalhes/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Mudança de visibilidade' })
    expect(await within(dialog).findByText('Carlos Lima, perfil Admin')).toBeInTheDocument()
    expect(dialog).toHaveTextContent('IP 10.0.4.12, Chrome no Windows')
    expect(within(dialog).getByRole('link', { name: 'Abrir sessão' })).toHaveAttribute('href', '/sessoes/s15')
    const changes = within(dialog).getAllByRole('row').map((r) => r.textContent)
    expect(changes).toEqual(['CampoAntesDepois', 'VisibilidadeSó o responsávelPesquisadores escolhidos', 'Pesquisadores com acesso—Bruno Castro'])
    expect(dialog).toHaveTextContent('Registros de auditoria não podem ser editados nem apagados.')
  })

  it('o período começa no início do dia, no fuso de quem olha', () => {
    const now = new Date(2026, 8, 29, 14, 31)
    expect(periodStart('hoje', now)).toBe(new Date(2026, 8, 29).toISOString())
    expect(periodStart('7d', now)).toBe(new Date(2026, 8, 23).toISOString())
    expect(periodStart('tudo', now)).toBeUndefined()
  })
})
