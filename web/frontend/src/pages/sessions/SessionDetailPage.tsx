import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ChartLine } from 'lucide-react'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { ApiError } from '../../api/client'
import { controlSessionPath, prepareSessionPath, sessionsApi, sessionsKeys } from '../../api/sessions'
import type { SequenceItem, SessionDetail } from '../../api/sessions'
import { KIND_LABELS } from '../../api/stimuli'
import Badge from '../../components/Badge/Badge'
import StatusBadge from '../../components/Badge/StatusBadge'
import Button from '../../components/Button/Button'
import LinkButton from '../../components/Button/LinkButton'
import Card from '../../components/Card/Card'
import Checkbox from '../../components/Checkbox/Checkbox'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import Spinner from '../../components/Spinner/Spinner'
import StimulusThumbnail from '../../components/StimulusThumbnail/StimulusThumbnail'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextField from '../../components/TextField/TextField'
import TextLink from '../../components/TextLink/TextLink'
import Textarea from '../../components/Textarea/Textarea'
import { useToast } from '../../components/Toast/toastContext'
import { formatDateTime, formatDuration, formatNumber, sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import { screenTimeText, sequenceHeadline } from './sequence'
import VisibilityLabel from './VisibilityLabel'
import VisibilityModal from './VisibilityModal'
import { infoSchema } from './wizard/InfoStep'
import type { InfoValues } from './wizard/InfoStep'
import styles from './SessionDetailPage.module.css'

const BACK = { to: '/sessoes', label: 'Sessões' }

// W16 (cabeçalho, resumo, informações e a sequência) e o modal de visibilidade (W18). Os estímulos
// exibidos, as marcações e os arquivos chegam com os dados coletados (Fase 5).
export default function SessionDetailPage() {
  const { sessionId = '' } = useParams()
  const session = useQuery({
    queryKey: sessionsKeys.detail(sessionId),
    queryFn: ({ signal }) => sessionsApi.get(sessionId, signal),
  })
  usePageTitle(session.data?.title ?? 'Sessão')

  if (session.isPending) {
    return (
      <>
        <PageHeader title="Sessão" back={BACK} />
        <Spinner size={28} label="Carregando a sessão" />
      </>
    )
  }
  if (session.isError) {
    return (
      <>
        <PageHeader title="Sessão" back={BACK} />
        <FormAlert>{sentence(session.error.message)}</FormAlert>
      </>
    )
  }
  return <SessionView session={session.data} />
}

function SessionView({ session }: { session: SessionDetail }) {
  const me = useCurrentUser()
  const [visibilityOpen, setVisibilityOpen] = useState(false)
  const executed = session.started_at !== null
  const canDuplicate = hasPermission(me, 'sessions.run')
  const patient = session.patient.name ? `Paciente ${session.patient.code}, ${session.patient.name}` : `Paciente ${session.patient.code}`

  let primary = null
  if (session.status === 'configured' && session.can_run) {
    primary = <LinkButton to={prepareSessionPath(session.id)}>Preparar sessão</LinkButton>
  } else if (session.status === 'running' && session.can_run) {
    primary = <LinkButton to={controlSessionPath(session.id)}>Abrir controle</LinkButton>
  } else if (session.status === 'completed' || session.status === 'interrupted') {
    primary = (
      <LinkButton to={`/sessoes/${session.id}/analise`} icon={ChartLine}>
        Analisar dados
      </LinkButton>
    )
  }

  return (
    <>
      <PageHeader
        title={session.title}
        badge={<StatusBadge kind="session" status={session.status} />}
        subtitle={patient}
        back={BACK}
        actions={
          (canDuplicate || session.can_change_visibility || primary) && (
            <>
              {canDuplicate && (
                <LinkButton variant="secondary" to={`/sessoes/nova?duplicar=${encodeURIComponent(session.id)}`}>
                  Duplicar para outro paciente
                </LinkButton>
              )}
              {session.can_change_visibility && (
                <Button variant="secondary" onClick={() => setVisibilityOpen(true)}>
                  Alterar visibilidade
                </Button>
              )}
              {primary}
            </>
          )
        }
      />

      <Card as="section" aria-label="Resumo" className={styles.summary}>
        <dl className={styles.summaryList}>
          <div>
            <dt>Responsável</dt>
            <dd>{session.owner.name}</dd>
          </div>
          <div>
            <dt>{executed ? 'Data e hora' : 'Configurada em'}</dt>
            <dd>{formatDateTime(session.date)}</dd>
          </div>
          <div>
            <dt>Duração</dt>
            <dd>{session.duration_seconds != null ? formatDuration(session.duration_seconds) : '—'}</dd>
          </div>
          <div>
            <dt>Estímulos</dt>
            <dd>{formatNumber(session.items.length)} na sequência</dd>
          </div>
          <div>
            <dt>Gravação</dt>
            <dd>{session.record ? 'Sim' : 'Não'}</dd>
          </div>
          <div>
            <dt>Visibilidade</dt>
            <dd>
              <VisibilityLabel visibility={session.visibility} />
            </dd>
          </div>
        </dl>
      </Card>

      <Information session={session} />
      <Sequence session={session} />

      <VisibilityModal session={session} open={visibilityOpen} onClose={() => setVisibilityOpen(false)} />
    </>
  )
}

function Information({ session }: { session: SessionDetail }) {
  const [editing, setEditing] = useState(false)
  return (
    <Card
      title="Informações"
      className={styles.info}
      actions={
        session.can_edit &&
        !editing && (
          <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
            Editar informações
          </Button>
        )
      }
    >
      {editing ? (
        <InformationForm session={session} onDone={() => setEditing(false)} />
      ) : (
        <dl className={styles.infoList}>
          <dt>Objetivo</dt>
          <dd>{session.objective}</dd>
          <dt>Observações</dt>
          <dd className={session.notes ? undefined : styles.muted}>{session.notes ?? 'Nenhuma observação.'}</dd>
          {session.duplicated_from && (
            <>
              <dt>Origem</dt>
              <dd>
                Duplicada de <TextLink to={`/sessoes/${session.duplicated_from.id}`}>{session.duplicated_from.title}</TextLink>
              </dd>
            </>
          )}
        </dl>
      )}
      <p className={styles.infoNote}>
        Os dados coletados não podem ser alterados. Qualquer mudança nas informações fica registrada na auditoria.
      </p>
    </Card>
  )
}

function InformationForm({ session, onDone }: { session: SessionDetail; onDone: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [formError, setFormError] = useState<string | null>(null)
  const configured = session.status === 'configured'
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<InfoValues>({
    resolver: zodResolver(infoSchema),
    defaultValues: { title: session.title, objective: session.objective, notes: session.notes ?? '', record: session.record },
  })

  async function onSubmit(values: InfoValues) {
    setFormError(null)
    try {
      const updated = await sessionsApi.update(session.id, {
        title: values.title.trim(),
        objective: values.objective.trim(),
        notes: values.notes.trim(),
        ...(configured ? { record: values.record } : {}),
      })
      queryClient.setQueryData(sessionsKeys.detail(updated.id), updated)
      queryClient.invalidateQueries({ queryKey: sessionsKeys.lists })
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      toast.success('Alterações salvas.')
      onDone()
    } catch (error) {
      setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar.')
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      <TextField label="Título" autoComplete="off" error={errors.title?.message} {...register('title')} />
      <Textarea label="Objetivo" rows={3} error={errors.objective?.message} {...register('objective')} />
      <Textarea label="Observações" rows={2} placeholder="Opcional" error={errors.notes?.message} {...register('notes')} />
      {configured && (
        <Checkbox
          strong
          label="Gravar a sessão"
          description="A gravação mostra o que o paciente viu no óculos e fica junto com os dados de rastreamento."
          {...register('record')}
        />
      )}
      {formError && <FormAlert>{formError}</FormAlert>}
      <div className={styles.formButtons}>
        <Button variant="secondary" size="sm" onClick={onDone} disabled={isSubmitting}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" loading={isSubmitting}>
          Salvar alterações
        </Button>
      </div>
    </form>
  )
}

const SEQUENCE_COLUMNS: Column<SequenceItem>[] = [
  { key: 'position', header: 'Nº', width: '64px', align: 'center', render: (i) => i.position },
  {
    key: 'stimulus',
    header: 'Estímulo',
    render: (i) => (
      <span className={styles.stimulus}>
        <StimulusThumbnail src={i.thumbnail_url} kind={i.kind} muted={i.archived} className={styles.thumb} />
        <TextLink to={`/estimulos/${i.stimulus_id}`} underline={false} className={styles.stimulusName}>
          {i.name}
        </TextLink>
        {i.archived && (
          <Badge tone="neutral" size="sm">
            Arquivado
          </Badge>
        )}
      </span>
    ),
  },
  { key: 'kind', header: 'Tipo', width: '16%', render: (i) => KIND_LABELS[i.kind] },
  { key: 'time', header: 'Tempo de tela', width: '24%', align: 'right', render: (i) => screenTimeText(i) },
]

function Sequence({ session }: { session: SessionDetail }) {
  return (
    <section className={styles.sequence} aria-labelledby="sequencia">
      <div className={styles.sequenceHeader}>
        <h2 id="sequencia" className={styles.heading}>
          Sequência da sessão
        </h2>
        <span className={styles.total}>{sequenceHeadline(session.items)}</span>
      </div>
      <Table caption="Sequência da sessão" columns={SEQUENCE_COLUMNS} rows={session.items} rowKey={(i) => i.position} />
    </section>
  )
}
