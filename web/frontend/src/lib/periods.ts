// Filtro de período das listas (W12, W22), calculado no fuso de quem olha.

export const PERIODS = [
  { value: 'hoje', label: 'Hoje', days: 1 },
  { value: '7d', label: 'Últimos 7 dias', days: 7 },
  { value: '30d', label: 'Últimos 30 dias', days: 30 },
  { value: '90d', label: 'Últimos 90 dias', days: 90 },
  { value: 'tudo', label: 'Todo o período', days: 0 },
]

export const PERIOD_OPTIONS = PERIODS.map(({ value, label }) => ({ value, label }))

// Início do período: "Últimos 7 dias" = hoje e os 6 dias anteriores. Sem início em "Todo o período".
export function periodStart(period: string, now = new Date()): string | undefined {
  const days = PERIODS.find((p) => p.value === period)?.days ?? 7
  if (!days) return undefined
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - (days - 1)).toISOString()
}
