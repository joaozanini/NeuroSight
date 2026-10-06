// Escalas e textos do gráfico de expressões da W17: os tempos do eixo, as séries em caminhos SVG e
// os rótulos das marcações que precisam caber até a próxima.
import { formatClock } from '../../../lib/format'

// Passos do eixo do tempo, em segundos: o menor que deixa até `maxTicks` marcas (1:50 → de 20 em 20 s).
const STEPS = [5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1800, 3600]

export function timeTicks(duration: number, maxTicks = 6): number[] {
  const step = STEPS.find((s) => duration / s <= maxTicks) ?? STEPS[STEPS.length - 1]
  const ticks: number[] = []
  for (let t = 0; t <= duration + 1e-9; t += step) ticks.push(t)
  return ticks
}

// Uma série (um valor a cada 1/hz s, null onde não houve leitura) vira um caminho, interrompido nos buracos.
export function seriesPath(
  values: readonly (number | null)[],
  hz: number,
  x: (t: number) => number,
  y: (v: number) => number,
): string {
  let path = ''
  let open = false
  values.forEach((v, i) => {
    if (v === null) {
      open = false
      return
    }
    // O valor de cada janela fica no meio dela.
    const px = x((i + 0.5) / hz).toFixed(1)
    const py = y(v).toFixed(1)
    path += `${open ? 'L' : 'M'}${px} ${py}`
    open = true
  })
  return path
}

// Largura aproximada de um caractere do rótulo (14 px, Inter): para cortar o texto antes da próxima marcação.
const CHAR_PX = 7.4

// "00:28 Paciente movimentou a cabeça", cortado com reticências se não couber em `room` pixels.
export function markerLabel(t: number, text: string, room: number): string {
  const time = formatClock(t)
  const full = `${time} ${text}`
  const fits = Math.floor(room / CHAR_PX)
  if (full.length <= fits) return full
  if (fits <= time.length + 4) return time
  return `${full.slice(0, fits - 1).trimEnd()}…`
}
