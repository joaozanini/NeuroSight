// Cliente da API. Tudo via /api (proxy do Vite -> :8000), então é same-origin.

export interface SessionSummary {
  id: string
  device_session_id: string
  status: string
  captured_at: string | null
  created_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  frame_count: number
  declared_frame_count: number
  sample_count: number
  valid_sample_count: number
  frame_width: number | null
  frame_height: number | null
  video_fps: number | null
  video_codec: string | null
  has_video: boolean
}

export interface GazeSample {
  t: number
  valid: boolean
  uv: [number, number]
  world?: number[]
  confidence?: number
}

export interface GazeFrame {
  idx: number
  t: number
  file: string
}

export interface SessionDetail extends SessionSummary {
  meta: Record<string, unknown>
  frames: GazeFrame[]
  samples: GazeSample[]
  uv_origin: string | null
  capture_fov_deg: number | null
  video_url: string | null
  error_detail: string | null
}

export interface SessionList {
  items: SessionSummary[]
  total: number
  limit: number
  offset: number
}

const API = '/api/v1'

export async function listSessions(limit = 100, offset = 0): Promise<SessionList> {
  const r = await fetch(`${API}/sessions?limit=${limit}&offset=${offset}`)
  if (!r.ok) throw new Error(`lista falhou: HTTP ${r.status}`)
  return r.json()
}

export async function getSession(id: string): Promise<SessionDetail> {
  const r = await fetch(`${API}/sessions/${id}`)
  if (!r.ok) throw new Error(`detalhe falhou: HTTP ${r.status}`)
  return r.json()
}

export async function deleteSession(id: string): Promise<void> {
  const r = await fetch(`${API}/sessions/${id}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(`delete falhou: HTTP ${r.status}`)
}
