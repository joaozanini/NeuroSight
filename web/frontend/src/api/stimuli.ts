// Biblioteca de estímulos (W09–W11). Cada arquivo sobe num request próprio (progresso por arquivo)
// e fica como rascunho até "Salvar na biblioteca".
import { api } from './client'
import { uploadFile } from './upload'
import type { UploadProgress } from './upload'

export type StimulusKind = 'image' | 'video'
export type StimulusFormat = 'jpg' | 'png' | 'mp4'
export type StimulusStatus = 'active' | 'archived'
export type DeviceStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface StimulusCard {
  id: string
  name: string
  kind: StimulusKind
  status: StimulusStatus
  tags: string[]
  duration_seconds: number | null
  thumbnail_url: string
}

export interface StimulusPage {
  items: StimulusCard[]
  total: number
  page: number
  page_size: number
  // Biblioteca inteira, sem filtros nem arquivados.
  counts: { total: number; images: number; videos: number }
}

export interface StimulusDraft {
  id: string
  original_filename: string
  suggested_name: string
  kind: StimulusKind
  format: StimulusFormat
  size_bytes: number
  width: number
  height: number
  duration_seconds: number | null
  thumbnail_url: string
}

export interface StimulusSession {
  id: string
  title: string
  patient_code: string
  date: string
}

export interface StimulusDetail {
  id: string
  name: string
  description: string | null
  kind: StimulusKind
  format: StimulusFormat
  status: StimulusStatus
  original_filename: string
  size_bytes: number
  width: number
  height: number
  duration_seconds: number | null
  has_audio: boolean | null
  tags: string[]
  created_at: string
  created_by_name: string | null
  thumbnail_url: string
  file_url: string
  device_status: DeviceStatus
  device_error: string | null
  sessions_count: number
  sessions: StimulusSession[]
  can_delete: boolean
}

export interface StimulusInfo {
  name: string
  description: string | null
  tags: string[]
}

export interface StimulusFilters {
  q?: string
  kind?: StimulusKind | ''
  tag?: string
  include_archived?: boolean
}

export const STIMULI_PAGE_SIZE = 48

// Formatos aceitos no envio (W10); o servidor confere o conteúdo de novo.
export const STIMULUS_ACCEPT = '.jpg,.jpeg,.png,.mp4'

export const KIND_LABELS: Record<StimulusKind, string> = { image: 'Imagem', video: 'Vídeo' }

export const stimuliKeys = {
  all: ['stimuli'] as const,
  lists: ['stimuli', 'list'] as const,
  list: (filters: StimulusFilters) => ['stimuli', 'list', filters] as const,
  allTags: ['stimuli', 'tags'] as const,
  tags: (includeArchived: boolean) => ['stimuli', 'tags', includeArchived] as const,
  detail: (id: string) => ['stimuli', 'detail', id] as const,
}

const path = (id: string) => `/stimuli/${encodeURIComponent(id)}`

export const stimuliApi = {
  list: (filters: StimulusFilters, page: number, signal?: AbortSignal) =>
    api.get<StimulusPage>('/stimuli', { signal, query: { ...filters, page, page_size: STIMULI_PAGE_SIZE } }),
  tags: (includeArchived: boolean, signal?: AbortSignal) =>
    api.get<string[]>('/stimuli/tags', { signal, query: { include_archived: includeArchived || undefined } }),
  get: (id: string, signal?: AbortSignal) => api.get<StimulusDetail>(path(id), { signal }),
  upload: (file: File, options: { onProgress?: (progress: UploadProgress) => void; signal?: AbortSignal } = {}) =>
    uploadFile<StimulusDraft>('/stimuli/uploads', { file, ...options }),
  discard: (id: string) => api.delete<void>(`/stimuli/uploads/${encodeURIComponent(id)}`),
  save: (items: (StimulusInfo & { id: string })[]) => api.post<StimulusCard[]>('/stimuli', { items }),
  update: (id: string, info: Partial<StimulusInfo>) => api.patch<StimulusDetail>(path(id), info),
  setStatus: (id: string, status: StimulusStatus) => api.put<StimulusDetail>(`${path(id)}/status`, { status }),
  remove: (id: string) => api.delete<void>(path(id)),
}
