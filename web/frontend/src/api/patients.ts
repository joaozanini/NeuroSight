// Pacientes (W06–W08). Cadastro e edição vão em multipart: os campos em JSON no `data` e o PDF do
// TCLE em `consent_file`, para o termo entrar junto com o cadastro.
import { API_BASE, api, apiRequest } from './client'
import type { PatientStatus, SessionStatus } from '../lib/status'

export type Sex = 'female' | 'male' | 'undisclosed'
export type VisionCorrection = 'none' | 'glasses' | 'contacts'

export interface PatientRow {
  id: string
  code: string
  name: string
  // Data sem hora ("1998-03-12").
  birth_date: string
  status: PatientStatus
  sessions_count: number
  last_session_at: string | null
}

export interface PatientPage {
  items: PatientRow[]
  total: number
  page: number
  page_size: number
  // Cadastro inteiro, sem a busca ("15 pacientes cadastrados").
  counts: { active: number; inactive: number }
}

export interface PatientSession {
  id: string
  title: string
  date: string
  owner_name: string
  stimuli_count: number
  status: SessionStatus
}

export interface PatientDetail {
  id: string
  code: string
  name: string
  birth_date: string
  sex: Sex
  vision_correction: VisionCorrection
  consent_signed: boolean
  consent_date: string | null
  consent_file: { name: string; size: number } | null
  notes: string | null
  status: PatientStatus
  created_at: string
  created_by_name: string | null
  sessions_count: number
  sessions: PatientSession[]
}

export interface PatientInput {
  code: string
  name: string
  birth_date: string
  sex: Sex
  vision_correction: VisionCorrection
  consent_signed: boolean
  consent_date: string | null
  notes: string
}

export interface PatientFilters {
  q?: string
  include_inactive?: boolean
  page?: number
}

export const PATIENTS_PAGE_SIZE = 8

export const SEX_LABELS: Record<Sex, string> = {
  female: 'Feminino',
  male: 'Masculino',
  undisclosed: 'Prefiro não informar',
}

export const VISION_LABELS: Record<VisionCorrection, string> = {
  none: 'Não',
  glasses: 'Óculos de grau',
  contacts: 'Lentes de contato',
}

export const patientsKeys = {
  all: ['patients'] as const,
  lists: ['patients', 'list'] as const,
  list: (filters: PatientFilters) => ['patients', 'list', filters] as const,
  detail: (id: string) => ['patients', 'detail', id] as const,
  nextCode: ['patients', 'next-code'] as const,
}

function patientForm(input: PatientInput, consentFile?: File | null): FormData {
  const form = new FormData()
  form.append('data', JSON.stringify(input))
  if (consentFile) form.append('consent_file', consentFile, consentFile.name)
  return form
}

const path = (id: string) => `/patients/${encodeURIComponent(id)}`

export const patientsApi = {
  list: (filters: PatientFilters, signal?: AbortSignal) =>
    api.get<PatientPage>('/patients', { signal, query: { ...filters, page_size: PATIENTS_PAGE_SIZE } }),
  nextCode: (signal?: AbortSignal) => api.get<{ code: string }>('/patients/next-code', { signal }),
  get: (id: string, signal?: AbortSignal) => api.get<PatientDetail>(path(id), { signal }),
  create: (input: PatientInput, consentFile?: File | null) =>
    apiRequest<PatientDetail>('/patients', { method: 'POST', body: patientForm(input, consentFile) }),
  update: (id: string, input: PatientInput, consentFile?: File | null) =>
    apiRequest<PatientDetail>(path(id), { method: 'PUT', body: patientForm(input, consentFile) }),
  setStatus: (id: string, status: PatientStatus) => api.put<PatientDetail>(`${path(id)}/status`, { status }),
  // O PDF abre numa aba nova; o cookie de login vai junto (mesma origem).
  consentUrl: (id: string) => `${API_BASE}${path(id)}/consent`,
}
