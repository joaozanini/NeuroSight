// Início (W04) e o selo de sessões do menu. O servidor monta os números da visão de cada um: o
// laboratório para o admin, as próprias sessões para o pesquisador.
import { api } from './client'
import type { DataStatus } from './sessions'
import type { SessionStatus } from '../lib/status'

// Número do mês, o do mesmo trecho do mês anterior e as últimas 8 semanas.
export interface Trend {
  value: number
  previous: number
  series: number[]
}

export interface AwaitingKpi {
  value: number
  series: number[]
  latest_id: string | null
  latest_title: string | null
  latest_data_status: DataStatus | null
}

export interface UsersKpi {
  active: number
  invited: number
  // Ativos cadastrados neste mês.
  added: number
  series: number[]
}

export interface AuditKpi {
  today: number
  // Ontem até a mesma hora.
  yesterday: number
  last_at: string | null
  series: number[]
}

export interface AttentionItem {
  id: string
  title: string
  status: SessionStatus
  patient_code: string
  owner_name: string
  started_at: string | null
  ended_at: string | null
  data_status: DataStatus
  can_run: boolean
}

export interface RecentSession {
  id: string
  title: string
  patient_code: string
  owner_name: string
  date: string
  status: SessionStatus
  stimuli_count: number
}

export interface AuditLine {
  id: number
  created_at: string
  user_name: string | null
  // A ação como frase ("Iniciou a sessão Rostos neutros e expressivos").
  text: string
}

export interface Dashboard {
  view: 'admin' | 'researcher'
  badge: number
  // "outubro", "setembro".
  month: string
  previous_month: string
  sessions: Trend
  awaiting: AwaitingKpi
  patients: Trend | null
  collection_seconds: Trend | null
  users: UsersKpi | null
  audit: AuditKpi | null
  attention: AttentionItem[]
  recent: RecentSession[]
  audit_entries: AuditLine[] | null
}

export const dashboardKeys = {
  dashboard: ['dashboard'] as const,
  // Dentro de ['sessions']: o que invalida as sessões atualiza o selo junto.
  badge: ['sessions', 'badge'] as const,
}

export const dashboardApi = {
  // O fuso do navegador decide o que é "hoje" e "no mês".
  get: (signal?: AbortSignal) =>
    api.get<Dashboard>('/dashboard', { signal, query: { tz: Intl.DateTimeFormat().resolvedOptions().timeZone } }),
  badge: (signal?: AbortSignal) => api.get<{ sessions: number }>('/dashboard/badge', { signal }),
}
