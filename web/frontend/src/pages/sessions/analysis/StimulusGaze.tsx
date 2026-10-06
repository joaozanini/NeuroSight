import { useEffect, useRef } from 'react'
import type { AnalysisExposure } from '../../../api/analysis'
import { accumulate, paint } from '../../../heatmap/heatmapEngine'
import { BLUE_LUT } from '../../../heatmap/palette'
import styles from './StimulusGaze.module.css'

export type GazeView = 'heatmap' | 'path'

// O mapa de calor é calculado em resolução reduzida e o canvas o amplia com suavização.
const HEAT_WIDTH = 160
// Desvio da gaussiana: 4% da largura do estímulo (perto de 2° de ângulo visual no painel do óculos).
const HEAT_SIGMA = 0.04
// A trajetória é desenhada numa grade de 640 de largura, perto do tamanho na tela.
const PATH_WIDTH = 640

function aspectOf(exposure: AnalysisExposure): number {
  return exposure.width && exposure.height ? exposure.width / exposure.height : 16 / 10
}

// O estímulo exibido com o olhar por cima (W17): o mapa de calor do tempo de olhar ou a trajetória,
// com cada fixação numerada na ordem e o tamanho pela duração.
export default function StimulusGaze({ exposure, view }: { exposure: AnalysisExposure; view: GazeView }) {
  const aspect = aspectOf(exposure)
  return (
    <div className={styles.stage} style={{ aspectRatio: String(aspect) }}>
      {exposure.kind === 'video' ? (
        <video className={styles.media} src={`${exposure.file_url}#t=0.1`} muted playsInline preload="metadata" aria-hidden />
      ) : (
        <img className={styles.media} src={exposure.file_url} alt="" />
      )}
      {view === 'heatmap' ? <Heatmap exposure={exposure} aspect={aspect} /> : <Path exposure={exposure} aspect={aspect} />}
    </div>
  )
}

function Heatmap({ exposure, aspect }: { exposure: AnalysisExposure; aspect: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const accW = HEAT_WIDTH
  const accH = Math.max(1, Math.round(HEAT_WIDTH / aspect))

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const acc = accumulate(exposure.heat, accW, accH, HEAT_SIGMA * accW)
    const img = paint(acc, accW, accH, BLUE_LUT)
    if (!img) return
    const small = document.createElement('canvas')
    small.width = accW
    small.height = accH
    small.getContext('2d')?.putImageData(img, 0, 0)
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(small, 0, 0, canvas.width, canvas.height)
  }, [exposure, accW, accH])

  const empty = exposure.heat.length === 0
  return (
    <>
      <canvas
        ref={canvasRef}
        className={styles.overlay}
        width={accW * 4}
        height={accH * 4}
        role="img"
        aria-label={empty ? 'Sem olhar sobre o estímulo' : `Mapa de calor do olhar sobre ${exposure.name}`}
      />
      {empty && <span className={styles.empty}>O olhar não caiu sobre o estímulo nesta exibição.</span>}
    </>
  )
}

function Path({ exposure, aspect }: { exposure: AnalysisExposure; aspect: number }) {
  const width = PATH_WIDTH
  const height = Math.round(PATH_WIDTH / aspect)
  const fixations = exposure.fixations
  const longest = Math.max(0.001, ...fixations.map((f) => f[1]))
  const points = fixations.map(([, , u, v]) => `${(u * width).toFixed(1)},${(v * height).toFixed(1)}`).join(' ')
  return (
    <>
      <svg
        className={styles.overlay}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Trajetória do olhar sobre ${exposure.name}: ${fixations.length} fixações`}
      >
        {fixations.length > 1 && <polyline className={styles.pathLine} points={points} />}
        {fixations.map(([start, duration, u, v], i) => (
          <g key={`${start}`} className={styles.fixation}>
            <circle cx={u * width} cy={v * height} r={8 + 12 * Math.sqrt(duration / longest)} />
            <text x={u * width} y={v * height} dy="0.35em">
              {i + 1}
            </text>
          </g>
        ))}
      </svg>
      {fixations.length === 0 && <span className={styles.empty}>Nenhuma fixação nesta exibição.</span>}
    </>
  )
}
