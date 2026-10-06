// Sessões (W12, W13, W16, W18): lista com filtros, criação pelo assistente, detalhe, edição das
// informações e visibilidade. Cada um vê só as sessões que a regra de visibilidade deixa.
import { api } from './client'
import type { Role } from './auth'
import type { Sex } from './patients'
import type { StimulusKind } from './stimuli'
import type { SessionStatus } from '../lib/status'

export type Visibility = 'private' | 'shared' | 'all'

export interface Person {
  id: string
  name: string
}

export interface ShareCandidate extends Person {
  role: Role
  role_label: string
}

export interface SessionRow {
  id: string
  title: string
  patient_id: string
  patient_code: string
  owner_id: string
  owner_name: string
  // Início, depois de executada; antes disso, quando foi configurada.
  date: string
  status: SessionStatus
  visibility: Visibility
}

export interface SessionPage {
  items: SessionRow[]
  total: number
  page: number
  page_size: number
}

export interface SequenceItem {
  position: number
  stimulus_id: string
  name: string
  kind: StimulusKind
  archived: boolean
  // Tempo de tela das imagens; null = troca manual (e sempre null nos vídeos).
  duration_seconds: number | null
  media_duration_seconds: number | null
  thumbnail_url: string
}

export interface SessionDetail {
  id: string
  type: string
  status: SessionStatus
  end_reason: string | null
  title: string
  objective: string
  notes: string | null
  record: boolean
  visibility: Visibility
  shared_with: ShareCandidate[]
  // Nome, nascimento e sexo só para quem pode ver pacientes.
  patient: { id: string; code: string; name: string | null; birth_date: string | null; sex: Sex | null }
  owner: Person
  created_at: string
  started_at: string | null
  ended_at: string | null
  date: string
  duration_seconds: number | null
  items: SequenceItem[]
  duplicated_from: { id: string; title: string } | null
  can_edit: boolean
  can_run: boolean
  can_change_visibility: boolean
}

export interface SessionInput {
  patient_id: string
  title: string
  objective: string
  notes: string
  record: boolean
  stimuli: { stimulus_id: string; duration_seconds: number | null }[]
  duplicated_from_id?: string | null
}

export interface SessionInfo {
  title?: string
  objective?: string
  notes?: string
  record?: boolean
}

export interface SessionFilters {
  q?: string
  status?: SessionStatus | ''
  owner_id?: string
  // Início do período (ISO), calculado no fuso do navegador.
  since?: string
  page?: number
}

export const SESSIONS_PAGE_SIZE = 8

export const VISIBILITY_LABELS: Record<Visibility, string> = {
  private: 'Privada',
  shared: 'Compartilhada',
  all: 'Aberta a todos',
}

export const sessionsKeys = {
  all: ['sessions'] as const,
  lists: ['sessions', 'list'] as const,
  list: (filters: SessionFilters) => ['sessions', 'list', filters] as const,
  owners: ['sessions', 'owners'] as const,
  detail: (id: string) => ['sessions', 'detail', id] as const,
  candidates: (id: string) => ['sessions', 'candidates', id] as const,
}

const path = (id: string) => `/sessions/${encodeURIComponent(id)}`

export const sessionsApi = {
  list: (filters: SessionFilters, signal?: AbortSignal) =>
    api.get<SessionPage>('/sessions', { signal, query: { ...filters, page_size: SESSIONS_PAGE_SIZE } }),
  owners: (signal?: AbortSignal) => api.get<Person[]>('/sessions/owners', { signal }),
  get: (id: string, signal?: AbortSignal) => api.get<SessionDetail>(path(id), { signal }),
  create: (input: SessionInput) => api.post<SessionDetail>('/sessions', input),
  update: (id: string, info: SessionInfo) => api.patch<SessionDetail>(path(id), info),
  shareCandidates: (id: string, signal?: AbortSignal) => api.get<ShareCandidate[]>(`${path(id)}/share-candidates`, { signal }),
  setVisibility: (id: string, visibility: Visibility, userIds: string[]) =>
    api.put<SessionDetail>(`${path(id)}/visibility`, { visibility, user_ids: userIds }),
}

// Preparação (W14) e controle ao vivo (W15).
export const prepareSessionPath = (id: string) => `/sessoes/${id}/preparar`
export const controlSessionPath = (id: string) => `/sessoes/${id}/controle`
