// Execução ao vivo (W14, W15): achar o óculos, preparar, iniciar, controlar, interromper e marcar.
// O retrato da sessão vem pelo WebSocket /sessions/:id/live a cada mudança (com o GET de reserva);
// o protocolo com o óculos está em docs/protocolo-oculos.md.
import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { API_BASE, api } from './client'
import { sessionsKeys } from './sessions'
import type { SessionStatus } from '../lib/status'

export type TrackingState = 'active' | 'no_permission' | 'unavailable' | 'off'
export type ControlAction = 'next' | 'previous' | 'goto' | 'neutral' | 'pause' | 'resume'

export interface LiveDevice {
  id: string
  name: string | null
  online: boolean
  pairing_code: string | null
  // Mesmo IP público do navegador ("Encontrado na rede").
  same_network: boolean
  paired_by: 'network' | 'code' | null
  state: string
  tracking: { eye?: TrackingState; face?: TrackingState }
}

export interface LiveSnapshot {
  type: 'live'
  // Cresce a cada mudança: entre dois retratos, vale o de versão maior (a resposta de uma rota pode
  // chegar depois de um retrato mais novo vindo do socket).
  version: number
  session_id: string
  status: SessionStatus
  started_at: string | null
  device: LiveDevice | null
  // Óculos livres na mesma rede, enquanto nenhum foi escolhido.
  nearby: { id: string; name: string; pairing_code: string | null }[]
  load: { loaded: number; total: number; error: { stimulus_id: string; message: string } | null }
  // O que o óculos está mostrando: o cursor da sequência, a tela neutra e o vídeo pausado.
  playback: { position: number | null; neutral: boolean; paused: boolean; shown: number[] }
}

export interface Marker {
  id: number
  // Segundos desde o início da sessão.
  t: number
  text: string
  created_at: string
  created_by_name: string | null
}

// Fora de ['sessions']: invalidar as sessões não pode recarregar o retrato que chegou pelo socket.
export const liveKeys = {
  snapshot: (id: string) => ['live', id] as const,
  markers: (id: string) => ['live', id, 'markers'] as const,
}

const path = (id: string) => `/sessions/${encodeURIComponent(id)}`

export const liveApi = {
  snapshot: (id: string, signal?: AbortSignal) => api.get<LiveSnapshot>(`${path(id)}/live`, { signal }),
  prepare: (id: string, target: { device_id: string } | { pairing_code: string }) =>
    api.post<LiveSnapshot>(`${path(id)}/prepare`, target),
  release: (id: string) => api.post<LiveSnapshot>(`${path(id)}/release`),
  start: (id: string) => api.post<LiveSnapshot>(`${path(id)}/start`),
  control: (id: string, action: ControlAction, position?: number) =>
    api.post<{ command_id: number }>(`${path(id)}/control`, position === undefined ? { action } : { action, position }),
  interrupt: (id: string) => api.post<LiveSnapshot>(`${path(id)}/interrupt`),
  markers: (id: string, signal?: AbortSignal) => api.get<Marker[]>(`${path(id)}/markers`, { signal }),
  mark: (id: string, text: string) => api.post<Marker>(`${path(id)}/markers`, { text }),
}

// Guarda o retrato só se ele for mais novo que o do cache; devolve o que ficou.
export function keepNewest(queryClient: QueryClient, next: LiveSnapshot): LiveSnapshot {
  const key = liveKeys.snapshot(next.session_id)
  const current = queryClient.getQueryData<LiveSnapshot>(key)
  if (current && current.version > next.version) return current
  queryClient.setQueryData(key, next)
  return next
}

// Fechamentos que não adianta tentar de novo: sem login ou sem acesso à sessão.
const FINAL_CLOSE_CODES = new Set([4401, 4404])

function liveUrl(id: string): string {
  const { protocol, host } = window.location
  return `${protocol === 'https:' ? 'wss' : 'ws'}://${host}${API_BASE}${path(id)}/live`
}

// O retrato da sessão, sempre atualizado: o GET responde primeiro e o WebSocket substitui a cada
// mudança, reconectando sozinho (1 s, 2 s, 4 s... até 15 s). `connected` diz se o canal está aberto.
export function useLiveSession(sessionId: string) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: liveKeys.snapshot(sessionId),
    queryFn: async ({ signal }) => {
      const next = await liveApi.snapshot(sessionId, signal)
      const current = queryClient.getQueryData<LiveSnapshot>(liveKeys.snapshot(sessionId))
      return current && current.version > next.version ? current : next
    },
  })
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let socket: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let delay = 1000
    let stopped = false

    function open() {
      socket = new WebSocket(liveUrl(sessionId))
      socket.onopen = () => {
        delay = 1000
        setConnected(true)
      }
      socket.onmessage = (event) => {
        const message = JSON.parse(String(event.data)) as LiveSnapshot
        if (message.type !== 'live') return
        const previous = queryClient.getQueryData<LiveSnapshot>(liveKeys.snapshot(sessionId))
        const kept = keepNewest(queryClient, message)
        if (previous && previous.status !== kept.status) {
          queryClient.invalidateQueries({ queryKey: sessionsKeys.all })
        }
      }
      socket.onclose = (event) => {
        setConnected(false)
        if (stopped || FINAL_CLOSE_CODES.has(event.code)) return
        timer = setTimeout(open, delay)
        delay = Math.min(delay * 2, 15000)
      }
    }

    open()
    return () => {
      stopped = true
      clearTimeout(timer)
      socket?.close()
    }
  }, [sessionId, queryClient])

  return { snapshot: query.data, error: query.error, isPending: query.isPending, connected }
}
