import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Pause, Play } from 'lucide-react'
import type { AnalysisRecording } from '../../../api/analysis'
import { drawGazeCircle, frameIndexAt, sessionTimeAt, videoTimeAt } from '../../../heatmap/gazeVideo'
import { formatClock } from '../../../lib/format'
import styles from './RecordingPlayer.module.css'

// Pedido para levar a gravação a um instante da sessão; o `nonce` repete o pedido para o mesmo instante.
export interface SeekRequest {
  t: number
  nonce: number
}

interface RecordingPlayerProps {
  recording: AnalysisRecording
  // Duração da coleta (o "01:50" do relógio).
  duration: number
  seek: SeekRequest | null
  // O instante da sessão que está na tela, para o cursor do gráfico.
  onTime: (t: number) => void
}

// Raio do círculo do olhar: 3,5% da largura do quadro.
const CIRCLE = 0.035
// A tela do player tem a proporção do protótipo; o quadro da gravação fica contido nela.
const SCREEN_ASPECT = 16 / 10

// A gravação da sessão (W17) com o círculo do olhar e controles próprios: tocar/pausar, a barra de
// posição e o tempo da sessão. O instante de cada frame vem do `frame_t` (o vídeo tem fps constante).
export default function RecordingPlayer({ recording, duration, seek, onTime }: RecordingPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(-2)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const { fps, frame_t: frameT, frame_gaze: frameGaze, width, height } = recording
  const frameStyle: CSSProperties = {
    aspectRatio: `${width} / ${height}`,
    ...(width / height >= SCREEN_ASPECT ? { width: '100%' } : { height: '100%' }),
  }

  // Desenha o círculo do frame atual; só faz algo quando o frame muda.
  const draw = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    const i = frameIndexAt(video.currentTime, fps, frameT.length)
    if (i === frameRef.current) return
    frameRef.current = i
    const t = sessionTimeAt(video.currentTime, fps, frameT)
    setTime(t)
    onTime(t)
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const gaze = i >= 0 ? frameGaze[i] : null
    if (gaze) drawGazeCircle(ctx, gaze[0] * canvas.width, gaze[1] * canvas.height, CIRCLE * canvas.width)
  }, [fps, frameT, frameGaze, onTime])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    let raf = 0
    const loop = () => {
      draw()
      raf = requestAnimationFrame(loop)
    }
    const onPlay = () => {
      setPlaying(true)
      raf = requestAnimationFrame(loop)
    }
    const onStop = () => {
      setPlaying(false)
      cancelAnimationFrame(raf)
      draw()
    }
    video.addEventListener('play', onPlay)
    video.addEventListener('pause', onStop)
    video.addEventListener('ended', onStop)
    video.addEventListener('seeked', draw)
    video.addEventListener('loadeddata', draw)
    video.addEventListener('timeupdate', draw)
    return () => {
      cancelAnimationFrame(raf)
      video.removeEventListener('play', onPlay)
      video.removeEventListener('pause', onStop)
      video.removeEventListener('ended', onStop)
      video.removeEventListener('seeked', draw)
      video.removeEventListener('loadeddata', draw)
      video.removeEventListener('timeupdate', draw)
    }
  }, [draw])

  const goTo = useCallback(
    (t: number) => {
      const video = videoRef.current
      if (!video) return
      video.currentTime = videoTimeAt(t, fps, frameT)
      // Sem esperar o "seeked": o relógio e o cursor do gráfico mudam na hora.
      setTime(t)
      onTime(t)
    },
    [fps, frameT, onTime],
  )

  useEffect(() => {
    if (seek) goTo(seek.t)
  }, [seek, goTo])

  function toggle() {
    const video = videoRef.current
    if (!video) return
    if (video.paused) void video.play()?.catch(() => setPlaying(false))
    else video.pause()
  }

  return (
    <div className={styles.player}>
      <div className={styles.screen}>
        {/* O vídeo e o círculo numa moldura da proporção do quadro, que ocupa a largura ou a altura. */}
        <div className={styles.frame} style={frameStyle}>
          <video ref={videoRef} className={styles.video} src={recording.url} muted playsInline preload="auto" />
          <canvas ref={canvasRef} className={styles.overlay} width={width} height={height} aria-hidden />
        </div>
      </div>
      <div className={styles.controls}>
        <button type="button" className={styles.play} onClick={toggle} aria-label={playing ? 'Pausar a gravação' : 'Tocar a gravação'}>
          {playing ? <Pause size={20} fill="currentColor" strokeWidth={0} /> : <Play size={20} fill="currentColor" strokeWidth={0} />}
        </button>
        <input
          type="range"
          className={styles.range}
          min={0}
          max={Math.max(duration, 0.1)}
          step={0.1}
          value={Math.min(time, duration)}
          onChange={(event) => goTo(Number(event.target.value))}
          aria-label="Posição na gravação"
          aria-valuetext={`${formatClock(time)} de ${formatClock(duration)}`}
          style={{ '--progress': `${duration > 0 ? (100 * Math.min(time, duration)) / duration : 0}%` } as CSSProperties}
        />
        <span className={styles.clock}>
          {formatClock(time)} / {formatClock(duration)}
        </span>
      </div>
    </div>
  )
}
