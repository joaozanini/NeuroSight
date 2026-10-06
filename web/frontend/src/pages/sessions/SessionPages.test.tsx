import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../App'
import type { PatientDetail, PatientRow } from '../../api/patients'
import type { SessionDetail, SessionInput, SessionRow } from '../../api/sessions'
import type { StimulusCard } from '../../api/stimuli'
import { periodStart } from '../../lib/periods'
import { mockApi, reply } from '../../test/api'
import { ADMIN, RESEARCHER } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'

afterEach(() => {
  vi.unstubAllGlobals()
})

function row(id: string, title: string, code: string, extra: Partial<SessionRow> = {}): SessionRow {
  return {
    id,
    title,
    patient_id: `p-${code}`,
    patient_code: code,
    owner_id: RESEARCHER.id,
    owner_name: 'Ana Souza',
    date: '2026-09-29T17:10:00Z',
    status: 'completed',
    visibility: 'private',
    ...extra,
  }
}

const ROWS = [
  row('s1', 'Rostos neutros e expressivos', 'P-014', { status: 'running' }),
  row('s2', 'Paisagens naturais', 'P-009', { status: 'awaiting_data' }),
  row('s3', 'Rostos neutros e expressivos', 'P-015', { status: 'configured', date: '2026-09-28T12:00:00Z' }),
  row('s4', 'Publicidade em vídeo', 'P-011', { status: 'interrupted', visibility: 'shared', owner_id: 'u4', owner_name: 'Bruno Castro' }),
  row('s5', 'Leitura de textos curtos', 'P-007', { visibility: 'all', owner_id: 'u4', owner_name: 'Bruno Castro' }),
]

const PAGE = { items: ROWS, total: 23, page: 1, page_size: 8 }
const OWNERS = [
  { id: 'u2', name: 'Ana Souza' },
  { id: 'u4', name: 'Bruno Castro' },
]

function patient(id: string, code: string, name: string, birth: string, sessions = 0): PatientRow {
  return { id, code, name, birth_date: birth, status: 'active', sessions_count: sessions, last_session_at: null }
}

const PATIENTS = [
  patient('p15', 'P-015', 'Beatriz Carvalho', '1995-07-21'),
  patient('p14', 'P-014', 'Mariana Alves', '1998-03-12', 3),
  patient('p9', 'P-009', 'Rafael Nunes', '2001-11-05', 2),
]

const BEATRIZ: PatientDetail = {
  ...PATIENTS[0],
  sex: 'female',
  vision_correction: 'none',
  consent_signed: true,
  consent_date: '2026-09-02',
  consent_file: null,
  notes: null,
  created_at: '2026-09-02T13:00:00Z',
  created_by_name: 'Ana Souza',
  sessions: [],
}

function stimulus(id: string, name: string, extra: Partial<StimulusCard> = {}): StimulusCard {
  return { id, name, kind: 'image', status: 'active', tags: [], duration_seconds: null, thumbnail_url: `/api/v1/stimuli/${id}/thumbnail`, ...extra }
}

const LIBRARY = {
  items: [
    stimulus('st1', 'Rosto neutro 01'),
    stimulus('st2', 'Rosto alegre 02'),
    stimulus('st3', 'Ondas na praia', { kind: 'video', duration_seconds: 45 }),
  ],
  total: 3,
  page: 1,
  page_size: 48,
  counts: { total: 3, images: 2, videos: 1 },
}

const DETAIL: SessionDetail = {
  id: 's3',
  type: 'media_sequence',
  status: 'configured',
  end_reason: null,
  title: 'Rostos neutros e expressivos',
  objective: 'Comparar o tempo de fixação e as expressões faciais diante de rostos neutros, alegres e surpresos.',
  notes: null,
  record: true,
  visibility: 'private',
  shared_with: [],
  patient: { id: 'p15', code: 'P-015', name: 'Beatriz Carvalho', birth_date: '1995-07-21', sex: 'female' },
  owner: { id: RESEARCHER.id, name: 'Ana Souza' },
  created_at: '2026-09-28T17:26:00Z',
  started_at: null,
  ended_at: null,
  date: '2026-09-28T17:26:00Z',
  duration_seconds: null,
  items: [
    { position: 1, stimulus_id: 'st1', name: 'Rosto neutro 01', kind: 'image', archived: false, duration_seconds: 5, media_duration_seconds: null, thumbnail_url: '/api/v1/stimuli/st1/thumbnail' },
    { position: 2, stimulus_id: 'st3', name: 'Ondas na praia', kind: 'video', archived: false, duration_seconds: null, media_duration_seconds: 45, thumbnail_url: '/api/v1/stimuli/st3/thumbnail' },
    { position: 3, stimulus_id: 'st9', name: 'Rosto antigo', kind: 'image', archived: true, duration_seconds: null, media_duration_seconds: null, thumbnail_url: '/api/v1/stimuli/st9/thumbnail' },
  ],
  duplicated_from: null,
  data_status: 'none',
  data_error: null,
  exposures: [],
  files: null,
  can_edit: true,
  can_run: true,
  can_change_visibility: false,
  can_export: true,
}

describe('W12 Lista de sessões', () => {
  it('mostra as sessões com a ação conforme o status e o responsável', async () => {
    const api = mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/owners': OWNERS, 'GET /sessions': PAGE })
    renderWithProviders(<App />, { route: '/sessoes' })
    expect(await screen.findByText('Suas sessões e as que outros pesquisadores liberaram para você.')).toBeInTheDocument()
    await screen.findByText('Paciente P-014')
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByRole('link', { name: 'Rostos neutros e expressivos' })).toHaveAttribute('href', '/sessoes/s1')
    expect(within(rows[0]).getByText('Paciente P-014')).toBeInTheDocument()
    expect(within(rows[0]).getByText('29/09/2026')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Em andamento')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Privada')).toBeInTheDocument()
    expect(within(rows[0]).getByRole('link', { name: 'Abrir controle' })).toHaveAttribute('href', '/sessoes/s1/controle')
    expect(within(rows[1]).getByRole('link', { name: 'Abrir' })).toHaveAttribute('href', '/sessoes/s2')
    expect(within(rows[2]).getByRole('link', { name: 'Preparar' })).toHaveAttribute('href', '/sessoes/s3/preparar')
    expect(within(rows[3]).getByText('Compartilhada')).toBeInTheDocument()
    expect(within(rows[3]).getByText('Bruno Castro')).toBeInTheDocument()
    expect(within(rows[4]).getByText('Aberta a todos')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Nova sessão' })).toHaveAttribute('href', '/sessoes/nova')
    expect(screen.getByText('Mostrando 1 a 8 de 23')).toBeInTheDocument()
    // Período padrão: últimos 30 dias.
    expect(screen.getByRole('combobox', { name: 'Período' })).toHaveValue('30d')
    expect(api.callsTo('GET', '/sessions')[0].query.get('since')).toBe(periodStart('30d'))
  })

  it('filtra por status, responsável, período e busca', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/owners': OWNERS, 'GET /sessions': { ...PAGE, items: [], total: 0 } })
    renderWithProviders(<App />, { route: '/sessoes' })
    expect(await screen.findByText('Nenhuma sessão encontrada com esses filtros.')).toBeInTheDocument()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'Configurada')
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Responsável' }), 'Bruno Castro')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Período' }), 'Todo o período')
    await user.type(screen.getByRole('searchbox', { name: 'Buscar por título ou paciente' }), 'P-011')
    await waitFor(() => expect(api.callsTo('GET', '/sessions').at(-1)!.query.get('q')).toBe('P-011'))
    const last = api.callsTo('GET', '/sessions').at(-1)!.query
    expect(last.get('status')).toBe('configured')
    expect(last.get('owner_id')).toBe('u4')
    expect(last.get('since')).toBeNull()
  })

  it('sem "Criar e executar sessões", não há Nova sessão nem Preparar', async () => {
    mockApi({
      'GET /me': { ...RESEARCHER, permissions: ['patients.view'] },
      'GET /sessions/owners': OWNERS,
      'GET /sessions': PAGE,
    })
    renderWithProviders(<App />, { route: '/sessoes' })
    await screen.findByText('Paciente P-014')
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[2]).getByRole('link', { name: 'Abrir' })).toHaveAttribute('href', '/sessoes/s3')
    expect(screen.queryByRole('link', { name: 'Nova sessão' })).not.toBeInTheDocument()
  })
})

function wizardApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /me': RESEARCHER,
    'GET /patients': ({ query }: { query: URLSearchParams }) => {
      const q = (query.get('q') ?? '').toLowerCase()
      const items = PATIENTS.filter((p) => !q || p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q))
      return { items, total: q ? items.length : 15, page: 1, page_size: 5, counts: { active: 15, inactive: 0 } }
    },
    'GET /patients/:id': BEATRIZ,
    'GET /stimuli': LIBRARY,
    'POST /sessions': ({ body }: { body: SessionInput }) => ({ ...DETAIL, id: 's99', title: body.title }),
    'GET /sessions/:id': DETAIL,
    ...extra,
  })
}

describe('W13 Nova sessão', () => {
  it('passa pelas quatro etapas e salva a sessão', async () => {
    const user = userEvent.setup()
    const api = wizardApi()
    renderWithProviders(<App />, { route: '/sessoes/nova' })

    // Etapa 1: paciente.
    expect(await screen.findByRole('heading', { name: 'Quem vai participar?' })).toBeInTheDocument()
    expect(screen.getByText('Escolha o paciente. A sessão fica vinculada ao cadastro dele.')).toBeInTheDocument()
    const beatriz = await screen.findByRole('radio', { name: /P-015\s*Beatriz Carvalho/ })
    expect(screen.getByText('Nenhuma sessão ainda')).toBeInTheDocument()
    expect(screen.getByText('3 sessões')).toBeInTheDocument()
    expect(screen.getByText('Mais 12 pacientes. Busque pelo nome ou código para encontrar outro.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Cadastrar paciente' })).toHaveAttribute('href', '/pacientes/novo')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Escolha o paciente para continuar.')
    await user.click(beatriz)
    await user.click(screen.getByRole('button', { name: 'Continuar' }))

    // Etapa 2: informações.
    expect(await screen.findByRole('heading', { name: 'Informações da sessão' })).toBeInTheDocument()
    expect(screen.getByText('P-015, Beatriz Carvalho', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Gravar a sessão' })).toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('Informe o título da sessão.')).toBeInTheDocument()
    expect(screen.getByText('Descreva o objetivo da sessão.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Título'), 'Rostos neutros e expressivos')
    await user.type(screen.getByLabelText('Objetivo'), 'Comparar o tempo de fixação.')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))

    // Etapa 3: estímulos.
    expect(await screen.findByRole('heading', { name: 'Sequência da sessão' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Adicione pelo menos um estímulo à sequência.')
    await user.click(await screen.findByRole('button', { name: 'Adicionar Rosto neutro 01' }))
    await user.click(screen.getByRole('button', { name: 'Adicionar Rosto alegre 02' }))
    await user.click(screen.getByRole('button', { name: 'Adicionar Ondas na praia' }))
    const library = screen.getByRole('list', { name: 'Estímulos da biblioteca' })
    expect(within(library).getAllByText('Adicionado')).toHaveLength(3)
    expect(within(library).getByText('Vídeo, 0:45')).toBeInTheDocument()
    expect(screen.getByText('3 estímulos, cerca de 55 s')).toBeInTheDocument()
    const time = screen.getByRole('textbox', { name: 'Tempo de tela de Rosto alegre 02, em segundos' })
    expect(time).toHaveValue('5')
    await user.clear(time)
    await user.type(time, 'x')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Confira os tempos destacados')
    await user.clear(time)
    expect(screen.getByText('3 estímulos, mais de 50 s')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remover Ondas na praia da sequência' }))
    await user.click(screen.getByRole('button', { name: 'Continuar' }))

    // Etapa 4: revisão.
    expect(await screen.findByText('Nascida em 21/07/1995')).toBeInTheDocument()
    expect(screen.getByText('P-015, Beatriz Carvalho')).toBeInTheDocument()
    expect(screen.getByText('Sim, a sessão será gravada')).toBeInTheDocument()
    expect(screen.getByText('2 imagens, mais de 5 s, com troca automática e manual')).toBeInTheDocument()
    expect(
      screen.getByText('A sessão fica com o status Configurada até ser executada. Você pode prepará-la agora ou depois, pela lista de sessões.'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Sessão salva com o status Configurada.')).toBeInTheDocument()
    expect(api.callsTo('POST', '/sessions')[0].body).toEqual({
      patient_id: 'p15',
      title: 'Rostos neutros e expressivos',
      objective: 'Comparar o tempo de fixação.',
      notes: '',
      record: true,
      stimuli: [
        { stimulus_id: 'st1', duration_seconds: 5 },
        { stimulus_id: 'st2', duration_seconds: null },
      ],
      duplicated_from_id: null,
    })
    // Vai para os detalhes da sessão criada.
    expect(await screen.findByRole('heading', { level: 1, name: 'Rostos neutros e expressivos' })).toBeInTheDocument()
  })

  it('com ?paciente abre nas informações; Editar na revisão volta à etapa', async () => {
    const user = userEvent.setup()
    wizardApi()
    renderWithProviders(<App />, { route: '/sessoes/nova?paciente=p15' })
    expect(await screen.findByRole('heading', { name: 'Informações da sessão' })).toBeInTheDocument()
    expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Informações')
    await user.type(screen.getByLabelText('Título'), 'Paisagens')
    // Trocar volta à etapa 1 com o paciente marcado e guarda o que foi digitado.
    await user.click(screen.getByRole('button', { name: 'Trocar' }))
    expect(await screen.findByRole('radio', { name: /Beatriz Carvalho/ })).toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByLabelText('Título')).toHaveValue('Paisagens')
  })

  it('Salvar e preparar leva à preparação; erro do servidor aparece na revisão', async () => {
    const user = userEvent.setup()
    let fail = true
    wizardApi({
      'POST /sessions': () => (fail ? reply(409, { detail: 'este paciente está inativo e não recebe novas sessões' }) : { ...DETAIL, id: 's99' }),
    })
    renderWithProviders(<App />, { route: '/sessoes/nova?paciente=p15' })
    await user.type(await screen.findByLabelText('Título'), 'Paisagens')
    await user.type(screen.getByLabelText('Objetivo'), 'Observar.')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    await user.click(await screen.findByRole('button', { name: 'Adicionar Rosto neutro 01' }))
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    await user.click(await screen.findByRole('button', { name: 'Salvar e preparar' }))
    expect(await screen.findByText('Este paciente está inativo e não recebe novas sessões.')).toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Salvar e preparar' }))
    // A preparação troca o título do "carregando" pelo da sessão carregada: o elemento achado por um
    // findBy pode sair da página antes do expect, então a busca se repete até o título ficar.
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: 'Preparar sessão' })).toBeInTheDocument())
  })

  it('duplicar traz as informações e a sequência, sem os arquivados, e pede o paciente', async () => {
    const user = userEvent.setup()
    const api = wizardApi()
    renderWithProviders(<App />, { route: '/sessoes/nova?duplicar=s3' })
    expect(
      await screen.findByText(
        'Copiando “Rostos neutros e expressivos” (paciente P-015). Escolha o paciente da nova sessão. Um estímulo arquivado ficou de fora da sequência.',
      ),
    ).toBeInTheDocument()
    await user.click(await screen.findByRole('radio', { name: /Mariana Alves/ }))
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByLabelText('Título')).toHaveValue('Rostos neutros e expressivos')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('2 estímulos, cerca de 50 s')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    await user.click(await screen.findByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(api.callsTo('POST', '/sessions')).toHaveLength(1))
    const body = api.callsTo('POST', '/sessions')[0].body as SessionInput
    expect(body.patient_id).toBe('p14')
    expect(body.duplicated_from_id).toBe('s3')
    expect(body.stimuli).toEqual([
      { stimulus_id: 'st1', duration_seconds: 5 },
      { stimulus_id: 'st3', duration_seconds: null },
    ])
  })

  it('sem "Criar e executar sessões" mostra "Sem acesso"', async () => {
    mockApi({ 'GET /me': { ...RESEARCHER, permissions: ['patients.view'] } })
    renderWithProviders(<App />, { route: '/sessoes/nova' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Sem acesso' })).toBeInTheDocument()
  })
})

// Executada, com os dados processados (W16 da Fase 5).
const EXECUTED: SessionDetail = {
  ...DETAIL,
  status: 'completed',
  end_reason: 'button_b',
  started_at: '2026-09-29T17:26:00Z',
  ended_at: '2026-09-29T17:27:50Z',
  date: '2026-09-29T17:26:00Z',
  duration_seconds: 110,
  data_status: 'ready',
  exposures: [
    { seq: 1, position: 1, stimulus_id: 'st1', name: 'Rosto neutro 01', kind: 'image', archived: false, thumbnail_url: '/api/v1/stimuli/st1/thumbnail', on_t: 20.2, screen_seconds: 5 },
    { seq: 2, position: 2, stimulus_id: 'st3', name: 'Ondas na praia', kind: 'video', archived: false, thumbnail_url: '/api/v1/stimuli/st3/thumbnail', on_t: 25.2, screen_seconds: 45 },
    { seq: 3, position: 1, stimulus_id: 'st1', name: 'Rosto neutro 01', kind: 'image', archived: false, thumbnail_url: '/api/v1/stimuli/st1/thumbnail', on_t: 72.4, screen_seconds: 65 },
  ],
  files: { tracking_bytes: 3_355_443, recording: { status: 'ready', size_bytes: 435_159_040 } },
}

const MARKERS = [
  { id: 1, t: 28.4, text: 'Paciente movimentou a cabeça', created_at: '2026-09-29T17:26:28Z', created_by_name: 'Ana Souza' },
  { id: 2, t: 65.1, text: 'Equipe de enfermagem entrou no quarto', created_at: '2026-09-29T17:27:05Z', created_by_name: 'Ana Souza' },
]

describe('W16 Detalhes da sessão e W18 Visibilidade', () => {
  it('mostra o cabeçalho, o resumo, as informações e a sequência', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/:id': DETAIL })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Rostos neutros e expressivos' })).toBeInTheDocument()
    expect(screen.getByText('Configurada')).toBeInTheDocument()
    expect(screen.getByText('Paciente P-015, Beatriz Carvalho')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Duplicar para outro paciente' })).toHaveAttribute('href', '/sessoes/nova?duplicar=s3')
    expect(screen.getByRole('link', { name: 'Preparar sessão' })).toHaveAttribute('href', '/sessoes/s3/preparar')
    expect(screen.queryByRole('button', { name: 'Alterar visibilidade' })).not.toBeInTheDocument()
    const summary = screen.getByRole('region', { name: 'Resumo' })
    expect(within(summary).getByText('Configurada em')).toBeInTheDocument()
    expect(within(summary).getByText('3 na sequência')).toBeInTheDocument()
    expect(within(summary).getByText('Privada')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma observação.')).toBeInTheDocument()
    expect(
      screen.getByText('Os dados coletados não podem ser alterados. Qualquer mudança nas informações fica registrada na auditoria.'),
    ).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Sequência da sessão' })
    expect(within(table).getByText('5,0 s')).toBeInTheDocument()
    expect(within(table).getByText('Vídeo inteiro (0:45)')).toBeInTheDocument()
    expect(within(table).getByText('Arquivado')).toBeInTheDocument()
    expect(within(table).getByText('Troca manual')).toBeInTheDocument()
  })

  it('edita as informações', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/:id': DETAIL,
      'PATCH /sessions/:id': ({ body }) => ({ ...DETAIL, ...(body as object) }),
    })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    await user.click(await screen.findByRole('button', { name: 'Editar informações' }))
    await user.type(screen.getByLabelText('Observações'), 'Paciente chegou cansado.')
    await user.click(screen.getByRole('checkbox', { name: 'Gravar a sessão' }))
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByText('Alterações salvas.')).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/sessions/s3')[0].body).toEqual({
      title: 'Rostos neutros e expressivos',
      objective: DETAIL.objective,
      notes: 'Paciente chegou cansado.',
      record: false,
    })
    expect(screen.getByText('Paciente chegou cansado.')).toBeInTheDocument()
  })

  it('executada: Analisar dados, sem Preparar e sem mudar a gravação', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/:id': EXECUTED, 'GET /sessions/:id/markers': MARKERS })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    expect(await screen.findByRole('link', { name: 'Analisar dados' })).toHaveAttribute('href', '/sessoes/s3/analise')
    expect(screen.queryByRole('link', { name: 'Preparar sessão' })).not.toBeInTheDocument()
    expect(screen.getByText('1 min 50 s')).toBeInTheDocument()
    expect(screen.getByText('Data e hora')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Editar informações' }))
    expect(screen.queryByRole('checkbox', { name: 'Gravar a sessão' })).not.toBeInTheDocument()
  })

  it('com os dados coletados: estímulos exibidos, marcações e arquivos', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/:id': EXECUTED, 'GET /sessions/:id/markers': MARKERS })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    // Rosto neutro 01 apareceu duas vezes (o pesquisador voltou a ele): 2 estímulos exibidos, 3 linhas.
    const summary = await screen.findByRole('region', { name: 'Resumo' })
    expect(within(summary).getByText('2 exibidos')).toBeInTheDocument()
    expect(screen.queryByRole('table', { name: 'Sequência da sessão' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Estímulos exibidos' })).toBeInTheDocument()
    expect(screen.getByText('Na ordem em que apareceram')).toBeInTheDocument()
    const rows = within(screen.getByRole('table', { name: /Estímulos exibidos/ })).getAllByRole('row').slice(1)
    expect(rows.map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))).toEqual([
      ['1', 'Rosto neutro 01', '00:20', '5,0 s'],
      ['2', 'Ondas na praia', '00:25', '45,0 s'],
      ['1', 'Rosto neutro 01', '01:12', '1 min 5 s'],
    ])
    const markers = await screen.findByRole('region', { name: 'Marcações' })
    expect(within(markers).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '00:28Paciente movimentou a cabeça',
      '01:05Equipe de enfermagem entrou no quarto',
    ])
    const files = screen.getByRole('region', { name: 'Arquivos' })
    expect(within(files).getByText('JSON, 3,2 MB')).toBeInTheDocument()
    expect(within(files).getByText('MP4, 415 MB')).toBeInTheDocument()
    expect(within(files).getByRole('link', { name: 'Baixar os dados de rastreamento (JSON)' }).getAttribute('href')).toMatch(
      /^\/api\/v1\/sessions\/s3\/downloads\/tracking\?tz=/,
    )
    expect(within(files).getByRole('link', { name: 'Baixar a gravação da sessão (MP4)' })).toHaveAttribute('download')
  })

  it('sem permissão de exportar, os arquivos aparecem sem Baixar; sem gravação, avisa', async () => {
    mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/:id': { ...EXECUTED, can_export: false, files: { tracking_bytes: 2048, recording: { status: 'none', size_bytes: null } } },
      'GET /sessions/:id/markers': [],
    })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    const files = await screen.findByRole('region', { name: 'Arquivos' })
    expect(within(files).getByText('Sessão sem gravação')).toBeInTheDocument()
    expect(within(files).queryByRole('link')).not.toBeInTheDocument()
    expect(await screen.findByText('Nenhuma marcação nesta sessão.')).toBeInTheDocument()
  })

  it.each([
    ['waiting', 'O óculos ainda está enviando os dados desta sessão.'],
    ['processing', 'Os dados chegaram e estão sendo processados. Esta página se atualiza sozinha.'],
    ['failed', 'Não foi possível processar os dados desta sessão: o JSON da sessão não pôde ser lido. O servidor tenta'],
  ] as const)('aguardando dados (%s): aviso e a sequência, sem Analisar dados', async (dataStatus, text) => {
    mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/:id': {
        ...EXECUTED,
        status: 'awaiting_data',
        data_status: dataStatus,
        data_error: dataStatus === 'failed' ? 'o JSON da sessão não pôde ser lido' : null,
        exposures: [],
        files: null,
      },
    })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    expect(await screen.findByText(text, { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Sequência da sessão' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Resumo' })).getByText('3 na sequência')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Analisar dados' })).not.toBeInTheDocument()
  })

  it('o admin muda a visibilidade para pesquisadores escolhidos', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': ADMIN,
      'GET /sessions/:id': { ...DETAIL, can_change_visibility: true, can_run: false },
      'GET /sessions/:id/share-candidates': [
        { id: 'u4', name: 'Bruno Castro', role: 'researcher', role_label: 'Pesquisador' },
        { id: 'u6', name: 'Daniela Rocha', role: 'researcher', role_label: 'Pesquisador' },
      ],
      'PUT /sessions/:id/visibility': ({ body }) => ({
        ...DETAIL,
        can_change_visibility: true,
        visibility: (body as { visibility: string }).visibility,
        shared_with: [{ id: 'u4', name: 'Bruno Castro', role: 'researcher', role_label: 'Pesquisador' }],
      }),
    })
    renderWithProviders(<App />, { route: '/sessoes/s3' })
    await user.click(await screen.findByRole('button', { name: 'Alterar visibilidade' }))
    const dialog = screen.getByRole('dialog', { name: 'Visibilidade da sessão' })
    expect(within(dialog).getByText('Rostos neutros e expressivos, paciente P-015')).toBeInTheDocument()
    expect(within(dialog).getByRole('radio', { name: /Só o responsável/ })).toBeChecked()
    expect(within(dialog).getByText('Apenas Ana Souza vê a sessão e os dados coletados.')).toBeInTheDocument()
    expect(within(dialog).getByText('A mudança fica registrada na auditoria.')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('radio', { name: /Pesquisadores escolhidos/ }))
    await user.click(within(dialog).getByRole('button', { name: 'Salvar' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Escolha pelo menos um pesquisador.')
    await user.type(within(dialog).getByRole('searchbox', { name: 'Buscar pesquisador' }), 'dani')
    expect(within(dialog).queryByRole('checkbox', { name: 'Bruno Castro' })).not.toBeInTheDocument()
    await user.clear(within(dialog).getByRole('searchbox', { name: 'Buscar pesquisador' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'Bruno Castro' }))
    await user.click(within(dialog).getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Visibilidade alterada.')).toBeInTheDocument()
    expect(api.callsTo('PUT', '/sessions/s3/visibility')[0].body).toEqual({ visibility: 'shared', user_ids: ['u4'] })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Resumo' })).getByText('Compartilhada')).toBeInTheDocument()
  })

  it('sessão que a pessoa não vê mostra a mensagem do servidor', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/:id': reply(404, { detail: 'sessão não encontrada' }) })
    renderWithProviders(<App />, { route: '/sessoes/outra' })
    expect(await screen.findByText('Sessão não encontrada.')).toBeInTheDocument()
  })
})
