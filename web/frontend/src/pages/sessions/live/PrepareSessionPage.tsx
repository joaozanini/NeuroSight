import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Circle, Play, RectangleGoggles } from 'lucide-react'
import { dashboardKeys } from '../../../api/dashboard'
import { keepNewest, liveApi, useLiveSession } from '../../../api/live'
import type { LiveSnapshot, TrackingState } from '../../../api/live'
import { controlSessionPath, sessionsApi, sessionsKeys } from '../../../api/sessions'
import type { SessionDetail } from '../../../api/sessions'
import Badge from '../../../components/Badge/Badge'
import Button from '../../../components/Button/Button'
import Card from '../../../components/Card/Card'
import Checkbox from '../../../components/Checkbox/Checkbox'
import FormAlert from '../../../components/FormAlert/FormAlert'
import CheckCircleFilled from '../../../components/icons/CheckCircleFilled'
import PageHeader from '../../../components/PageHeader/PageHeader'
import ProgressBar from '../../../components/ProgressBar/ProgressBar'
import Spinner from '../../../components/Spinner/Spinner'
import TextField from '../../../components/TextField/TextField'
import TextLink from '../../../components/TextLink/TextLink'
import { cx } from '../../../lib/cx'
import { sentence } from '../../../lib/format'
import { usePageTitle } from '../../../lib/usePageTitle'
import { trackingLabel } from './liveTexts'
import styles from './PrepareSessionPage.module.css'

const BACK = { to: '/sessoes', label: 'Sessões' }
const TITLE = 'Preparar sessão'

// W14: acha o óculos (pelo IP ou pelo código), manda a sessão para ele e mostra o carregamento dos
// estímulos. "Iniciar sessão" só fica ativo com o óculos conectado, tudo carregado, o eye tracking
// ativo e o óculos no paciente.
export default function PrepareSessionPage() {
  const { sessionId = '' } = useParams()
  usePageTitle(TITLE)
  const session = useQuery({
    queryKey: sessionsKeys.detail(sessionId),
    queryFn: ({ signal }) => sessionsApi.get(sessionId, signal),
  })

  if (session.isPending) {
    return (
      <>
        <PageHeader title={TITLE} back={BACK} />
        <Spinner size={28} label="Carregando a sessão" />
      </>
    )
  }
  if (session.isError) {
    return (
      <>
        <PageHeader title={TITLE} back={BACK} />
        <FormAlert>{sentence(session.error.message)}</FormAlert>
      </>
    )
  }

  const data = session.data
  if (data.status === 'running' && data.can_run) return <Navigate to={controlSessionPath(data.id)} replace />
  let blocked: string | null = null
  if (!data.can_run) blocked = 'Só o responsável pela sessão pode prepará-la e executá-la.'
  else if (data.status !== 'configured') blocked = 'Esta sessão já foi executada.'
  if (blocked) {
    return (
      <>
        <PageHeader title={TITLE} subtitle={subtitle(data)} back={BACK} />
        <FormAlert>
          {blocked} <TextLink to={`/sessoes/${data.id}`}>Ver os detalhes da sessão</TextLink>
        </FormAlert>
      </>
    )
  }
  return <Preparation session={data} />
}

function subtitle(session: SessionDetail): string {
  return `${session.title}, paciente ${session.patient.code}.`
}

function Preparation({ session }: { session: SessionDetail }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { snapshot, error } = useLiveSession(session.id)
  const [onPatient, setOnPatient] = useState(false)
  const [code, setCode] = useState('')
  const [codeError, setCodeError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const autoTried = useRef(false)

  const setSnapshot = (next: LiveSnapshot) => keepNewest(queryClient, next)
  const prepare = useMutation({
    mutationFn: (target: { device_id: string } | { pairing_code: string }) => liveApi.prepare(session.id, target),
    onSuccess: (next) => {
      setSnapshot(next)
      setActionError(null)
    },
  })
  const prepareDevice = prepare.mutate
  const start = useMutation({
    mutationFn: () => liveApi.start(session.id),
    onSuccess: (next) => {
      setSnapshot(next)
      // A W15 decide pela sessão em cache: ela já precisa estar Em andamento.
      queryClient.setQueryData<SessionDetail>(sessionsKeys.detail(session.id), (old) =>
        old && { ...old, status: next.status, started_at: next.started_at, date: next.started_at ?? old.date },
      )
      queryClient.invalidateQueries({ queryKey: sessionsKeys.lists })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.badge })
      navigate(controlSessionPath(session.id))
    },
    onError: (err) => setActionError(sentence(err.message)),
  })
  const release = useMutation({
    mutationFn: () => liveApi.release(session.id),
    onSettled: () => navigate(`/sessoes/${session.id}`),
  })

  // O óculos que aparece na mesma rede é escolhido sozinho, uma vez ("Encontrado na rede").
  useEffect(() => {
    if (!snapshot || snapshot.status !== 'configured' || snapshot.device || autoTried.current) return
    const found = snapshot.nearby[0]
    if (!found) return
    autoTried.current = true
    prepareDevice({ device_id: found.id }, { onError: (err) => setActionError(sentence(err.message)) })
  }, [snapshot, prepareDevice])

  // Iniciada em outra aba: vai para o controle.
  useEffect(() => {
    if (snapshot?.status === 'running') navigate(controlSessionPath(session.id), { replace: true })
  }, [snapshot?.status, session.id, navigate])

  function connectByCode(event: FormEvent) {
    event.preventDefault()
    const value = code.trim()
    if (!/^\d{4}$/.test(value)) {
      setCodeError('Digite os 4 números do código que aparece no app do óculos.')
      return
    }
    setCodeError(null)
    prepare.mutate(
      { pairing_code: value },
      {
        onSuccess: () => setCode(''),
        onError: (err) => setCodeError(sentence(err.message)),
      },
    )
  }

  if (!snapshot) {
    return (
      <>
        <PageHeader title={TITLE} subtitle={subtitle(session)} back={BACK} />
        {error ? <FormAlert>{sentence(error.message)}</FormAlert> : <Spinner size={28} label="Procurando o óculos" />}
      </>
    )
  }

  const device = snapshot.device
  const online = Boolean(device?.online)
  const { loaded, total } = snapshot.load
  const loadedAll = total > 0 && loaded >= total
  const eye = device?.tracking.eye
  const face = device?.tracking.face
  const failed = snapshot.load.error
  const failedName = failed ? session.items.find((i) => i.stimulus_id === failed.stimulus_id)?.name : null

  let footer: string
  if (!device) footer = 'Abra o app NeuroSight no óculos, na mesma rede deste computador, ou digite o código que aparece no app.'
  else if (!online) footer = 'O óculos desconectou. Confira se o app está aberto e conectado à rede.'
  else if (failed) footer = 'Um estímulo não carregou no óculos. Tente carregar de novo.'
  else if (!loadedAll) footer = 'Aguarde o óculos carregar os estímulos.'
  else if (eye !== 'active') footer = 'Ative o eye tracking no óculos para iniciar a sessão.'
  else if (!onPatient) footer = 'Marque que o óculos está no paciente para iniciar.'
  else if (face !== 'active') footer = 'Tudo pronto, mas sem as expressões faciais (emotion tracking inativo). Ao iniciar, a coleta começa e você escolhe o primeiro estímulo.'
  else footer = 'Tudo pronto. Ao iniciar, a coleta começa e você escolhe o primeiro estímulo.'
  const ready = online && !failed && loadedAll && eye === 'active' && onPatient

  let deviceStatus: string
  if (!device) deviceStatus = 'Nenhum óculos nesta rede ainda'
  else if (!online) deviceStatus = 'Desconectado. Aguardando o app voltar'
  else if (device.paired_by === 'code') deviceStatus = 'Pareado pelo código'
  else deviceStatus = 'Encontrado na rede'

  return (
    <div className={styles.page}>
      <PageHeader title={TITLE} subtitle={subtitle(session)} back={BACK} />

      <div className={styles.grid}>
        <Card title="Antes de começar" padding="lg" className={styles.checklistCard}>
          <ul className={styles.checklist}>
            <CheckItem
              done={Boolean(device && online)}
              title="Óculos e computador na mesma rede"
              description={
                !device
                  ? 'Procurando o óculos na rede deste computador.'
                  : device.same_network
                    ? 'Detectado automaticamente.'
                    : 'Conectado pelo código de pareamento.'
              }
            />
            <CheckItem
              done={online}
              title="App aberto no óculos"
              description={
                !device
                  ? 'Abra o app NeuroSight no óculos.'
                  : online
                    ? 'O óculos está na tela inicial do aplicativo.'
                    : 'O app do óculos não está respondendo.'
              }
            />
            <li className={styles.manual}>
              <Checkbox
                strong
                label="O óculos está no paciente"
                description="Marque depois de ajustar o óculos no rosto do paciente."
                checked={onPatient}
                onChange={(event) => setOnPatient(event.target.checked)}
                className={styles.checkbox}
              />
            </li>
          </ul>
        </Card>

        <Card padding="lg" aria-label="Óculos" className={styles.deviceCard}>
          <div className={styles.deviceHeader}>
            <span className={styles.deviceIcon}>
              <RectangleGoggles size={26} strokeWidth={1.8} aria-hidden />
            </span>
            <div className={styles.deviceName}>
              <strong>{device?.name ?? 'Procurando o óculos'}</strong>
              <span>{deviceStatus}</span>
            </div>
            {device && (
              <Badge tone={online ? 'success' : 'neutral'} className={styles.deviceBadge}>
                {online ? 'Conectado' : 'Desconectado'}
              </Badge>
            )}
          </div>
          <dl className={styles.deviceRows}>
            <TrackingRow label="Eye tracking" state={device && online ? eye : undefined} required />
            <TrackingRow label="Emotion tracking" state={device && online ? face : undefined} />
            <div>
              <dt>Gravação</dt>
              <dd className={styles.strong}>{session.record ? 'Será gravada' : 'Não será gravada'}</dd>
            </div>
          </dl>
          <form className={styles.code} onSubmit={connectByCode} noValidate>
            <label htmlFor="pairing-code" className={styles.codeLabel}>
              {device ? 'Não é este o óculos? Digite o código que aparece no app.' : 'O óculos está em outra rede? Digite o código que aparece no app.'}
            </label>
            <div className={styles.codeRow}>
              <TextField
                id="pairing-code"
                size="sm"
                inputMode="numeric"
                autoComplete="off"
                maxLength={4}
                placeholder="Ex.: 4827"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
                error={codeError ?? undefined}
                fieldClassName={styles.codeField}
              />
              <Button type="submit" variant="secondary" size="sm" loading={prepare.isPending && Boolean(code)}>
                Conectar
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <Card padding="lg" aria-label="Estímulos no óculos" className={styles.loadCard}>
        <div className={styles.loadHeader}>
          <h2>Estímulos no óculos</h2>
          {device && (
            <span className={cx(styles.loadCount, loadedAll && styles.loadDone)}>
              {loaded} de {total} carregados
            </span>
          )}
        </div>
        <ProgressBar
          value={device && total ? loaded / total : 0}
          tone={loadedAll ? 'success' : 'primary'}
          size="md"
          label="Estímulos carregados no óculos"
        />
        {failed && (
          <p className={styles.loadError} role="alert">
            Não foi possível carregar {failedName ? `“${failedName}”` : 'um estímulo'} no óculos ({failed.message}).{' '}
            <Button
              variant="text"
              onClick={() => device && prepare.mutate({ device_id: device.id }, { onError: (err) => setActionError(sentence(err.message)) })}
            >
              Tentar de novo
            </Button>
          </p>
        )}
      </Card>

      {actionError && <FormAlert className={styles.alert}>{actionError}</FormAlert>}

      <div className={styles.spacer} />
      <footer className={styles.footer}>
        <p aria-live="polite">{footer}</p>
        <div className={styles.footerActions}>
          <Button variant="secondary" onClick={() => release.mutate()} loading={release.isPending}>
            Cancelar
          </Button>
          <Button icon={Play} className={styles.start} disabled={!ready} loading={start.isPending} onClick={() => start.mutate()}>
            Iniciar sessão
          </Button>
        </div>
      </footer>
    </div>
  )
}

function CheckItem({ done, title, description }: { done: boolean; title: string; description: ReactNode }) {
  return (
    <li className={styles.item}>
      {done ? (
        <CheckCircleFilled size={24} className={styles.done} />
      ) : (
        <Circle size={24} strokeWidth={1.6} className={styles.pending} aria-hidden />
      )}
      <div>
        <p className={styles.itemTitle}>
          {title}
          <span className="sr-only">{done ? ' (pronto)' : ' (pendente)'}</span>
        </p>
        <p className={styles.itemDescription}>{description}</p>
      </div>
    </li>
  )
}

function TrackingRow({ label, state, required = false }: { label: string; state?: TrackingState; required?: boolean }) {
  const tone = state === undefined ? styles.unknown : state === 'active' ? styles.ok : required ? styles.bad : styles.warn
  return (
    <div>
      <dt>{label}</dt>
      <dd className={cx(styles.strong, tone)}>{state === undefined ? '—' : trackingLabel(state)}</dd>
    </div>
  )
}
