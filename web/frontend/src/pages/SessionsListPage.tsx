import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSessions, deleteSession } from '../api/client'
import type { SessionSummary } from '../api/client'

export default function SessionsListPage() {
  const [items, setItems] = useState<SessionSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setErr(null)
    try {
      const d = await listSessions(100, 0)
      setItems(d.items)
      setTotal(d.total)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function onDelete(id: string) {
    if (!confirm('Apagar esta sessão e a mídia?')) return
    try {
      await deleteSession(id)
      load()
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Sessões</h1>
          <p className="sub">{total === 1 ? '1 registro' : `${total} registros`}</p>
        </div>
        <button className="btn" onClick={load} disabled={loading}>
          ↻ Atualizar
        </button>
      </div>

      {loading && (
        <div className="state">
          <span className="spinner" /> Carregando…
        </div>
      )}

      {!loading && err && (
        <p className="error">
          Erro: {err}. A API está rodando em <code>:8000</code>?
        </p>
      )}

      {!loading && !err && items.length === 0 && (
        <div className="card empty">
          <h3>Nenhuma sessão ainda</h3>
          <p>
            Envie uma com <code>scripts/replay_session.py</code> ou apertando <strong>B</strong> no óculos.
          </p>
        </div>
      )}

      {!loading && !err && items.length > 0 && (
        <div className="card table-card">
          <table className="grid">
            <thead>
              <tr>
                <th>Sessão</th>
                <th>Duração</th>
                <th>Frames</th>
                <th>Amostras</th>
                <th>Válidas</th>
                <th>Status</th>
                <th>Vídeo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={`/sessions/${s.id}`} className="session-name mono">
                      {s.device_session_id}
                    </Link>
                    <div className="muted small">{fmtDate(s.captured_at ?? s.created_at)}</div>
                  </td>
                  <td className="num">{s.duration_seconds != null ? `${s.duration_seconds.toFixed(1)}s` : '—'}</td>
                  <td className="num">{s.frame_count}</td>
                  <td className="num">{s.sample_count}</td>
                  <td className="num">
                    <span className={`dot ${s.valid_sample_count > 0 ? 'ok' : 'off'}`} />
                    {s.valid_sample_count}
                  </td>
                  <td>
                    <span className={`badge ${s.status}`}>{s.status}</span>
                  </td>
                  <td>{videoCell(s)}</td>
                  <td>
                    <button className="link danger" onClick={() => onDelete(s.id)}>
                      apagar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function videoCell(s: SessionSummary) {
  if (!s.has_video) return <span className="muted">—</span>
  if (s.video_codec === 'mp4v')
    return (
      <span className="chip-warn" title="mp4v pode não tocar no Chrome">
        ⚠ mp4v
      </span>
    )
  return <span style={{ color: 'var(--success)' }}>✓</span>
}

function fmtDate(s: string | null): string {
  if (!s) return ''
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleString()
}
