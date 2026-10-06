import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../App'
import type { PatientDetail, PatientRow } from '../../api/patients'
import { mockApi, reply } from '../../test/api'
import { ADMIN, RESEARCHER } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

function row(id: string, code: string, name: string, birth: string, extra: Partial<PatientRow> = {}): PatientRow {
  return { id, code, name, birth_date: birth, status: 'active', sessions_count: 0, last_session_at: null, ...extra }
}

const ROWS = [
  row('p14', 'P-014', 'Mariana Alves', '1998-03-12', { sessions_count: 3, last_session_at: '2026-09-29T14:10:00Z' }),
  row('p09', 'P-009', 'Rafael Nunes', '2001-11-05'),
  row('p03', 'P-003', 'Joana Prado', '1990-01-30', { status: 'inactive' }),
]

const PAGE = { items: ROWS.slice(0, 2), total: 15, page: 1, page_size: 8, counts: { active: 15, inactive: 1 } }

const MARIANA: PatientDetail = {
  id: 'p14',
  code: 'P-014',
  name: 'Mariana Alves',
  birth_date: '1998-03-12',
  sex: 'female',
  vision_correction: 'glasses',
  consent_signed: true,
  consent_date: '2026-09-01',
  consent_file: { name: 'termo-P-014.pdf', size: 212 * 1024 },
  notes: 'Prefere sessões no período da manhã.',
  status: 'active',
  created_at: '2026-09-01T13:00:00Z',
  created_by_name: 'Ana Souza',
  sessions_count: 0,
  sessions: [],
}

describe('W06 Lista de pacientes', () => {
  it('mostra os pacientes, a contagem e as ações de cada linha', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /patients': PAGE })
    renderWithProviders(<App />, { route: '/pacientes' })
    expect(await screen.findByText('15 pacientes cadastrados.')).toBeInTheDocument()
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('P-014')).toBeInTheDocument()
    expect(within(rows[0]).getByRole('link', { name: 'Mariana Alves' })).toHaveAttribute('href', '/pacientes/p14')
    expect(within(rows[0]).getByText('12/03/1998')).toBeInTheDocument()
    expect(within(rows[0]).getByText('3')).toBeInTheDocument()
    expect(within(rows[0]).getByText('29/09/2026')).toBeInTheDocument()
    expect(within(rows[0]).getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/pacientes/p14/editar')
    expect(within(rows[0]).getByRole('link', { name: 'Nova sessão' })).toHaveAttribute('href', '/sessoes/nova?paciente=p14')
    expect(within(rows[1]).getByText('—')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Novo paciente' })).toHaveAttribute('href', '/pacientes/novo')
    expect(screen.getByText('Mostrando 1 a 8 de 15')).toBeInTheDocument()
  })

  it('mostra os inativos pelo filtro, sem "Nova sessão" para eles', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /patients': ({ query }) => (query.get('include_inactive') === 'true' ? { ...PAGE, items: ROWS, total: 16 } : PAGE),
    })
    renderWithProviders(<App />, { route: '/pacientes' })
    await user.click(await screen.findByRole('checkbox', { name: 'Mostrar inativos' }))
    expect(await screen.findByText('15 pacientes cadastrados e 1 inativo.')).toBeInTheDocument()
    const inactive = screen.getByRole('row', { name: /Joana Prado/ })
    expect(within(inactive).getByText('Inativo')).toBeInTheDocument()
    expect(within(inactive).queryByRole('link', { name: 'Nova sessão' })).not.toBeInTheDocument()
    expect(api.callsTo('GET', '/patients').at(-1)!.query.get('include_inactive')).toBe('true')
  })

  it('busca por nome ou código', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /me': RESEARCHER, 'GET /patients': { ...PAGE, items: [], total: 0 } })
    renderWithProviders(<App />, { route: '/pacientes' })
    await user.type(await screen.findByRole('searchbox', { name: 'Buscar por nome ou código' }), 'P-0')
    expect(await screen.findByText('Nenhum paciente encontrado com essa busca.')).toBeInTheDocument()
    expect(api.callsTo('GET', '/patients').at(-1)!.query.get('q')).toBe('P-0')
  })

  it('sem permissão de editar, some "Novo paciente" e "Editar"', async () => {
    mockApi({ 'GET /me': { ...RESEARCHER, permissions: ['patients.view'] }, 'GET /patients': PAGE })
    renderWithProviders(<App />, { route: '/pacientes' })
    await screen.findByText('Mariana Alves')
    expect(screen.queryByRole('link', { name: 'Novo paciente' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nova sessão' })).not.toBeInTheDocument()
  })

  it('sem "Ver pacientes" o menu esconde Pacientes e a rota mostra "Sem acesso"', async () => {
    mockApi({ 'GET /me': { ...RESEARCHER, permissions: ['stimuli.edit'] } })
    renderWithProviders(<App />, { route: '/pacientes' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Sem acesso' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Menu principal' })
    expect(within(nav).queryByRole('link', { name: 'Pacientes' })).not.toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Estímulos' })).toBeInTheDocument()
  })
})

describe('W07 Novo e Editar paciente', () => {
  it('novo: sugere o código, valida e cadastra com o PDF do termo', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /patients/next-code': { code: 'P-016' },
      'POST /patients': ({ body }) => ({ ...MARIANA, id: 'p16', code: JSON.parse((body as { data: string }).data).code }),
      'GET /patients/:id': { ...MARIANA, id: 'p16', code: 'P-016' },
    })
    renderWithProviders(<App />, { route: '/pacientes/novo' })
    expect(await screen.findByLabelText('Código do participante')).toHaveValue('P-016')
    expect(screen.getByText('O código identifica o paciente nas análises e exportações, sem expor o nome.')).toBeInTheDocument()
    expect(screen.getByText('Nenhum arquivo anexado')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cadastrar paciente' }))
    expect(screen.getByText('Informe o nome completo.')).toBeInTheDocument()
    expect(screen.getByText('Informe a data de nascimento.')).toBeInTheDocument()
    expect(screen.getAllByText('Escolha uma opção.')).toHaveLength(2)
    expect(api.callsTo('POST', '/patients')).toHaveLength(0)

    await user.type(screen.getByLabelText('Nome completo'), 'Mariana Alves')
    await user.type(screen.getByLabelText('Data de nascimento'), '12031998')
    expect(screen.getByLabelText('Data de nascimento')).toHaveValue('12/03/1998')
    await user.click(screen.getByRole('radio', { name: 'Feminino' }))
    await user.click(screen.getByRole('radio', { name: 'Óculos de grau' }))

    // Anexar o PDF marca o termo como assinado; a data passa a ser exigida.
    const pdf = new File(['%PDF-1.4'], 'termo-P-016.pdf', { type: 'application/pdf' })
    await user.upload(document.querySelector('input[type="file"]') as HTMLInputElement, pdf)
    expect(screen.getByRole('checkbox', { name: 'Termo assinado pelo paciente' })).toBeChecked()
    expect(screen.getByText(/termo-P-016\.pdf/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cadastrar paciente' }))
    expect(screen.getByText('Informe a data da assinatura.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Data da assinatura'), '01092026')
    await user.type(screen.getByLabelText('Observações'), 'Prefere manhã.')
    await user.click(screen.getByRole('button', { name: 'Cadastrar paciente' }))
    expect(await screen.findByText('Paciente P-016 cadastrado.')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 1, name: 'Mariana Alves' })).toBeInTheDocument()

    const sent = api.callsTo('POST', '/patients')[0].body as { data: string; consent_file: File }
    expect(JSON.parse(sent.data)).toEqual({
      code: 'P-016',
      name: 'Mariana Alves',
      birth_date: '1998-03-12',
      sex: 'female',
      vision_correction: 'glasses',
      consent_signed: true,
      consent_date: '2026-09-01',
      notes: 'Prefere manhã.',
    })
    expect(sent.consent_file.name).toBe('termo-P-016.pdf')
  })

  it('recusa um termo que não é PDF e mostra o código repetido no campo', async () => {
    // Arrastar e soltar não respeita o accept do campo: a tela confere o arquivo.
    const user = userEvent.setup({ applyAccept: false })
    mockApi({
      'GET /me': RESEARCHER,
      'GET /patients/next-code': { code: 'P-016' },
      'POST /patients': reply(409, { detail: 'já existe um paciente com este código' }),
    })
    renderWithProviders(<App />, { route: '/pacientes/novo' })
    const input = (await screen.findByLabelText('Código do participante')).ownerDocument.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, new File(['x'], 'termo.docx'))
    expect(screen.getByText('Anexe o termo em PDF.')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Termo assinado pelo paciente' })).not.toBeChecked()

    await user.clear(screen.getByLabelText('Código do participante'))
    await user.type(screen.getByLabelText('Código do participante'), 'p-014')
    await user.type(screen.getByLabelText('Nome completo'), 'Outra Pessoa')
    await user.type(screen.getByLabelText('Data de nascimento'), '01011990')
    await user.click(screen.getByRole('radio', { name: 'Prefiro não informar' }))
    await user.click(screen.getByRole('radio', { name: 'Não' }))
    await user.click(screen.getByRole('button', { name: 'Cadastrar paciente' }))
    expect(await screen.findByText('Já existe um paciente com este código.')).toBeInTheDocument()
  })

  it('editar: mostra o termo salvo; desmarcar a assinatura tira a data e o PDF', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /patients/:id': MARIANA,
      'PUT /patients/:id': ({ body }) => ({ ...MARIANA, ...JSON.parse((body as { data: string }).data) }),
    })
    renderWithProviders(<App />, { route: '/pacientes/p14/editar' })
    expect(await screen.findByText('As alterações ficam registradas na auditoria.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Editar paciente' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Mariana Alves' })).toHaveAttribute('href', '/pacientes/p14')
    expect(screen.getByLabelText('Data de nascimento')).toHaveValue('12/03/1998')
    expect(screen.getByRole('radio', { name: 'Feminino' })).toBeChecked()
    expect(screen.getByText('termo-P-014.pdf (212 KB)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trocar arquivo' })).toBeInTheDocument()
    expect(screen.getByLabelText('Observações')).toHaveValue('Prefere sessões no período da manhã.')

    await user.click(screen.getByRole('checkbox', { name: 'Termo assinado pelo paciente' }))
    expect(screen.getByLabelText('Data da assinatura')).toHaveValue('')
    expect(screen.getByText('Nenhum arquivo anexado')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByText('Alterações salvas.')).toBeInTheDocument()
    const sent = api.callsTo('PUT', '/patients/p14')[0].body as { data: string; consent_file?: File }
    expect(JSON.parse(sent.data)).toMatchObject({ consent_signed: false, consent_date: null })
    expect(sent.consent_file).toBeUndefined()
  })
})

describe('W08 Detalhes do paciente', () => {
  it('mostra os dados, a idade, o termo e o histórico', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 5, 12))
    mockApi({ 'GET /me': RESEARCHER, 'GET /patients/:id': MARIANA })
    renderWithProviders(<App />, { route: '/pacientes/p14' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Mariana Alves' })).toBeInTheDocument()
    vi.useRealTimers()
    expect(screen.getByText('P-014')).toBeInTheDocument()
    expect(screen.getByText('Cadastrada em 01/09/2026 por Ana Souza.')).toBeInTheDocument()
    expect(screen.getByText('12/03/1998 (28 anos)')).toBeInTheDocument()
    expect(screen.getByText('Óculos de grau')).toBeInTheDocument()
    expect(screen.getByText('Assinado em 01/09/2026')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver termo (PDF)' })).toHaveAttribute('href', '/api/v1/patients/p14/consent')
    expect(screen.getByText('Ativo')).toBeInTheDocument()
    expect(screen.getByText('Prefere sessões no período da manhã.')).toBeInTheDocument()
    expect(screen.getByText('0 sessões')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma sessão com este paciente ainda.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Editar' })).toHaveAttribute('href', '/pacientes/p14/editar')
    expect(screen.getByRole('link', { name: 'Nova sessão' })).toHaveAttribute('href', '/sessoes/nova?paciente=p14')
    // O pesquisador não inativa pacientes (W21).
    expect(screen.queryByRole('button', { name: 'Inativar paciente' })).not.toBeInTheDocument()
  })

  it('o admin inativa e reativa', async () => {
    const user = userEvent.setup()
    let status = 'active'
    const api = mockApi({
      'GET /me': ADMIN,
      'GET /patients/:id': () => ({ ...MARIANA, status }),
      'PUT /patients/:id/status': ({ body }) => {
        status = (body as { status: string }).status
        return { ...MARIANA, status }
      },
    })
    renderWithProviders(<App />, { route: '/pacientes/p14' })
    await user.click(await screen.findByRole('button', { name: 'Inativar paciente' }))
    expect(await screen.findByText('P-014 inativado. O cadastro saiu das listas.')).toBeInTheDocument()
    expect(api.callsTo('PUT', '/patients/p14/status')[0].body).toEqual({ status: 'inactive' })
    expect(screen.getByText('Inativo')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nova sessão' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reativar paciente' }))
    expect(await screen.findByText('P-014 reativado.')).toBeInTheDocument()
  })

  it('termo não assinado e paciente sem observações', async () => {
    mockApi({
      'GET /me': RESEARCHER,
      'GET /patients/:id': { ...MARIANA, sex: 'male', consent_signed: false, consent_date: null, consent_file: null, notes: null },
    })
    renderWithProviders(<App />, { route: '/pacientes/p14' })
    expect(await screen.findByText('Não assinado')).toBeInTheDocument()
    expect(screen.getByText('Cadastrado em 01/09/2026 por Ana Souza.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma observação.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ver termo (PDF)' })).not.toBeInTheDocument()
  })
})
