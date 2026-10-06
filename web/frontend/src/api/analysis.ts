// Análise da sessão (W17): as exibições de estímulo com as métricas do olhar, as marcações, a
// gravação com o olhar em cada frame e as expressões faciais ao longo da sessão.
import { api } from './client'
import { sessionsKeys } from './sessions'
import type { RecordingStatus } from './sessions'
import type { StimulusKind } from './stimuli'
import type { SessionStatus } from '../lib/status'

export interface AnalysisExposure {
  seq: number
  // Posição na sequência da sessão (o número da tira e de "Estímulo N").
  position: number
  stimulus_id: string
  name: string
  kind: StimulusKind
  thumbnail_url: string
  file_url: string
  width: number | null
  height: number | null
  // Segundos desde o início da sessão (relógio do óculos).
  on_t: number
  off_t: number
  samples: number
  valid_samples: number
  fixation_count: number
  mean_fixation_ms: number | null
  first_fixation_ms: number | null
  // [início, duração, u, v]: UV no estímulo, origem em cima à esquerda.
  fixations: [number, number, number, number][]
  // [u, v, amostras]: células da grade com olhar sobre o estímulo.
  heat: [number, number, number][]
}

export interface AnalysisRecording {
  url: string
  fps: number
  width: number
  height: number
  // Instante da sessão de cada frame do vídeo e o olhar nele (UV no quadro).
  frame_t: number[]
  frame_gaze: ([number, number] | null)[]
}

export interface FaceSeries {
  key: string
  label: string
  // Uma média a cada 1/hz s desde o início; null onde não houve leitura.
  values: (number | null)[]
}

export interface SessionAnalysis {
  id: string
  title: string
  patient_code: string
  started_at: string | null
  status: SessionStatus
  duration: number
  exposures: AnalysisExposure[]
  markers: { t: number; text: string }[]
  recording_status: RecordingStatus
  recording: AnalysisRecording | null
  face: { hz: number; series: FaceSeries[] } | null
  can_export: boolean
}

export const analysisApi = {
  get: (id: string, signal?: AbortSignal) =>
    api.get<SessionAnalysis>(`/sessions/${encodeURIComponent(id)}/analysis`, { signal }),
}

export const analysisKey = sessionsKeys.analysis
