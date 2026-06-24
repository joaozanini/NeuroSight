import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getSession } from '../api/client'
import type { SessionDetail } from '../api/client'
import HeatmapOverlay from '../heatmap/HeatmapOverlay'
import type { ViewerMode } from '../heatmap/HeatmapOverlay'

export default function SessionDetailPage() {
  const { id } = useParams()
  const [sess, setSess] = useState<SessionDetail | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [mode, setMode] = useState<ViewerMode>('heatmap')
  const [sigma, setSigma] = useState(35)
  const [windowS, setWindowS] = useState(1.5)
  const [alpha, setAlpha] = useState(0.5)

  useEffect(() => {
    if (!id) return
    setSess(null)
    setErr(null)
    getSession(id)
      .then(setSess)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [id])

  // ordena os frames por idx (todos os hooks antes de qualquer return condicional)
  const frames = useMemo(() => (sess ? [...sess.frames].sort((a, b) => a.idx - b.idx) : []), [sess])

  if (err) return <p className="error">Erro: {err}</p>
  if (!sess)
    return (
      <div className="state">
        <span className="spinner" /> Carregando…
      </div>
    )

  const fw = sess.frame_width ?? 1024
  const fh = sess.frame_height ?? 1024
  const fps = sess.video_fps ?? 15
  const modes: ViewerMode[] = ['off', 'heatmap', 'validate']

  return (
    <div>
      <div className="detail-head">
        <Link to="/" className="back">
          ← Sessões
        </Link>
        <div className="title-row">
          <h1>{sess.device_session_id}</h1>
          <span className={`badge ${sess.status}`}>{sess.status}</span>
          {sess.video_codec === 'mp4v' && (
            <span className="chip-warn" title="mp4v pode não tocar no Chrome">
              ⚠ vídeo mp4v
            </span>
          )}
        </div>
        <div className="stats">
          <Stat k="Resolução" v={`${fw}×${fh}`} />
          <Stat k="FPS" v={String(fps)} />
          <Stat k="Frames" v={String(sess.frame_count)} />
          <Stat k="Válidas" v={`${sess.valid_sample_count}/${sess.sample_count}`} />
          <Stat k="Duração" v={sess.duration_seconds != null ? `${sess.duration_seconds.toFixed(1)}s` : '—'} />
        </div>
      </div>

      {sess.valid_sample_count === 0 && (
        <p className="notice">
          <span>ⓘ</span>
          <span>
            Esta sessão não tem amostras de gaze válidas (eye tracker não calibrado), então o heatmap fica
            vazio — o vídeo toca normalmente.
          </span>
        </p>
      )}

      {sess.video_url ? (
        <div className="card viewer-card">
          <HeatmapOverlay
            videoUrl={sess.video_url}
            frames={frames}
            samples={sess.samples}
            videoFps={fps}
            frameWidth={fw}
            frameHeight={fh}
            mode={mode}
            sigma={sigma}
            window={windowS}
            alpha={alpha}
          />

          <div className="controls">
            <div className="seg">
              {modes.map((m) => (
                <button key={m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>
                  {label(m)}
                </button>
              ))}
            </div>
            {mode === 'heatmap' && (
              <>
                <Slider label={`σ ${sigma}px`} min={5} max={120} step={1} value={sigma} onChange={setSigma} />
                <Slider
                  label={`janela ${windowS.toFixed(1)}s`}
                  min={0.1}
                  max={5}
                  step={0.1}
                  value={windowS}
                  onChange={setWindowS}
                />
                <Slider
                  label={`opacidade ${alpha.toFixed(2)}`}
                  min={0}
                  max={1}
                  step={0.05}
                  value={alpha}
                  onChange={setAlpha}
                />
              </>
            )}
          </div>

          {mode === 'heatmap' && (
            <div className="jet-legend">
              <span>menos olhar</span>
              <span className="jet-bar" />
              <span>mais olhar</span>
            </div>
          )}
        </div>
      ) : (
        <p className="error">Vídeo não disponível (status: {sess.status}).</p>
      )}
    </div>
  )
}

function label(m: ViewerMode): string {
  return m === 'off' ? 'Sem heatmap' : m === 'heatmap' ? 'Heatmap' : 'Validate'
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="stat">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  )
}

function Slider(props: {
  label: string
  min: number
  max: number
  step: number
  value: number
  onChange: (n: number) => void
}) {
  return (
    <label className="slider">
      <span>{props.label}</span>
      <input
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={props.value}
        onChange={(e) => props.onChange(parseFloat(e.target.value))}
      />
    </label>
  )
}
