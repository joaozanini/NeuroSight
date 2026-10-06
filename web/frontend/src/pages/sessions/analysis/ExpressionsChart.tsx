import { useId, useMemo, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { AnalysisExposure, FaceSeries } from '../../../api/analysis'
import { formatClock } from '../../../lib/format'
import { useElementWidth } from '../../../lib/useElementWidth'
import { markerLabel, seriesPath, timeTicks } from './chartScale'
import styles from './ExpressionsChart.module.css'

// Margens do gráfico: os valores do eixo à esquerda, as marcações em cima e os tempos embaixo.
const LEFT = 48
const RIGHT = 8
const TOP = 34
const PLOT = 180
const BOTTOM = 34
const HEIGHT = TOP + PLOT + BOTTOM

// Traço de cada expressão da legenda padrão (as outras, se vierem, ficam em cinza).
export const SERIES_STYLES: Record<string, string> = {
  INNER_BROW_RAISER: styles.solid,
  LIP_CORNER_PULLER: styles.dashed,
  EYES_CLOSED: styles.dotted,
}

interface ExpressionsChartProps {
  duration: number
  hz: number
  series: FaceSeries[]
  exposures: AnalysisExposure[]
  markers: { t: number; text: string }[]
  selectedSeq: number | null
  // Cursor: o instante da gravação (ou o começo do estímulo escolhido, sem gravação).
  cursor: number | null
  onSelect: (seq: number) => void
}

// "Expressões faciais ao longo da sessão" (W17): as séries de 0 a 1, uma faixa listrada por
// exibição de estímulo (clicar escolhe o estímulo), as marcações e o cursor do tempo atual.
export default function ExpressionsChart(props: ExpressionsChartProps) {
  const { duration, hz, series, exposures, markers, selectedSeq, cursor, onSelect } = props
  const boxRef = useRef<HTMLDivElement>(null)
  const width = useElementWidth(boxRef, 1000)
  const hatch = `hachura-${useId().replace(/:/g, '')}`
  const plotW = Math.max(10, width - LEFT - RIGHT)
  const span = Math.max(duration, 1)
  const x = (t: number) => LEFT + (Math.min(Math.max(t, 0), span) / span) * plotW
  const y = (v: number) => TOP + (1 - Math.min(Math.max(v, 0), 1)) * PLOT

  // Os caminhos só mudam com os dados e com a largura e a duração, que definem x e y (o cursor anda a
  // cada frame da gravação e não deve refazê-los).
  const paths = useMemo(
    () => series.map((s) => ({ ...s, d: seriesPath(s.values, hz, x, y) })),
    [series, hz, plotW, span],
  )
  const ticks = timeTicks(span)
  const sortedMarkers = [...markers].sort((a, b) => a.t - b.t)

  function onBandKey(event: KeyboardEvent<SVGRectElement>, seq: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(seq)
    }
  }

  return (
    <div ref={boxRef} className={styles.box}>
      <svg width={width} height={HEIGHT} className={styles.chart} role="group" aria-label="Expressões faciais ao longo da sessão">
        <defs>
          <pattern id={hatch} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" className={styles.hatchBase} />
            <rect width="3" height="8" className={styles.hatchLine} />
          </pattern>
        </defs>

        {exposures.map((e) => {
          const selected = e.seq === selectedSeq
          return (
            <rect
              key={e.seq}
              x={x(e.on_t)}
              y={TOP}
              width={Math.max(1, x(e.off_t) - x(e.on_t))}
              height={PLOT}
              fill={selected ? undefined : `url(#${hatch})`}
              className={selected ? styles.bandSelected : styles.band}
              role="button"
              tabIndex={0}
              aria-pressed={selected}
              aria-label={`Analisar o estímulo ${e.position}: ${e.name}, de ${formatClock(e.on_t)} a ${formatClock(e.off_t)}`}
              onClick={() => onSelect(e.seq)}
              onKeyDown={(event) => onBandKey(event, e.seq)}
            >
              <title>{`Estímulo ${e.position}: ${e.name}`}</title>
            </rect>
          )
        })}

        {[1, 0.5].map((v) => (
          <line key={v} x1={LEFT} x2={LEFT + plotW} y1={y(v)} y2={y(v)} className={styles.grid} />
        ))}
        <line x1={LEFT} x2={LEFT + plotW} y1={y(0)} y2={y(0)} className={styles.axis} />
        {[
          [1, '1'],
          [0.5, '0,5'],
          [0, '0'],
        ].map(([v, label]) => (
          <text key={label} x={LEFT - 12} y={y(v as number)} dy="0.35em" className={styles.yLabel}>
            {label}
          </text>
        ))}
        {/* O rótulo que cairia para fora do gráfico (o do fim) termina na borda. */}
        {ticks.map((t) => (
          <text
            key={t}
            x={x(t)}
            y={TOP + PLOT + 24}
            textAnchor={x(t) > width - 24 ? 'end' : 'middle'}
            className={styles.xLabel}
          >
            {formatClock(t)}
          </text>
        ))}

        {sortedMarkers.map((m, i) => {
          const mx = x(m.t)
          const next = i + 1 < sortedMarkers.length ? x(sortedMarkers[i + 1].t) : LEFT + plotW
          return (
            <g key={`${m.t}-${i}`} className={styles.marker}>
              <line x1={mx} x2={mx} y1={TOP - 26} y2={y(0)} />
              <text x={mx + 6} y={TOP - 12}>
                {markerLabel(m.t, m.text, next - mx - 14)}
              </text>
            </g>
          )
        })}

        {paths.map((s) => (
          <path key={s.key} d={s.d} className={SERIES_STYLES[s.key] ?? styles.other} />
        ))}

        {cursor !== null && <line x1={x(cursor)} x2={x(cursor)} y1={TOP} y2={y(0) + 6} className={styles.cursor} />}
      </svg>
    </div>
  )
}
