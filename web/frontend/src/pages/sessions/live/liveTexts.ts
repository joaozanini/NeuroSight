// Textos da execução ao vivo (W14, W15): estado dos rastreamentos e a forma de troca do estímulo.
import type { TrackingState } from '../../../api/live'
import type { SequenceItem } from '../../../api/sessions'
import { formatMediaDuration } from '../../../lib/format'
import { secondsText } from '../sequence'

export const TRACKING_LABELS: Record<TrackingState, string> = {
  active: 'Ativo',
  no_permission: 'Sem permissão',
  unavailable: 'Indisponível',
  off: 'Desligado',
}

export function trackingLabel(state: TrackingState | undefined): string {
  return state ? TRACKING_LABELS[state] : 'Sem informação'
}

// "Imagem, troca automática a cada 5 s", "Imagem, troca manual" ou "Vídeo, avança ao terminar (0:45)".
export function switchText(item: Pick<SequenceItem, 'kind' | 'duration_seconds' | 'media_duration_seconds'>): string {
  if (item.kind === 'video') {
    const length = item.media_duration_seconds != null ? ` (${formatMediaDuration(item.media_duration_seconds)})` : ''
    return `Vídeo, avança ao terminar${length}`
  }
  return item.duration_seconds === null
    ? 'Imagem, troca manual'
    : `Imagem, troca automática a cada ${secondsText(item.duration_seconds)} s`
}
