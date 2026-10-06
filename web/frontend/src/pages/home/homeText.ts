// Textos do Início (W04) que dependem dos números: o subtítulo, as variações dos KPIs, o tempo de
// coleta e a situação de cada sessão de "Precisam de atenção".
import type { AttentionItem, Trend } from '../../api/dashboard'
import type { StatDelta } from '../../components/StatCard/StatCard'
import { formatDate, formatNumber, formatTime, toDate } from '../../lib/format'

const NUMBER_WORDS = ['Nenhuma', 'Uma', 'Duas', 'Três', 'Quatro', 'Cinco', 'Seis', 'Sete', 'Oito', 'Nove', 'Dez']

function sessionsWord(count: number): string {
  const n = NUMBER_WORDS[count] ?? formatNumber(count)
  return `${n} ${count <= 1 ? 'sessão' : 'sessões'}`
}

// "Duas sessões estão em andamento ou aguardando dados." (admin) ou "Duas sessões precisam da sua
// atenção." (pesquisador).
export function attentionSubtitle(count: number, view: 'admin' | 'researcher'): string {
  if (view === 'admin') {
    if (count === 0) return 'Nenhuma sessão em andamento ou aguardando dados.'
    return `${sessionsWord(count)} ${count === 1 ? 'está' : 'estão'} em andamento ou aguardando dados.`
  }
  return `${sessionsWord(count)} ${count <= 1 ? 'precisa' : 'precisam'} da sua atenção.`
}

const MINUS = '−'

// Variação absoluta ("+2", "−1"); sem mudança, nada.
export function countDelta(value: number, previous: number): StatDelta | undefined {
  const diff = value - previous
  if (diff === 0) return undefined
  return { text: `${diff > 0 ? '+' : MINUS}${formatNumber(Math.abs(diff))}`, direction: diff > 0 ? 'up' : 'down' }
}

// Variação percentual contra o mesmo trecho do mês anterior ("+19%"); sem base, nada.
export function percentDelta(trend: Trend): StatDelta | undefined {
  if (trend.previous <= 0) return undefined
  const pct = Math.round(((trend.value - trend.previous) / trend.previous) * 100)
  if (pct === 0) return { text: '0%' }
  return { text: `${pct > 0 ? '+' : MINUS}${formatNumber(Math.abs(pct))}%`, direction: pct > 0 ? 'up' : 'down' }
}

// Tempo de coleta: "26 min", "1 h 05 min", "40 s".
export function formatCollection(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (minutes === 0 && seconds > 0) return `${Math.round(seconds)} s`
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h} h ${String(m).padStart(2, '0')} min` : `${h} h`
}

// "às 14:10" hoje, "ontem às 17:30" ou "em 27/09/2026 às 09:00".
export function atTime(value: string, now: Date = new Date()): string {
  const d = toDate(value)
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const days = Math.round((day(now) - day(d)) / 86_400_000)
  if (days === 0) return `às ${formatTime(d)}`
  if (days === 1) return `ontem às ${formatTime(d)}`
  return `em ${formatDate(d)} às ${formatTime(d)}`
}

const DATA_TEXT: Record<string, string> = {
  waiting: 'recebendo dados',
  processing: 'processando os dados',
  failed: 'falha no processamento',
}

// "Iniciada às 14:10" ou "Encerrada às 11:42, recebendo dados".
export function attentionWhen(item: AttentionItem, now: Date = new Date()): string {
  if (item.status === 'running') return item.started_at ? `Iniciada ${atTime(item.started_at, now)}` : 'Em andamento'
  const ended = item.ended_at ? `Encerrada ${atTime(item.ended_at, now)}` : 'Encerrada'
  const data = DATA_TEXT[item.data_status]
  return data ? `${ended}, ${data}` : ended
}

// O destaque do KPI "Aguardando dados" ("em envio").
export const AWAITING_HIGHLIGHT: Record<string, string> = {
  waiting: 'em envio',
  processing: 'processando',
  failed: 'com falha',
}
