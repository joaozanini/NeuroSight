import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Gamepad2, Pause, Play, Plus } from 'lucide-react'
import { keepNewest, liveApi, liveKeys, useLiveSession } from '../../../api/live'
import type { ControlAction, LiveSnapshot, Marker } from '../../../api/live'
import { prepareSessionPath, sessionsApi, sessionsKeys } from '../../../api/sessions'
import type { SequenceItem, SessionDetail } from '../../../api/sessions'
import Button from '../../../components/Button/Button'
import FormAlert from '../../../components/FormAlert/FormAlert'
import Logo from '../../../components/Logo/Logo'
import Modal from '../../../components/Modal/Modal'
import Spinner from '../../../components/Spinner/Spinner'
import StimulusThumbnail from '../../../components/StimulusThumbnail/StimulusThumbnail'
import TextField from '../../../components/TextField/TextField'
import TextLink from '../../../components/TextLink/TextLink'
import { useToast } from '../../../components/Toast/toastContext'
import { cx } from '../../../lib/cx'
import { formatClock, sentence } from '../../../lib/format'
import { usePageTitle } from '../../../lib/usePageTitle'
import { switchText } from './liveTexts'
import styles from './LiveControlPage.module.css'

const TITLE = 'Controle da sessão ao vivo'

// W15, em tela cheia: o que o óculos está mostrando, os comandos (que o óculos executa), a sequência
// clicável e as marcações. A sessão termina pelo B no óculos ou por "Interromper sessão".
export default function LiveControlPage() {
  const { sessionId = '' } = useParams()
  usePageTitle(TITLE)
  const session = useQuery({
    queryKey: sessionsKeys.detail(sessionId),
    queryFn: ({ signal }) => sessionsApi.get(sessionId, signal),
  })

  if (session.isPending) {
    return (
      <div className={styles.center}>
        <Spinner size={28} label="Carregando a sessão" />
      </div>
    )
  }
  if (session.isError) {
    return (
      <div className={styles.center}>
        <FormAlert>
          {sentence(session.error.message)} <TextLink to="/sessoes">Voltar para as sessões</TextLink>
        </FormAlert>
      </div>
    )
  }
  const data = session.data
  if (!data.can_run) {
    return (
      <div className={styles.center}>
        <FormAlert>
          Só o responsável pela sessão pode controlá-la. <TextLink to={`/sessoes/${data.id}`}>Ver os detalhes da sessão</TextLink>
        </FormAlert>
      </div>
    )
  }
  if (data.status === 'configured') return <Navigate to={prepareSessionPath(data.id)} replace />
  if (data.status !== 'running') return <Navigate to={`/sessoes/${data.id}`} replace />
  return <LiveControl session={data} />
}

// Segundos desde o início, atualizados a cada meio segundo.
function useElapsed(startedAt: string | null): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(timer)
  }, [])
  return startedAt ? Math.max(0, (now - new Date(startedAt).getTime()) / 1000) : 0
}

function LiveControl({ session }: { session: SessionDetail }) {
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const { snapshot } = useLiveSession(session.id)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const interruptedHere = useRef(false)
  const elapsed = useElapsed(snapshot?.started_at ?? session.started_at)

  const control = useMutation({
    mutationFn: ({ action, position }: { action: ControlAction; position?: number }) =>
      liveApi.control(session.id, action, position),
    onError: (err) => toast.error(sentence(err.message)),
  })
  const interrupt = useMutation({
    mutationFn: () => liveApi.interrupt(session.id),
    // O retrato do fim pode chegar pelo socket antes da resposta.
    onMutate: () => {
      interruptedHere.current = true
    },
    onSuccess: (next) => {
      keepNewest(queryClient, next)
      queryClient.setQueryData<SessionDetail>(sessionsKeys.detail(session.id), (old) => old && { ...old, status: next.status })
    },
    onError: (err) => {
      interruptedHere.current = false
      setConfirmOpen(false)
      toast.error(sentence(err.message))
    },
  })

  // Acabou (o B no óculos ou a interrupção): os dados chegam depois, na W16.
  const status = snapshot?.status
  useEffect(() => {
    if (status !== 'awaiting_data' && status !== 'completed' && status !== 'interrupted') return
    // A W16 abre já com o status novo (e o aviso dos dados), sem piscar o "Em andamento" do cache.
    queryClient.setQueryData<SessionDetail>(sessionsKeys.detail(session.id), (old) => old && { ...old, status })
    queryClient.invalidateQueries({ queryKey: sessionsKeys.all })
    toast.success(
      interruptedHere.current
        ? 'Sessão interrompida. O óculos está enviando o que foi coletado.'
        : 'Sessão encerrada no óculos. Os dados estão sendo enviados.',
    )
    navigate(`/sessoes/${session.id}`, { replace: true })
  }, [status, session.id, navigate, queryClient, toast])

  const device = snapshot?.device
  const online = Boolean(device?.online)
  const playback = snapshot?.playback ?? { position: null, neutral: true, paused: false, shown: [] }
  const total = session.items.length
  const current = playback.position !== null && !playback.neutral ? session.items[playback.position - 1] : undefined
  const send = (action: ControlAction, position?: number) => control.mutate({ action, position })
  const patient = session.patient.name ? `Paciente ${session.patient.code}, ${session.patient.name}` : `Paciente ${session.patient.code}`

  const atEnd = playback.neutral && playback.position === total && playback.shown.includes(total)

  return (
    <div className={styles.screen}>
      <header className={styles.topbar}>
        <div className={styles.identity}>
          <Logo size={30} variant="mark" />
          <div>
            <h1 className={styles.title}>{session.title}</h1>
            <p className={styles.patient}>{patient}</p>
          </div>
        </div>
        <ul className={styles.pills} aria-label="Estado do óculos">
          <Pill tone={session.record ? 'recording' : 'off'}>{session.record ? 'Gravando' : 'Sem gravação'}</Pill>
          <Pill tone={online ? 'ok' : 'bad'}>{online ? 'Óculos conectado' : 'Óculos desconectado'}</Pill>
          <Pill tone={online && device?.tracking.eye === 'active' ? 'ok' : 'bad'}>Eye tracking</Pill>
          <Pill tone={online && device?.tracking.face === 'active' ? 'ok' : 'off'}>Emotion tracking</Pill>
        </ul>
        <div className={styles.clock}>
          <span>Tempo de sessão</span>
          <strong role="timer" aria-live="off">
            {formatClock(elapsed)}
          </strong>
        </div>
        <Button variant="danger-subtle" size="sm" onClick={() => setConfirmOpen(true)}>
          Interromper sessão
        </Button>
      </header>

      <main className={styles.content}>
        <div className={styles.left}>
          <section className={styles.stage} aria-label="Em exibição no óculos">
            <header className={styles.stageHeader}>
              <h2>Em exibição no óculos</h2>
              <span>{positionText(playback, total)}</span>
            </header>
            <Preview item={current} paused={playback.paused} />
            <p className={styles.caption}>
              {current ? (
                <>
                  <strong>{current.name}</strong> <span>{switchText(current)}</span>
                </>
              ) : (
                <>
                  <strong>Tela neutra</strong>{' '}
                  <span>{atEnd ? 'Fim da sequência. Aperte o B no óculos para encerrar.' : 'O óculos mostra só a sala neutra.'}</span>
                </>
              )}
            </p>
          </section>

          <div className={styles.controls}>
            <Button
              variant="secondary"
              icon={ChevronLeft}
              disabled={!online || !playback.position || playback.position <= 1}
              onClick={() => send('previous')}
            >
              Anterior
            </Button>
            <Button variant="secondary" icon={Plus} disabled={!online || playback.neutral} onClick={() => send('neutral')}>
              Tela neutra
            </Button>
            {playback.paused ? (
              <Button variant="secondary" icon={Play} disabled={!online} onClick={() => send('resume')}>
                Retomar vídeo
              </Button>
            ) : (
              <Button variant="secondary" icon={Pause} disabled={!online || current?.kind !== 'video'} onClick={() => send('pause')}>
                Pausar vídeo
              </Button>
            )}
            <Button iconRight={ChevronRight} className={styles.next} disabled={!online || atEnd} onClick={() => send('next')}>
              Próximo estímulo
            </Button>
          </div>
          <p className={styles.hint}>
            <Gamepad2 size={22} strokeWidth={1.6} aria-hidden />
            Para encerrar a sessão, aperte o botão B no controle do óculos.
          </p>
          {!online && (
            <FormAlert className={styles.offline}>
              O óculos está desconectado. A coleta continua nele; os comandos voltam quando ele reconectar.
            </FormAlert>
          )}
        </div>

        <div className={styles.right}>
          <Sequence session={session} playback={playback} disabled={!online} onPick={(position) => send('goto', position)} />
          <Markers sessionId={session.id} />
        </div>
      </main>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Interromper sessão?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setConfirmOpen(false)}>
              Continuar sessão
            </Button>
            <Button variant="danger" size="sm" loading={interrupt.isPending} onClick={() => interrupt.mutate()}>
              Interromper sessão
            </Button>
          </>
        }
      >
        <p className={styles.modalText}>
          A coleta para agora e o óculos envia o que já foi coletado. A sessão termina como Interrompida, e o
          fim fica registrado na auditoria.
        </p>
      </Modal>
    </div>
  )
}

// "Estímulo 3 de 12"; na tela neutra, onde a sequência está.
function positionText(playback: LiveSnapshot['playback'], total: number): string {
  if (!playback.neutral && playback.position !== null) return `Estímulo ${playback.position} de ${total}`
  if (playback.position === null) return `Antes do estímulo 1 de ${total}`
  return `Depois do estímulo ${playback.position} de ${total}`
}

function Pill({ tone, children }: { tone: 'ok' | 'bad' | 'off' | 'recording'; children: ReactNode }) {
  return (
    <li className={cx(styles.pill, styles[tone])}>
      <span className={styles.pillDot} aria-hidden />
      {children}
    </li>
  )
}

// O estímulo como aparece no painel do óculos: inteiro, com faixas escuras nos lados que sobram.
function Preview({ item, paused }: { item?: SequenceItem; paused: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    if (paused) video.pause()
    else void video.play().catch(() => undefined)
  }, [paused, item?.stimulus_id])

  if (!item) return <div className={cx(styles.preview, styles.neutral)} aria-label="Tela neutra" />
  const src = `/api/v1/stimuli/${encodeURIComponent(item.stimulus_id)}/file`
  return (
    <div className={styles.preview}>
      {item.kind === 'video' ? (
        <video key={item.stimulus_id} ref={videoRef} src={src} muted playsInline autoPlay aria-label={item.name} />
      ) : (
        <img src={src} alt={item.name} />
      )}
    </div>
  )
}

function Sequence({
  session,
  playback,
  disabled,
  onPick,
}: {
  session: SessionDetail
  playback: LiveSnapshot['playback']
  disabled: boolean
  onPick: (position: number) => void
}) {
  const currentRef = useRef<HTMLLIElement>(null)
  const showing = playback.neutral ? null : playback.position
  useEffect(() => {
    currentRef.current?.scrollIntoView?.({ block: 'nearest' })
  }, [showing])

  return (
    <section className={styles.sequence} aria-label="Sequência">
      <header className={styles.cardHeader}>
        <h2>Sequência</h2>
        <span>Clique para exibir</span>
      </header>
      <ol className={styles.sequenceList}>
        {session.items.map((item) => {
          const isCurrent = item.position === showing
          const status = isCurrent ? 'Em exibição' : playback.shown.includes(item.position) ? 'Exibido' : 'Pendente'
          return (
            <li key={item.position} ref={isCurrent ? currentRef : undefined}>
              <button
                type="button"
                className={cx(styles.sequenceItem, isCurrent && styles.current)}
                disabled={disabled}
                aria-current={isCurrent ? 'true' : undefined}
                onClick={() => onPick(item.position)}
              >
                <span className={styles.number}>{item.position}</span>
                <StimulusThumbnail
                  src={item.thumbnail_url}
                  kind={item.kind}
                  className={styles.thumb}
                />
                <span className={styles.name}>{item.name}</span>
                <span className={styles.state}>{status}</span>
              </button>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

function Markers({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const markers = useQuery({
    queryKey: liveKeys.markers(sessionId),
    queryFn: ({ signal }) => liveApi.markers(sessionId, signal),
  })
  const mark = useMutation({
    mutationFn: (value: string) => liveApi.mark(sessionId, value),
    onSuccess: (marker) => {
      queryClient.setQueryData<Marker[]>(liveKeys.markers(sessionId), (old) => [...(old ?? []), marker])
      setText('')
      setError(null)
    },
    onError: (err) => setError(sentence(err.message)),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const value = text.trim()
    if (!value) {
      setError('Escreva o que aconteceu.')
      return
    }
    mark.mutate(value)
  }

  // As mais recentes primeiro.
  const list = [...(markers.data ?? [])].reverse()
  return (
    <section className={styles.markers} aria-label="Marcações">
      <h2 className={styles.markersTitle}>Marcações</h2>
      <form className={styles.markForm} onSubmit={submit} noValidate>
        <TextField
          size="sm"
          label="Marcação"
          hideLabel
          placeholder="Ex.: enfermagem entrou no quarto"
          maxLength={200}
          value={text}
          onChange={(event) => setText(event.target.value)}
          error={error ?? undefined}
          fieldClassName={styles.markField}
        />
        <Button type="submit" variant="secondary" size="sm" loading={mark.isPending}>
          Marcar
        </Button>
      </form>
      {list.length > 0 && (
        <ul className={styles.markerList}>
          {list.map((m) => (
            <li key={m.id}>
              <time>{formatClock(m.t)}</time>
              <span>{m.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
