import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../../App'
import type { LiveSnapshot } from '../../../api/live'
import type { SequenceItem, SessionDetail } from '../../../api/sessions'
import { mockApi, reply } from '../../../test/api'
import { RESEARCHER } from '../../../test/fixtures'
import { renderWithProviders } from '../../../test/render'
import { mockSockets } from '../../../test/socket'

afterEach(() => {
  vi.unstubAllGlobals()
})

function item(position: number, name: string, extra: Partial<SequenceItem> = {}): SequenceItem {
  return {
    position,
    stimulus_id: `st${position}`,
    name,
    kind: 'image',
    archived: false,
    duration_seconds: 5,
    media_duration_seconds: null,
    thumbnail_url: `/api/v1/stimuli/st${position}/thumbnail`,
    ...extra,
  }
}

const ITEMS = [
  item(1, 'Rosto neutro 01'),
  item(2, 'Rosto alegre 02', { duration_seconds: null }),
  item(3, 'Ondas na praia', { kind: 'video', duration_seconds: null, media_duration_seconds: 45 }),
]

function session(extra: Partial<SessionDetail> = {}): SessionDetail {
  return {
    id: 's1',
    type: 'media_sequence',
    status: 'configured',
    end_reason: null,
    title: 'Rostos neutros e expressivos',
    objective: 'Comparar o tempo de fixação.',
    notes: null,
    record: true,
    visibility: 'private',
    shared_with: [],
    patient: { id: 'p15', code: 'P-015', name: 'Beatriz Carvalho', birth_date: '1995-07-21', sex: 'female' },
    owner: { id: RESEARCHER.id, name: 'Ana Souza' },
    created_at: '2026-10-06T12:00:00Z',
    started_at: null,
    ended_at: null,
    date: '2026-10-06T12:00:00Z',
    duration_seconds: null,
    items: ITEMS,
    duplicated_from: null,
    data_status: 'none',
    data_error: null,
    exposures: [],
    files: null,
    can_edit: true,
    can_run: true,
    can_change_visibility: false,
    can_export: true,
    ...extra,
  }
}

const QUEST = {
  id: 'quest-01',
  name: 'Quest Pro 01',
  online: true,
  pairing_code: '4827',
  same_network: true,
  paired_by: 'network' as const,
  state: 'loading',
  tracking: { eye: 'active' as const, face: 'active' as const },
}

// Cada retrato montado é mais novo que o anterior, como no servidor.
let version = 0

function snapshot(extra: Partial<LiveSnapshot> = {}): LiveSnapshot {
  return {
    type: 'live',
    session_id: 's1',
    status: 'configured',
    started_at: null,
    device: null,
    nearby: [],
    load: { loaded: 0, total: 3, error: null },
    playback: { position: null, neutral: true, paused: false, shown: [] },
    version: ++version,
    ...extra,
  }
}

// Depois de iniciar, mais novo que qualquer retrato da preparação.
const RUNNING = snapshot({
  version: 1_000_000,
  status: 'running',
  started_at: new Date(Date.now() - 36_000).toISOString(),
  device: { ...QUEST, state: 'running' },
  load: { loaded: 3, total: 3, error: null },
  playback: { position: 2, neutral: false, paused: false, shown: [1, 2] },
})

describe('W14 Preparação da sessão', () => {
  it('acha o óculos na rede, acompanha o carregamento e inicia a sessão', async () => {
    const user = userEvent.setup()
    const sockets = mockSockets()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/s1': session(),
      'GET /sessions/s1/live': snapshot({ nearby: [{ id: 'quest-01', name: 'Quest Pro 01', pairing_code: '4827' }] }),
      'POST /sessions/s1/prepare': snapshot({ device: QUEST }),
      'POST /sessions/s1/start': RUNNING,
      'GET /sessions/s1/markers': [],
    })
    renderWithProviders(<App />, { route: '/sessoes/s1/preparar' })

    // O óculos da mesma rede é escolhido sozinho.
    expect(await screen.findByText('Encontrado na rede')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Preparar sessão' })).toBeInTheDocument()
    expect(screen.getByText('Rostos neutros e expressivos, paciente P-015.')).toBeInTheDocument()
    expect(api.callsTo('POST', '/sessions/s1/prepare')[0].body).toEqual({ device_id: 'quest-01' })
    expect(sockets.urls).toEqual(['ws://localhost:3000/api/v1/sessions/s1/live'])
    expect(screen.getByText('Conectado')).toBeInTheDocument()
    expect(screen.getByText('Detectado automaticamente.')).toBeInTheDocument()
    expect(screen.getByText('Será gravada')).toBeInTheDocument()
    expect(screen.getByText('0 de 3 carregados')).toBeInTheDocument()
    const start = screen.getByRole('button', { name: 'Iniciar sessão' })
    expect(start).toBeDisabled()
    expect(screen.getByText('Aguarde o óculos carregar os estímulos.')).toBeInTheDocument()

    await sockets.push(snapshot({ device: { ...QUEST, state: 'ready' }, load: { loaded: 3, total: 3, error: null } }))
    expect(screen.getByText('3 de 3 carregados')).toBeInTheDocument()
    expect(screen.getByText('Marque que o óculos está no paciente para iniciar.')).toBeInTheDocument()
    expect(start).toBeDisabled()

    await user.click(screen.getByLabelText('O óculos está no paciente'))
    expect(screen.getByText('Tudo pronto. Ao iniciar, a coleta começa e você escolhe o primeiro estímulo.')).toBeInTheDocument()
    await user.click(start)

    // Vai para o controle ao vivo (W15), em tela cheia.
    expect(await screen.findByRole('heading', { level: 1, name: 'Rostos neutros e expressivos' })).toBeInTheDocument()
    expect(api.callsTo('POST', '/sessions/s1/start')).toHaveLength(1)
    expect(screen.queryByRole('navigation', { name: 'Menu principal' })).not.toBeInTheDocument()
  })

  it('conecta pelo código de pareamento e mostra o erro do servidor', async () => {
    const user = userEvent.setup()
    mockSockets()
    let tries = 0
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/s1': session(),
      'GET /sessions/s1/live': snapshot(),
      'POST /sessions/s1/prepare': () =>
        ++tries === 1
          ? reply(404, { detail: 'nenhum óculos conectado com o código 1234' })
          : snapshot({ device: { ...QUEST, paired_by: 'code', same_network: false } }),
      'POST /sessions/s1/release': snapshot(),
    })
    renderWithProviders(<App />, { route: '/sessoes/s1/preparar' })

    expect(await screen.findByText('Nenhum óculos nesta rede ainda')).toBeInTheDocument()
    expect(screen.getByText('Procurando o óculos na rede deste computador.')).toBeInTheDocument()
    const code = screen.getByPlaceholderText('Ex.: 4827')
    await user.type(code, '12')
    await user.click(screen.getByRole('button', { name: 'Conectar' }))
    expect(screen.getByText('Digite os 4 números do código que aparece no app do óculos.')).toBeInTheDocument()

    await user.type(code, '34')
    await user.click(screen.getByRole('button', { name: 'Conectar' }))
    expect(await screen.findByText('Nenhum óculos conectado com o código 1234.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Conectar' }))
    expect(await screen.findByText('Pareado pelo código')).toBeInTheDocument()
    expect(screen.getByText('Conectado pelo código de pareamento.')).toBeInTheDocument()
    expect(api.callsTo('POST', '/sessions/s1/prepare').map((c) => c.body)).toEqual([
      { pairing_code: '1234' },
      { pairing_code: '1234' },
    ])

    // Cancelar desfaz o vínculo e volta aos detalhes da sessão.
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(await screen.findByRole('link', { name: 'Preparar sessão' })).toHaveAttribute('href', '/sessoes/s1/preparar')
    expect(api.callsTo('POST', '/sessions/s1/release')).toHaveLength(1)
  })

  it('sem o eye tracking ativo não dá para iniciar, e sem o facial avisa', async () => {
    const user = userEvent.setup()
    const sockets = mockSockets()
    const loaded = { loaded: 3, total: 3, error: null }
    mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/s1': session({ record: false }),
      'GET /sessions/s1/live': snapshot({
        device: { ...QUEST, state: 'ready', tracking: { eye: 'no_permission', face: 'unavailable' } },
        load: loaded,
      }),
    })
    renderWithProviders(<App />, { route: '/sessoes/s1/preparar' })

    expect(await screen.findByText('Sem permissão')).toBeInTheDocument()
    expect(screen.getByText('Indisponível')).toBeInTheDocument()
    expect(screen.getByText('Não será gravada')).toBeInTheDocument()
    await user.click(screen.getByLabelText('O óculos está no paciente'))
    expect(screen.getByText('Ative o eye tracking no óculos para iniciar a sessão.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Iniciar sessão' })).toBeDisabled()

    await sockets.push(snapshot({ device: { ...QUEST, state: 'ready', tracking: { eye: 'active', face: 'unavailable' } }, load: loaded }))
    expect(screen.getByText(/Tudo pronto, mas sem as expressões faciais/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Iniciar sessão' })).toBeEnabled()
  })

  it('mostra o estímulo que não carregou e o óculos que caiu', async () => {
    const sockets = mockSockets()
    mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/s1': session(),
      'GET /sessions/s1/live': snapshot({
        device: QUEST,
        load: { loaded: 1, total: 3, error: { stimulus_id: 'st2', message: 'sha256 não confere' } },
      }),
    })
    renderWithProviders(<App />, { route: '/sessoes/s1/preparar' })

    expect(await screen.findByText(/Não foi possível carregar “Rosto alegre 02” no óculos \(sha256 não confere\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tentar de novo' })).toBeInTheDocument()

    await sockets.push(snapshot({ device: { ...QUEST, online: false, state: 'offline' }, load: { loaded: 1, total: 3, error: null } }))
    expect(screen.getByText('Desconectado')).toBeInTheDocument()
    expect(screen.getByText('O óculos desconectou. Confira se o app está aberto e conectado à rede.')).toBeInTheDocument()
  })

  it('só o responsável prepara, e a sessão já iniciada abre o controle', async () => {
    mockSockets()
    mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/s1': session({ can_run: false }) })
    renderWithProviders(<App />, { route: '/sessoes/s1/preparar' })
    expect(await screen.findByText('Só o responsável pela sessão pode prepará-la e executá-la.')).toBeInTheDocument()
  })
})

describe('W15 Controle da sessão ao vivo', () => {
  function running(routes: Record<string, unknown> = {}) {
    return mockApi({
      'GET /me': RESEARCHER,
      'GET /sessions/s1': session({ status: 'running', started_at: RUNNING.started_at }),
      'GET /sessions/s1/live': RUNNING,
      'GET /sessions/s1/markers': [{ id: 1, t: 28.4, text: 'Paciente movimentou a cabeça', created_at: '', created_by_name: 'Ana Souza' }],
      'POST /sessions/s1/control': { command_id: 1 },
      ...routes,
    })
  }

  it('mostra o que o óculos exibe, a sequência e manda os comandos', async () => {
    const user = userEvent.setup()
    const sockets = mockSockets()
    const api = running({
      'POST /sessions/s1/markers': { id: 2, t: 40, text: 'Enfermagem entrou no quarto', created_at: '', created_by_name: 'Ana Souza' },
    })
    renderWithProviders(<App />, { route: '/sessoes/s1/controle' })

    expect(await screen.findByRole('heading', { level: 1, name: 'Rostos neutros e expressivos' })).toBeInTheDocument()
    expect(screen.getByText('Paciente P-015, Beatriz Carvalho')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Menu principal' })).not.toBeInTheDocument()
    expect(await screen.findByText('Estímulo 2 de 3')).toBeInTheDocument()
    const pills = screen.getByRole('list', { name: 'Estado do óculos' })
    expect(within(pills).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Gravando',
      'Óculos conectado',
      'Eye tracking',
      'Emotion tracking',
    ])
    expect(screen.getByRole('timer')).toHaveTextContent(/^00:3\d$/)
    expect(screen.getByRole('img', { name: 'Rosto alegre 02' })).toHaveAttribute('src', '/api/v1/stimuli/st2/file')
    expect(screen.getByText('Imagem, troca manual')).toBeInTheDocument()

    const sequence = screen.getByRole('region', { name: 'Sequência' })
    const rows = within(sequence).getAllByRole('button')
    expect(rows.map((r) => r.textContent)).toEqual([
      '1Rosto neutro 01Exibido',
      '2Rosto alegre 02Em exibição',
      '3Ondas na praiaPendente',
    ])
    expect(screen.getByRole('button', { name: 'Pausar vídeo' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: /Próximo estímulo/ }))
    await user.click(rows[2])
    await user.click(screen.getByRole('button', { name: 'Tela neutra' }))
    await waitFor(() => expect(api.callsTo('POST', '/sessions/s1/control')).toHaveLength(3))
    expect(api.callsTo('POST', '/sessions/s1/control').map((c) => c.body)).toEqual([
      { action: 'next' },
      { action: 'goto', position: 3 },
      { action: 'neutral' },
    ])

    // O óculos avançou para o vídeo e o pausou.
    await sockets.push({ ...RUNNING, playback: { position: 3, neutral: false, paused: true, shown: [1, 2, 3] } })
    expect(screen.getByText('Estímulo 3 de 3')).toBeInTheDocument()
    expect(screen.getByText('Vídeo, avança ao terminar (0:45)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retomar vídeo' }))
    expect(api.callsTo('POST', '/sessions/s1/control').at(-1)?.body).toEqual({ action: 'resume' })

    // Depois do último, a tela neutra até o B.
    await sockets.push({ ...RUNNING, playback: { position: 3, neutral: true, paused: false, shown: [1, 2, 3] } })
    expect(screen.getByText('Fim da sequência. Aperte o B no óculos para encerrar.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Próximo estímulo/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Tela neutra' })).toBeDisabled()

    expect(await screen.findByText('Paciente movimentou a cabeça')).toBeInTheDocument()
    expect(screen.getByText('00:28')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Marcar' }))
    expect(screen.getByText('Escreva o que aconteceu.')).toBeInTheDocument()
    await user.type(screen.getByPlaceholderText('Ex.: enfermagem entrou no quarto'), 'Enfermagem entrou no quarto')
    await user.click(screen.getByRole('button', { name: 'Marcar' }))
    expect(await screen.findByText('Enfermagem entrou no quarto')).toBeInTheDocument()
    expect(screen.getByText('00:40')).toBeInTheDocument()
    expect(api.callsTo('POST', '/sessions/s1/markers')[0].body).toEqual({ text: 'Enfermagem entrou no quarto' })
  })

  it('com o óculos desconectado os comandos ficam desligados', async () => {
    const sockets = mockSockets()
    running()
    renderWithProviders(<App />, { route: '/sessoes/s1/controle' })
    expect(await screen.findByText('Estímulo 2 de 3')).toBeInTheDocument()
    await sockets.push({ ...RUNNING, device: { ...QUEST, online: false, state: 'offline', tracking: {} } })
    expect(screen.getByText('Óculos desconectado')).toBeInTheDocument()
    expect(screen.getByText(/A coleta continua nele/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Próximo estímulo/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
  })

  it('o B no óculos leva aos detalhes da sessão', async () => {
    const sockets = mockSockets()
    running()
    renderWithProviders(<App />, { route: '/sessoes/s1/controle' })
    expect(await screen.findByText('Estímulo 2 de 3')).toBeInTheDocument()
    await sockets.push({ ...RUNNING, status: 'awaiting_data' })
    expect(await screen.findByText('Sessão encerrada no óculos. Os dados estão sendo enviados.')).toBeInTheDocument()
    expect(await screen.findByRole('navigation', { name: 'Menu principal' })).toBeInTheDocument()
  })

  it('interromper pede confirmação', async () => {
    const user = userEvent.setup()
    mockSockets()
    const api = running({ 'POST /sessions/s1/interrupt': { ...RUNNING, status: 'awaiting_data' } })
    renderWithProviders(<App />, { route: '/sessoes/s1/controle' })
    await user.click(await screen.findByRole('button', { name: 'Interromper sessão' }))
    const dialog = screen.getByRole('dialog', { name: 'Interromper sessão?' })
    await user.click(within(dialog).getByRole('button', { name: 'Continuar sessão' }))
    expect(api.callsTo('POST', '/sessions/s1/interrupt')).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Interromper sessão' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Interromper sessão' }))
    expect(await screen.findByText('Sessão interrompida. O óculos está enviando o que foi coletado.')).toBeInTheDocument()
    expect(api.callsTo('POST', '/sessions/s1/interrupt')).toHaveLength(1)
  })

  it('a sessão ainda não iniciada volta para a preparação', async () => {
    mockSockets()
    mockApi({ 'GET /me': RESEARCHER, 'GET /sessions/s1': session(), 'GET /sessions/s1/live': snapshot() })
    renderWithProviders(<App />, { route: '/sessoes/s1/controle' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Preparar sessão' })).toBeInTheDocument()
  })
})
