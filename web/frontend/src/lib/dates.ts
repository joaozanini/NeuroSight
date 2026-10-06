// Datas digitadas como nos protótipos (dd/mm/aaaa) e o formato da API para datas sem hora
// (aaaa-mm-dd), como nascimento e assinatura do termo.
import { formatDate } from './format'

// Máscara enquanto digita: "12031998" -> "12/03/1998". As barras entram sozinhas.
export function maskDate(text: string): string {
  const digits = text.replace(/\D/g, '').slice(0, 8)
  if (digits.length <= 2) return digits
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`
}

// "12/03/1998" -> "1998-03-12"; null se estiver incompleta ou não existir (31/02/2026).
export function parseBrDate(text: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text.trim())
  if (!m) return null
  const [day, month, year] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null
  return `${m[3]}-${m[2]}-${m[1]}`
}

// "1998-03-12" -> "12/03/1998" (vazio se não houver data).
export function isoToBr(iso: string | null | undefined): string {
  return iso ? formatDate(iso) : ''
}

// Data de hoje no fuso do navegador, no formato da API.
export function todayIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// Idade em anos completos: nascido em 12/03/1998, em 05/10/2026 tem 28.
export function ageOn(birthIso: string, now: Date = new Date()): number {
  const [year, month, day] = birthIso.split('-').map(Number)
  let age = now.getFullYear() - year
  if (now.getMonth() + 1 < month || (now.getMonth() + 1 === month && now.getDate() < day)) age -= 1
  return Math.max(0, age)
}
