import { useCallback, useEffect, useMemo, useRef } from 'react'
import type { GazeFrame, GazeSample } from '../api/client'
import { renderHeatmapImageData } from './heatmapEngine'

export type ViewerMode = 'off' | 'heatmap' | 'validate'

interface Props {
  videoUrl: string
  frames: GazeFrame[]
  samples: GazeSample[]
  videoFps: number
  frameWidth: number
  frameHeight: number
  mode: ViewerMode
  sigma: number
  window: number
  alpha: number
}

export default function HeatmapOverlay(props: Props) {
  const { videoUrl, frames, samples, videoFps, frameWidth, frameHeight, mode, sigma, window: win, alpha } = props
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const accCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const lastKeyRef = useRef<string>('')

  // amostras válidas com uv em [0,1] (heatmap e validate só usam essas)
  const validSamples = useMemo(() => samples.filter((s) => s.valid && inUnit(s.uv)), [samples])

  // acumulador em quarter-res
  const accW = Math.max(1, Math.round(frameWidth * 0.25))
  const accH = Math.max(1, Math.round(frameHeight * 0.25))

  useEffect(() => {
    if (!accCanvasRef.current) accCanvasRef.current = document.createElement('canvas')
    accCanvasRef.current.width = accW
    accCanvasRef.current.height = accH
    lastKeyRef.current = '' // força redesenho quando a resolução muda
  }, [accW, accH])

  // Desenha o overlay para o tempo atual do vídeo. Idempotente via lastKeyRef.
  const render = useCallback(() => {
    const v = videoRef.current
    const c = canvasRef.current
    if (!v || !c) return
    const ctx = c.getContext('2d')
    if (!ctx) return

    const gt = gazeTimeFromVideo(v.currentTime, videoFps, frames)
    const key = `${mode}|${sigma}|${win}|${alpha}|${Math.round(gt * 1000)}`
    if (key === lastKeyRef.current) return
    lastKeyRef.current = key

    ctx.clearRect(0, 0, c.width, c.height)
    if (mode === 'heatmap') {
      const img = renderHeatmapImageData(validSamples, gt, accW, accH, frameWidth, sigma, win, alpha)
      const acc = accCanvasRef.current
      if (img && acc) {
        acc.getContext('2d')!.putImageData(img, 0, 0)
        ctx.imageSmoothingEnabled = true
        ctx.drawImage(acc, 0, 0, accW, accH, 0, 0, c.width, c.height)
      }
    } else if (mode === 'validate') {
      const s = nearest(validSamples, gt)
      if (s) drawCrosshair(ctx, s.uv[0] * c.width, s.uv[1] * c.height)
    }
  }, [mode, sigma, win, alpha, validSamples, frames, videoFps, accW, accH, frameWidth])

  useEffect(() => {
    lastKeyRef.current = '' // parâmetros/dados mudaram -> permite o próximo desenho
    render() // desenha já (cobre vídeo pausado, aba oculta e mudança de slider)

    // rAF mantém o overlay suave durante o play (quando a aba está visível);
    // os eventos do vídeo cobrem seek/pausa e abas não-visíveis (onde o rAF não dispara).
    let raf = 0
    const loop = () => {
      render()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    const v = videoRef.current
    const onEvent = () => render()
    v?.addEventListener('seeked', onEvent)
    v?.addEventListener('timeupdate', onEvent)
    v?.addEventListener('loadeddata', onEvent)
    return () => {
      cancelAnimationFrame(raf)
      v?.removeEventListener('seeked', onEvent)
      v?.removeEventListener('timeupdate', onEvent)
      v?.removeEventListener('loadeddata', onEvent)
    }
  }, [render])

  return (
    <div className="viewer" style={{ aspectRatio: `${frameWidth} / ${frameHeight}` }}>
      <video ref={videoRef} src={videoUrl} controls playsInline />
      <canvas ref={canvasRef} width={frameWidth} height={frameHeight} className="overlay" />
    </div>
  )
}

function inUnit(uv: [number, number]): boolean {
  return !!uv && uv[0] >= 0 && uv[0] <= 1 && uv[1] >= 0 && uv[1] <= 1
}

// currentTime do vídeo (fps constante) -> índice do frame -> tempo de gaze real desse frame.
// Sem isso o overlay derraparia, porque os frames têm dt não-uniforme.
function gazeTimeFromVideo(currentTime: number, fps: number, frames: GazeFrame[]): number {
  if (!frames.length) return currentTime
  const i = Math.min(frames.length - 1, Math.max(0, Math.floor(currentTime * fps)))
  return frames[i]?.t ?? currentTime
}

function nearest(valid: GazeSample[], t: number): GazeSample | null {
  if (!valid.length) return null
  let best = valid[0]
  let bd = Math.abs(valid[0].t - t)
  for (const s of valid) {
    const d = Math.abs(s.t - t)
    if (d < bd) {
      bd = d
      best = s
    }
  }
  return best
}

function drawCrosshair(ctx: CanvasRenderingContext2D, cx: number, cy: number) {
  ctx.strokeStyle = 'rgb(0,255,0)'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.arc(cx, cy, 14, 0, Math.PI * 2)
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(cx - 14, cy)
  ctx.lineTo(cx + 14, cy)
  ctx.moveTo(cx, cy - 14)
  ctx.lineTo(cx, cy + 14)
  ctx.stroke()
}
