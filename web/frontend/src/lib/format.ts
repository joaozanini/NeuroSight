// Formatos da interface (pt-BR), como nos protótipos: datas dd/mm/aaaa, horários relativos
// ("Hoje, 14:10"), vírgula decimal ("5,0 s", "2,8 MB") e separador de milhar ("1.248").

export type DateInput = Date | string | number

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/

// "1998-03-12" (data sem hora, como nascimento) é lida no fuso local: `new Date()` a trataria
// como meia-noite UTC, que no Brasil ainda é o dia anterior.
export function toDate(value: DateInput): Date {
  if (value instanceof Date) return value
  if (typeof value === 'string') {
    const m = DATE_ONLY.exec(value)
    if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  }
  return new Date(value)
}

const pad = (n: number) => String(n).padStart(2, '0')

export function formatDate(value: DateInput): string {
  const d = toDate(value)
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`
}

export function formatTime(value: DateInput, withSeconds = false): string {
  const d = toDate(value)
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  return withSeconds ? `${hm}:${pad(d.getSeconds())}` : hm
}

// "29/09/2026, 14:26" (ou "29/09/2026, 14:31:07").
export function formatDateTime(value: DateInput, withSeconds = false): string {
  return `${formatDate(value)}, ${formatTime(value, withSeconds)}`
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

// "Hoje, 14:10", "Ontem, 17:30" ou a data, para o que é mais antigo.
export function formatRelative(value: DateInput, now: Date = new Date()): string {
  const d = toDate(value)
  const days = Math.round((startOfDay(now) - startOfDay(d)) / 86_400_000)
  if (days === 0) return `Hoje, ${formatTime(d)}`
  if (days === 1) return `Ontem, ${formatTime(d)}`
  return formatDate(d)
}

const numberFormats = new Map<string, Intl.NumberFormat>()

function numberFormat(options: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = JSON.stringify(options)
  let f = numberFormats.get(key)
  if (!f) {
    f = new Intl.NumberFormat('pt-BR', options)
    numberFormats.set(key, f)
  }
  return f
}

// 1248 -> "1.248"
export function formatNumber(value: number): string {
  return numberFormat({ maximumFractionDigits: 0 }).format(value)
}

// 5 -> "5,0" (casas fixas)
export function formatDecimal(value: number, digits = 1): string {
  return numberFormat({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

// 0.89 -> "89%"
export function formatPercent(fraction: number, digits = 0): string {
  return numberFormat({ style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits })
    .format(fraction)
}

// 5 -> "5,0 s"
export function formatSeconds(seconds: number, digits = 1): string {
  return `${formatDecimal(seconds, digits)} s`
}

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB']

// 2_936_013 -> "2,8 MB"; uma casa abaixo de 10, nenhuma a partir daí ("86 MB", "212 KB").
export function formatBytes(bytes: number): string {
  let value = bytes
  let unit = 0
  while (unit < BYTE_UNITS.length - 1 && Math.round(value) >= 1024) {
    value /= 1024
    unit++
  }
  if (unit === 0) return `${Math.round(value)} B`
  const digits = Math.round(value * 10) / 10 < 10 ? 1 : 0
  return `${formatDecimal(value, digits)} ${BYTE_UNITS[unit]}`
}

// Tempo de sessão: 36 -> "00:36", 65 -> "01:05", 3723 -> "1:02:03".
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`
}

// Duração de mídia: 45 -> "0:45", 80 -> "1:20".
export function formatMediaDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`
}

// Duração por extenso: 110 -> "1 min 50 s".
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const parts: string[] = []
  if (h) parts.push(`${h} h`)
  if (m) parts.push(`${m} min`)
  if (sec || parts.length === 0) parts.push(`${sec} s`)
  return parts.join(' ')
}

// plural(3, 'sessão', 'sessões') -> "3 sessões"
export function plural(count: number, one: string, many: string): string {
  return `${formatNumber(count)} ${count === 1 ? one : many}`
}

// "Ana Souza" -> "AS"; "Carlos" -> "C".
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return ''
  const first = words[0][0]
  const last = words.length > 1 ? words[words.length - 1][0] : ''
  return (first + last).toLocaleUpperCase('pt-BR')
}

// Mensagem do servidor como frase: "E-mail ou senha incorretos" -> "E-mail ou senha incorretos."
export function sentence(text: string): string {
  const t = text.trim()
  return /[.!?…]$/.test(t) ? t : `${t}.`
}
