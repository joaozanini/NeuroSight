import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import App from '../../App'
import type { AttentionItem, Dashboard } from '../../api/dashboard'
import { mockApi, reply } from '../../test/api'
import { ADMIN, RESEARCHER } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { attentionSubtitle, attentionWhen, countDelta, formatCollection, percentDelta } from './homeText'

function at(hours: number, minutes: number, daysAgo = 0): string {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  d.setHours(hours, minutes, 0, 0)
  return d.toISOString()
}

const RUNNING: AttentionItem = {
  id: 's1',
  title: 'Rostos neutros e expressivos',
  status: 'running',
  patient_code: 'P-014',
  owner_name: 'Ana Souza',
  started_at: at(14, 10),
  ended_at: null,
  data_status: 'none',
  can_run: true,
}

const WAITING: AttentionItem = {
  id: 's2',
  title: 'Paisagens naturais',
  status: 'awaiting_data',
  patient_code: 'P-009',
  owner_name: 'Ana Souza',
  started_at: at(11, 30),
  ended_at: at(11, 42),
  data_status: 'waiting',
  can_run: true,
}

const RECENT = [
  { id: 's2', title: 'Paisagens naturais', patient_code: 'P-009', owner_name: 'Ana Souza', date: '2026-09-29T14:00:00Z', status: 'awaiting_data', stimuli_count: 8 },
  { id: 's3', title: 'Rostos neutros e expressivos', patient_code: 'P-015', owner_name: 'Ana Souza', date: '2026-09-28T14:00:00Z', status: 'configured', stimuli_count: 12 },
  { id: 's4', title: 'Publicidade em vídeo', patient_code: 'P-011', owner_name: 'Bruno Castro', date: '2026-09-25T14:00:00Z', status: 'interrupted', stimuli_count: 2 },
] as Dashboard['recent']

const ADMIN_DASHBOARD: Dashboard = {
  view: 'admin',
  badge: 2,
  month: 'setembro',
  previous_month: 'agosto',
  sessions: { value: 38, previous: 32, series: [4, 6, 5, 7, 6, 8, 7, 9] },
  awaiting: { value: 1, series: [0, 0, 1, 0, 0, 2, 0, 1], latest_id: 's2', latest_title: 'Paisagens naturais', latest_data_status: 'waiting' },
  patients: null,
  collection_seconds: null,
  users: { active: 12, invited: 1, added: 1, series: [6, 7, 8, 9, 10, 11, 11, 12] },
  audit: { today: 7, yesterday: 5, last_at: at(14, 31), series: [3, 4, 3, 5, 4, 6, 5, 7] },
  attention: [{ ...RUNNING, can_run: false }, { ...WAITING, can_run: false }],
  recent: RECENT,
  audit_entries: [
    { id: 5, created_at: at(14, 10), user_name: 'Ana Souza', text: 'Iniciou a sessão Rostos neutros e expressivos' },
    { id: 4, created_at: at(11, 42), user_name: 'Ana Souza', text: 'Encerrou a sessão Paisagens naturais' },
    { id: 3, created_at: at(9, 5), user_name: 'Carlos Lima', text: 'Criou o usuário Igor Mendes' },
    { id: 2, created_at: at(17, 30, 1), user_name: 'Bruno Castro', text: 'Enviou 6 estímulos' },
    { id: 1, created_at: at(16, 2, 1), user_name: null, text: 'Entrou no sistema' },
  ],
}

const RESEARCHER_DASHBOARD: Dashboard = {
  view: 'researcher',
  badge: 2,
  month: 'setembro',
  previous_month: 'agosto',
  sessions: { value: 14, previous: 12, series: [2, 3, 2, 4, 3, 4, 3, 5] },
  awaiting: ADMIN_DASHBOARD.awaiting,
  patients: { value: 9, previous: 7, series: [1, 2, 2, 3, 2, 3, 3, 4] },
  collection_seconds: { value: 1560, previous: 1393, series: [2, 3, 2, 4, 3, 4, 3, 5] },
  users: null,
  audit: null,
  attention: [RUNNING, WAITING],
  recent: RECENT.slice(0, 2),
  audit_entries: null,
}

afterEach(() => {
  vi.unstubAllGlobals()
})

function cardOf(label: string) {
  return screen.getByRole('region', { name: label })
}

describe('W04 Início', () => {
  it('admin: KPIs do laboratório, atenção, auditoria e sessões recentes', async () => {
    const api = mockApi({ 'GET /me': ADMIN, 'GET /dashboard': ADMIN_DASHBOARD, 'GET /dashboard/badge': { sessions: 2 } })
    renderWithProviders(<App />, { route: '/' })

    expect(await screen.findByRole('heading', { level: 1, name: 'Olá, Carlos' })).toBeInTheDocument()
    expect(await screen.findByText('Duas sessões estão em andamento ou aguardando dados.')).toBeInTheDocument()
    expect(api.callsTo('GET', '/dashboard')[0].query.get('tz')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Novo paciente' })).toHaveAttribute('href', '/pacientes/novo')
    expect(screen.getByRole('link', { name: 'Enviar estímulos' })).toHaveAttribute('href', '/estimulos?enviar=1')
    expect(screen.getByRole('link', { name: 'Nova sessão' })).toHaveAttribute('href', '/sessoes/nova')

    expect(cardOf('Usuários ativos')).toHaveTextContent('121 convite pendente+1')
    expect(cardOf('Sessões em setembro')).toHaveTextContent('38desde agosto+19%')
    expect(cardOf('Aguardando dados')).toHaveTextContent('1Paisagens naturaisem envio')
    expect(cardOf('Registros na auditoria hoje')).toHaveTextContent('7o último às 14:31+2')

    const attention = screen.getByRole('region', { name: 'Precisam de atenção' })
    const rows = within(attention).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Em andamentoRostos neutros e expressivosPaciente P-014, responsável: Ana SouzaIniciada às 14:10')
    expect(within(rows[0]).getByRole('link', { name: /Ver sessão/ })).toHaveAttribute('href', '/sessoes/s1')
    expect(rows[1]).toHaveTextContent('Aguardando dadosPaisagens naturaisPaciente P-009, responsável: Ana SouzaEncerrada às 11:42, recebendo dados')

    const audit = screen.getByRole('region', { name: 'Últimas ações da auditoria' })
    expect(within(audit).getByRole('link', { name: 'Ver auditoria' })).toHaveAttribute('href', '/admin/auditoria')
    const auditRows = within(audit).getAllByRole('row').slice(1)
    expect(auditRows[0]).toHaveTextContent('Hoje, 14:10Ana SouzaIniciou a sessão Rostos neutros e expressivos')
    expect(auditRows[3]).toHaveTextContent('Ontem, 17:30Bruno CastroEnviou 6 estímulos')
    expect(auditRows[4]).toHaveTextContent('Sistema')

    const recent = screen.getByRole('region', { name: 'Sessões recentes' })
    expect(within(recent).getByRole('link', { name: 'Ver todas as sessões' })).toHaveAttribute('href', '/sessoes')
    expect(within(recent).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Sessão', 'Responsável', 'Paciente', 'Data', 'Status'])
    expect(within(recent).getAllByRole('row')[3]).toHaveTextContent('Publicidade em vídeoBruno CastroP-01125/09/2026Interrompida')

    const nav = screen.getByRole('navigation', { name: 'Menu principal' })
    expect(within(nav).getByRole('link', { name: /Sessões/ })).toHaveTextContent('2')
  })

  it('pesquisador: as próprias sessões, Abrir controle e a contagem de estímulos', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /dashboard': RESEARCHER_DASHBOARD })
    renderWithProviders(<App />, { route: '/' })

    expect(await screen.findByText('Duas sessões precisam da sua atenção.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Olá, Ana' })).toBeInTheDocument()
    expect(cardOf('Sessões no mês')).toHaveTextContent('14desde agosto+17%')
    expect(cardOf('Pacientes acompanhados')).toHaveTextContent('9neste mês+2')
    expect(cardOf('Tempo de coleta no mês')).toHaveTextContent('26 mindesde agosto+12%')
    expect(screen.queryByRole('region', { name: 'Usuários ativos' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Últimas ações da auditoria' })).not.toBeInTheDocument()

    const attention = screen.getByRole('region', { name: 'Precisam de atenção' })
    const rows = within(attention).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Rostos neutros e expressivosPaciente P-014Iniciada às 14:10')
    expect(rows[0]).not.toHaveTextContent('responsável')
    expect(within(rows[0]).getByRole('link', { name: 'Abrir controle' })).toHaveAttribute('href', '/sessoes/s1/controle')
    expect(within(rows[1]).getByRole('link', { name: /Ver sessão/ })).toHaveAttribute('href', '/sessoes/s2')

    const recent = screen.getByRole('region', { name: 'Suas sessões recentes' })
    expect(within(recent).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Sessão', 'Paciente', 'Data', 'Estímulos', 'Status'])
    expect(within(recent).getAllByRole('row')[2]).toHaveTextContent('Rostos neutros e expressivosP-01528/09/202612Configurada')
  })

  it('sem sessões pendentes e sem permissões de criar, só o resumo', async () => {
    mockApi({
      'GET /me': { ...RESEARCHER, permissions: ['patients.view'] },
      'GET /dashboard': {
        ...RESEARCHER_DASHBOARD,
        badge: 0,
        attention: [],
        recent: [],
        awaiting: { value: 0, series: [0, 0, 0, 0, 0, 0, 0, 0], latest_id: null, latest_title: null, latest_data_status: null },
        sessions: { value: 0, previous: 0, series: [0, 0, 0, 0, 0, 0, 0, 0] },
      },
    })
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByText('Nenhuma sessão precisa da sua atenção.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma sessão em andamento ou aguardando dados.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma sessão ainda.')).toBeInTheDocument()
    expect(cardOf('Aguardando dados')).toHaveTextContent('0nenhuma no momento')
    expect(cardOf('Sessões no mês')).toHaveTextContent('0neste mês')
    expect(screen.queryByRole('link', { name: 'Nova sessão' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Novo paciente' })).not.toBeInTheDocument()
  })

  it('erro ao carregar aparece no lugar dos números', async () => {
    mockApi({ 'GET /me': ADMIN, 'GET /dashboard': reply(500, { detail: 'falha' }) })
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('alert')).toHaveTextContent('O servidor encontrou um erro.')
    expect(screen.getByRole('heading', { level: 1, name: 'Olá, Carlos' })).toBeInTheDocument()
  })
})

describe('textos do Início', () => {
  it('subtítulo por extenso', () => {
    expect(attentionSubtitle(0, 'researcher')).toBe('Nenhuma sessão precisa da sua atenção.')
    expect(attentionSubtitle(1, 'admin')).toBe('Uma sessão está em andamento ou aguardando dados.')
    expect(attentionSubtitle(12, 'admin')).toBe('12 sessões estão em andamento ou aguardando dados.')
    expect(attentionSubtitle(1, 'researcher')).toBe('Uma sessão precisa da sua atenção.')
    expect(attentionSubtitle(3, 'researcher')).toBe('Três sessões precisam da sua atenção.')
  })

  it('variações', () => {
    expect(percentDelta({ value: 38, previous: 32, series: [] })).toEqual({ text: '+19%', direction: 'up' })
    expect(percentDelta({ value: 3, previous: 4, series: [] })).toEqual({ text: '−25%', direction: 'down' })
    expect(percentDelta({ value: 4, previous: 4, series: [] })).toEqual({ text: '0%' })
    expect(percentDelta({ value: 4, previous: 0, series: [] })).toBeUndefined()
    expect(countDelta(9, 7)).toEqual({ text: '+2', direction: 'up' })
    expect(countDelta(5, 6)).toEqual({ text: '−1', direction: 'down' })
    expect(countDelta(5, 5)).toBeUndefined()
  })

  it('tempo de coleta', () => {
    expect(formatCollection(1560)).toBe('26 min')
    expect(formatCollection(0)).toBe('0 min')
    expect(formatCollection(25)).toBe('25 s')
    expect(formatCollection(3900)).toBe('1 h 05 min')
    expect(formatCollection(7200)).toBe('2 h')
  })

  it('quando a sessão começou ou terminou', () => {
    const now = new Date(2026, 9, 6, 15, 0)
    const yesterday = new Date(2026, 9, 5, 17, 30).toISOString()
    const older = new Date(2026, 8, 27, 9, 0).toISOString()
    expect(attentionWhen({ ...RUNNING, started_at: yesterday }, now)).toBe('Iniciada ontem às 17:30')
    expect(attentionWhen({ ...WAITING, ended_at: older, data_status: 'processing' }, now)).toBe(
      'Encerrada em 27/09/2026 às 09:00, processando os dados',
    )
    expect(attentionWhen({ ...WAITING, ended_at: older, data_status: 'failed' }, now)).toBe(
      'Encerrada em 27/09/2026 às 09:00, falha no processamento',
    )
  })
})
