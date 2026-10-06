import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { ApiError } from '../../api/client'
import { KIND_LABELS, stimuliApi, stimuliKeys } from '../../api/stimuli'
import type { StimulusDetail, StimulusStatus } from '../../api/stimuli'
import Badge from '../../components/Badge/Badge'
import Button from '../../components/Button/Button'
import Card from '../../components/Card/Card'
import DangerZone from '../../components/DangerZone/DangerZone'
import FormAlert from '../../components/FormAlert/FormAlert'
import Modal from '../../components/Modal/Modal'
import PageHeader from '../../components/PageHeader/PageHeader'
import Spinner from '../../components/Spinner/Spinner'
import Tag from '../../components/Tag/Tag'
import TagInput from '../../components/TagInput/TagInput'
import TextField from '../../components/TextField/TextField'
import Textarea from '../../components/Textarea/Textarea'
import { useToast } from '../../components/Toast/toastContext'
import { formatBytes, formatDate, formatMediaDuration, plural, sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import styles from './StimulusDetailPage.module.css'

const BACK = { to: '/estimulos', label: 'Estímulos' }

const schema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do estímulo.').max(120, 'Use no máximo 120 caracteres.'),
  description: z.string().max(1000, 'Use no máximo 1.000 caracteres.'),
  tags: z.array(z.string()).max(20, 'Use no máximo 20 etiquetas.'),
})

type InfoValues = z.infer<typeof schema>

const normalizeTag = (text: string) => text.trim().replace(/\s+/g, ' ').toLocaleLowerCase('pt-BR')

// W11: prévia, ficha do arquivo, nome, descrição e etiquetas, onde foi usado e o arquivamento.
export default function StimulusDetailPage() {
  const { stimulusId = '' } = useParams()
  const stimulus = useQuery({
    queryKey: stimuliKeys.detail(stimulusId),
    queryFn: ({ signal }) => stimuliApi.get(stimulusId, signal),
  })
  usePageTitle(stimulus.data?.name ?? 'Estímulo')

  if (stimulus.isPending) {
    return (
      <>
        <PageHeader title="Estímulo" back={BACK} />
        <Spinner size={28} label="Carregando o estímulo" />
      </>
    )
  }
  if (stimulus.isError) {
    return (
      <>
        <PageHeader title="Estímulo" back={BACK} />
        <FormAlert>{sentence(stimulus.error.message)}</FormAlert>
      </>
    )
  }
  return <StimulusView key={stimulus.data.id} stimulus={stimulus.data} />
}

function StimulusView({ stimulus }: { stimulus: StimulusDetail }) {
  const me = useCurrentUser()
  const canEdit = hasPermission(me, 'stimuli.edit')
  const canArchive = hasPermission(me, 'stimuli.archive')
  const archived = stimulus.status === 'archived'
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)

  function refresh(updated?: StimulusDetail) {
    if (updated) queryClient.setQueryData(stimuliKeys.detail(updated.id), updated)
    queryClient.invalidateQueries({ queryKey: stimuliKeys.lists })
    queryClient.invalidateQueries({ queryKey: stimuliKeys.allTags })
    queryClient.invalidateQueries({ queryKey: ['audit'] })
  }

  const showError = (fallback: string) => (error: unknown) =>
    toast.error(error instanceof ApiError ? sentence(error.message) : fallback)

  const setStatus = useMutation({
    mutationFn: (status: StimulusStatus) => stimuliApi.setStatus(stimulus.id, status),
    onSuccess: (updated) => {
      refresh(updated)
      toast.success(updated.status === 'archived' ? 'Estímulo arquivado. Ele saiu da biblioteca.' : 'Estímulo de volta à biblioteca.')
    },
    onError: showError('Não foi possível concluir a ação.'),
  })

  const remove = useMutation({
    mutationFn: () => stimuliApi.remove(stimulus.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: stimuliKeys.detail(stimulus.id) })
      refresh()
      toast.success('Estímulo excluído.')
      navigate('/estimulos', { replace: true })
    },
    onError: (error) => {
      setConfirmDelete(false)
      showError('Não foi possível excluir o estímulo.')(error)
    },
  })

  const facts: [string, string][] = [
    ['Formato', stimulus.format.toUpperCase()],
    ['Resolução', `${stimulus.width} × ${stimulus.height}`],
    ['Tamanho', formatBytes(stimulus.size_bytes)],
    ['Enviado por', stimulus.created_by_name ?? 'Sistema'],
    ['Enviado em', formatDate(stimulus.created_at)],
  ]
  if (stimulus.kind === 'video' && stimulus.duration_seconds != null) facts.push(['Duração', formatMediaDuration(stimulus.duration_seconds)])

  return (
    <>
      <PageHeader
        title={stimulus.name}
        badge={
          <>
            <Tag shape="rounded" size="md">
              {KIND_LABELS[stimulus.kind]}
            </Tag>
            {archived && <Badge tone="neutral">Arquivado</Badge>}
          </>
        }
        back={BACK}
      />
      <div className={styles.layout}>
        <div className={styles.main}>
          <div className={styles.preview}>
            {stimulus.kind === 'video' ? (
              <video src={stimulus.file_url} poster={stimulus.thumbnail_url} controls preload="metadata" aria-label={`Prévia de ${stimulus.name}`} />
            ) : (
              <img src={stimulus.file_url} alt={`Prévia de ${stimulus.name}`} />
            )}
          </div>
          <dl className={styles.facts}>
            {facts.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          {stimulus.device_status === 'failed' && (
            <FormAlert className={styles.deviceAlert}>
              Não foi possível preparar a versão para o óculos{stimulus.device_error ? ` (${stimulus.device_error})` : ''}. Envie o
              arquivo de novo como outro estímulo.
            </FormAlert>
          )}
        </div>

        <aside className={styles.side}>
          <InfoForm stimulus={stimulus} canEdit={canEdit} onSaved={refresh} />
          <UsedIn stimulus={stimulus} />
        </aside>
      </div>

      {canArchive && (
        <ArchiveZone
          stimulus={stimulus}
          busy={setStatus.isPending}
          onArchive={() => setStatus.mutate('archived')}
          onRestore={() => setStatus.mutate('active')}
          onDelete={() => setConfirmDelete(true)}
        />
      )}

      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        size="sm"
        title="Excluir estímulo?"
        dismissible={!remove.isPending}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setConfirmDelete(false)} disabled={remove.isPending}>
              Cancelar
            </Button>
            <Button variant="danger" size="sm" loading={remove.isPending} onClick={() => remove.mutate()}>
              Excluir estímulo
            </Button>
          </>
        }
      >
        <p className={styles.confirmText}>
          “{stimulus.name}” sai da biblioteca e o arquivo é apagado do servidor. Não dá para desfazer. A exclusão fica registrada na
          auditoria.
        </p>
      </Modal>
    </>
  )
}

function InfoForm({ stimulus, canEdit, onSaved }: { stimulus: StimulusDetail; canEdit: boolean; onSaved: (s: StimulusDetail) => void }) {
  const toast = useToast()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InfoValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: stimulus.name, description: stimulus.description ?? '', tags: stimulus.tags },
  })

  async function onSubmit(values: InfoValues) {
    setFormError(null)
    try {
      const updated = await stimuliApi.update(stimulus.id, {
        name: values.name.trim(),
        description: values.description.trim() || null,
        tags: values.tags,
      })
      reset({ name: updated.name, description: updated.description ?? '', tags: updated.tags })
      onSaved(updated)
      toast.success('Alterações salvas.')
    } catch (error) {
      setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar.')
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate aria-labelledby="informacoes">
      <h2 id="informacoes" className={styles.heading}>
        Informações
      </h2>
      <TextField label="Nome" autoComplete="off" disabled={!canEdit} error={errors.name?.message} {...register('name')} />
      <Textarea label="Descrição" rows={3} disabled={!canEdit} error={errors.description?.message} {...register('description')} />
      <Controller
        control={control}
        name="tags"
        render={({ field }) => (
          <TagInput
            label="Etiquetas"
            value={field.value}
            onChange={field.onChange}
            onBlur={field.onBlur}
            normalize={normalizeTag}
            disabled={!canEdit}
            error={errors.tags?.message}
          />
        )}
      />
      {formError && <FormAlert>{formError}</FormAlert>}
      {canEdit && (
        <Button type="submit" loading={isSubmitting} className={styles.save}>
          Salvar alterações
        </Button>
      )}
    </form>
  )
}

function UsedIn({ stimulus }: { stimulus: StimulusDetail }) {
  const count = stimulus.sessions_count
  // A contagem inclui as sessões que a pessoa não pode ver; a lista, não.
  const hidden = count - stimulus.sessions.length
  return (
    <section className={styles.used} aria-labelledby="usado-em">
      <h2 id="usado-em" className={styles.heading}>
        {count > 0 ? `Usado em ${plural(count, 'sessão', 'sessões')}` : 'Uso em sessões'}
      </h2>
      {count > 0 ? (
        <Card padding="none">
          <ul className={styles.sessions}>
            {stimulus.sessions.map((s) => (
              <li key={s.id}>
                <Link to={`/sessoes/${s.id}`} className={styles.sessionLink}>
                  {s.title}
                </Link>
                <span className={styles.sessionMeta}>
                  Paciente {s.patient_code}, {formatDate(s.date)}
                </span>
              </li>
            ))}
            {hidden > 0 && (
              <li className={styles.sessionMeta}>
                {hidden === 1 ? 'Mais 1 sessão de outro pesquisador.' : `Mais ${hidden} sessões de outros pesquisadores.`}
              </li>
            )}
          </ul>
        </Card>
      ) : (
        <p className={styles.unused}>Este estímulo ainda não foi usado em nenhuma sessão.</p>
      )}
    </section>
  )
}

interface ArchiveZoneProps {
  stimulus: StimulusDetail
  busy: boolean
  onArchive: () => void
  onRestore: () => void
  onDelete: () => void
}

// "Arquivar estímulo" da W11. O que nunca foi usado também pode ser excluído; o arquivado volta.
function ArchiveZone({ stimulus, busy, onArchive, onRestore, onDelete }: ArchiveZoneProps) {
  const deleteButton = stimulus.can_delete && (
    <Button variant="danger" size="sm" onClick={onDelete} disabled={busy}>
      Excluir estímulo
    </Button>
  )
  if (stimulus.status === 'archived') {
    return (
      <DangerZone
        tone="neutral"
        title="Estímulo arquivado"
        description="Ele não aparece na biblioteca e não entra em novas sessões. As sessões antigas continuam com os dados intactos."
        actions={
          <>
            {deleteButton}
            <Button variant="secondary" size="sm" onClick={onRestore} loading={busy}>
              Desarquivar estímulo
            </Button>
          </>
        }
      />
    )
  }
  return (
    <DangerZone
      title={stimulus.can_delete ? 'Arquivar ou excluir estímulo' : 'Arquivar estímulo'}
      description={
        stimulus.can_delete
          ? 'Como ainda não foi usado em sessões, este estímulo pode ser excluído de vez. Arquivado, ele sai da biblioteca e não entra em novas sessões, mas continua guardado.'
          : 'Como já foi usado em sessões, este estímulo não pode ser excluído. Arquivado, ele sai da biblioteca e não entra em novas sessões, mas as sessões antigas continuam com os dados intactos.'
      }
      actions={
        <>
          {deleteButton}
          <Button variant="danger" size="sm" onClick={onArchive} loading={busy}>
            Arquivar estímulo
          </Button>
        </>
      }
    />
  )
}
