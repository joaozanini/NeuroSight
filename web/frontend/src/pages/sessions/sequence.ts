// Textos da sequência de estímulos (W13 e W16): duração aproximada, resumo da revisão e o tempo
// de tela digitado em segundos.
import { formatDecimal, formatMediaDuration, formatNumber, formatSeconds } from '../../lib/format'
import type { StimulusKind } from '../../api/stimuli'

export interface SequenceEntry {
  kind: StimulusKind
  // Tempo de tela da imagem; null = troca manual.
  duration_seconds: number | null
  media_duration_seconds: number | null
}

// Tempo de tela padrão de uma imagem recém-adicionada (W13).
export const DEFAULT_IMAGE_SECONDS = 5
export const MAX_IMAGE_SECONDS = 3600

// "5" -> 5, "2,5" -> 2.5, "" -> null (troca manual); undefined quando o texto não vale.
export function parseSeconds(text: string): number | null | undefined {
  const t = text.trim().replace(',', '.')
  if (!t) return null
  if (!/^\d+(\.\d+)?$/.test(t)) return undefined
  const value = Number(t)
  if (value < 0.1 || value > MAX_IMAGE_SECONDS) return undefined
  return Math.round(value * 1000) / 1000
}

// 5 -> "5", 2.5 -> "2,5" (o valor no campo e nos textos).
export function secondsText(value: number): string {
  return Number.isInteger(value) ? formatNumber(value) : formatDecimal(value, 1)
}

function knownSeconds(entries: SequenceEntry[]): number {
  return entries.reduce((sum, e) => sum + (e.kind === 'video' ? (e.media_duration_seconds ?? 0) : (e.duration_seconds ?? 0)), 0)
}

function hasManual(entries: SequenceEntry[]): boolean {
  return entries.some((e) => e.kind === 'image' && e.duration_seconds === null)
}

function roughly(seconds: number): string {
  if (seconds < 60) return `${formatNumber(Math.max(1, Math.round(seconds)))} s`
  return `${formatNumber(Math.round(seconds / 60))} min`
}

// "cerca de 1 min"; com trocas manuais, o que se sabe é o mínimo ("mais de 30 s"). Vazio sem tempo nenhum.
export function aboutDuration(entries: SequenceEntry[]): string {
  const seconds = knownSeconds(entries)
  if (seconds <= 0) return ''
  return `${hasManual(entries) ? 'mais de' : 'cerca de'} ${roughly(seconds)}`
}

// Cabeçalho da sequência na etapa 3: "12 estímulos, cerca de 1 min".
export function sequenceHeadline(entries: SequenceEntry[]): string {
  if (entries.length === 0) return 'Nenhum estímulo'
  const count = `${formatNumber(entries.length)} ${entries.length === 1 ? 'estímulo' : 'estímulos'}`
  const about = aboutDuration(entries)
  return about ? `${count}, ${about}` : count
}

function kindsText(entries: SequenceEntry[]): string {
  const images = entries.filter((e) => e.kind === 'image').length
  const videos = entries.length - images
  const parts: string[] = []
  if (images) parts.push(`${formatNumber(images)} ${images === 1 ? 'imagem' : 'imagens'}`)
  if (videos) parts.push(`${formatNumber(videos)} ${videos === 1 ? 'vídeo' : 'vídeos'}`)
  return parts.join(' e ')
}

function switchingText(entries: SequenceEntry[]): string {
  const images = entries.filter((e) => e.kind === 'image')
  if (images.length === 0) return ''
  const timed = images.filter((e) => e.duration_seconds !== null)
  if (timed.length === 0) return 'com troca manual'
  if (timed.length < images.length) return 'com troca automática e manual'
  const first = timed[0].duration_seconds!
  if (timed.every((e) => e.duration_seconds === first)) return `com troca automática a cada ${secondsText(first)} s`
  return 'com troca automática'
}

// Revisão (W13): "12 imagens, cerca de 1 min, com troca automática a cada 5 s".
export function reviewSummary(entries: SequenceEntry[]): string {
  return [kindsText(entries), aboutDuration(entries), switchingText(entries)].filter(Boolean).join(', ')
}

// Coluna "Tempo de tela" da sequência na W16.
export function screenTimeText(entry: SequenceEntry): string {
  if (entry.kind === 'video') {
    return entry.media_duration_seconds != null ? `Vídeo inteiro (${formatMediaDuration(entry.media_duration_seconds)})` : 'Vídeo inteiro'
  }
  return entry.duration_seconds === null ? 'Troca manual' : formatSeconds(entry.duration_seconds)
}

// "Imagem" ou "Vídeo, 0:45" (linha de apoio na biblioteca e na sequência).
export function kindText(kind: StimulusKind, mediaDuration: number | null): string {
  if (kind === 'image') return 'Imagem'
  return mediaDuration != null ? `Vídeo, ${formatMediaDuration(mediaDuration)}` : 'Vídeo'
}
