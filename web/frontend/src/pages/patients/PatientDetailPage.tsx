import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { ApiError } from '../../api/client'
import { SEX_LABELS, VISION_LABELS, patientsApi, patientsKeys } from '../../api/patients'
import type { PatientDetail, PatientSession } from '../../api/patients'
import StatusBadge from '../../components/Badge/StatusBadge'
import LinkButton from '../../components/Button/LinkButton'
import Card from '../../components/Card/Card'
import DangerZone from '../../components/DangerZone/DangerZone'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import Spinner from '../../components/Spinner/Spinner'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import Tag from '../../components/Tag/Tag'
import TextLink from '../../components/TextLink/TextLink'
import { useToast } from '../../components/Toast/toastContext'
import { ageOn } from '../../lib/dates'
import { formatDate, formatNumber, plural, sentence } from '../../lib/format'
import type { PatientStatus } from '../../lib/status'
import { usePageTitle } from '../../lib/usePageTitle'
import { newSessionPath } from './patientPaths'
import styles from './PatientDetailPage.module.css'

const BACK = { to: '/pacientes', label: 'Pacientes' }

// "Cadastrada em 01/09/2026 por Ana Souza." (concorda com o sexo informado).
function registeredLine(patient: PatientDetail): string {
  const word = patient.sex === 'female' ? 'Cadastrada' : patient.sex === 'male' ? 'Cadastrado' : 'Cadastro feito'
  return `${word} em ${formatDate(patient.created_at)} por ${patient.created_by_name ?? 'Sistema'}.`
}

function ageText(birthDate: string): string {
  const age = ageOn(birthDate)
  return `${formatDate(birthDate)} (${age} ${age === 1 ? 'ano' : 'anos'})`
}

const SESSION_COLUMNS: Column<PatientSession>[] = [
  {
    key: 'title',
    header: 'Sessão',
    width: '32%',
    render: (s) => (
      <TextLink to={`/sessoes/${s.id}`} underline={false} className={styles.sessionLink}>
        {s.title}
      </TextLink>
    ),
  },
  { key: 'date', header: 'Data', width: '16%', render: (s) => formatDate(s.date) },
  { key: 'owner', header: 'Responsável', width: '20%', render: (s) => s.owner_name },
  { key: 'stimuli', header: 'Estímulos', width: '10%', align: 'right', render: (s) => formatNumber(s.stimuli_count) },
  { key: 'status', header: 'Status', className: styles.statusCell, render: (s) => <StatusBadge kind="session" status={s.status} /> },
]

// W08: dados do paciente, termo, histórico de sessões e inativação.
export default function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const patient = useQuery({
    queryKey: patientsKeys.detail(patientId),
    queryFn: ({ signal }) => patientsApi.get(patientId, signal),
  })
  usePageTitle(patient.data?.name ?? 'Paciente')

  if (patient.isPending) {
    return (
      <>
        <PageHeader title="Paciente" back={BACK} />
        <Spinner size={28} label="Carregando o paciente" />
      </>
    )
  }
  if (patient.isError) {
    return (
      <>
        <PageHeader title="Paciente" back={BACK} />
        <FormAlert>{sentence(patient.error.message)}</FormAlert>
      </>
    )
  }
  return <PatientView patient={patient.data} />
}

function PatientView({ patient }: { patient: PatientDetail }) {
  const me = useCurrentUser()
  const toast = useToast()
  const queryClient = useQueryClient()
  const active = patient.status === 'active'
  const canEdit = hasPermission(me, 'patients.edit')
  const canDeactivate = hasPermission(me, 'patients.deactivate')
  const canStartSession = hasPermission(me, 'sessions.run') && active

  const setStatus = useMutation({
    mutationFn: (status: PatientStatus) => patientsApi.setStatus(patient.id, status),
    onSuccess: (updated) => {
      queryClient.setQueryData(patientsKeys.detail(updated.id), updated)
      queryClient.invalidateQueries({ queryKey: patientsKeys.lists })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      if (updated.status === 'inactive') toast.success(`${updated.code} inativado. O cadastro saiu das listas.`)
      else toast.success(`${updated.code} reativado.`)
    },
    onError: (error) => toast.error(error instanceof ApiError ? sentence(error.message) : 'Não foi possível concluir a ação.'),
  })

  let consent = <dd>Não assinado</dd>
  if (patient.consent_signed) {
    consent = (
      <dd>
        {patient.consent_date ? `Assinado em ${formatDate(patient.consent_date)}` : 'Assinado'}
        {patient.consent_file ? (
          <TextLink href={patientsApi.consentUrl(patient.id)} target="_blank" rel="noopener" className={styles.consentLink}>
            Ver termo (PDF)
          </TextLink>
        ) : (
          <span className={styles.noFile}>PDF não anexado</span>
        )}
      </dd>
    )
  }

  return (
    <>
      <PageHeader
        title={patient.name}
        badge={
          <Tag shape="rounded" size="md">
            {patient.code}
          </Tag>
        }
        subtitle={registeredLine(patient)}
        back={BACK}
        actions={
          (canEdit || canStartSession) && (
            <>
              {canEdit && (
                <LinkButton variant="secondary" to={`/pacientes/${patient.id}/editar`}>
                  Editar
                </LinkButton>
              )}
              {canStartSession && (
                <LinkButton to={newSessionPath(patient.id)} icon={Plus}>
                  Nova sessão
                </LinkButton>
              )}
            </>
          )
        }
      />

      <section className={styles.section} aria-labelledby="dados">
        <h2 id="dados" className={styles.heading}>
          Dados do paciente
        </h2>
        <Card>
          <dl className={styles.data}>
            <div>
              <dt>Data de nascimento</dt>
              <dd>{ageText(patient.birth_date)}</dd>
            </div>
            <div>
              <dt>Sexo</dt>
              <dd>{SEX_LABELS[patient.sex]}</dd>
            </div>
            <div>
              <dt>Óculos ou lentes</dt>
              <dd>{VISION_LABELS[patient.vision_correction]}</dd>
            </div>
            <div>
              <dt>Termo de consentimento</dt>
              {consent}
            </div>
            <div>
              <dt>Situação</dt>
              <dd>
                <StatusBadge kind="patient" status={patient.status} />
              </dd>
            </div>
          </dl>
          <dl className={styles.notes}>
            <dt>Observações</dt>
            <dd className={patient.notes ? undefined : styles.empty}>{patient.notes ?? 'Nenhuma observação.'}</dd>
          </dl>
        </Card>
      </section>

      <section className={styles.section} aria-labelledby="historico">
        <div className={styles.headingRow}>
          <h2 id="historico" className={styles.heading}>
            Histórico de sessões
          </h2>
          <span className={styles.count}>{plural(patient.sessions_count, 'sessão', 'sessões')}</span>
        </div>
        <Table
          caption={`Sessões de ${patient.code}`}
          columns={SESSION_COLUMNS}
          rows={patient.sessions}
          rowKey={(s) => s.id}
          empty="Nenhuma sessão com este paciente ainda."
        />
      </section>

      {canDeactivate &&
        (active ? (
          <DangerZone
            title="Inativar paciente"
            description="O cadastro sai das listas e não recebe novas sessões. As sessões e os dados coletados continuam guardados."
            actionLabel="Inativar paciente"
            loading={setStatus.isPending}
            onAction={() => setStatus.mutate('inactive')}
          />
        ) : (
          <DangerZone
            tone="neutral"
            title="Reativar paciente"
            description="O cadastro está inativo: não aparece nas listas e não recebe novas sessões. Reativado, ele volta a aparecer e pode receber sessões."
            actionLabel="Reativar paciente"
            loading={setStatus.isPending}
            onAction={() => setStatus.mutate('active')}
          />
        ))}
    </>
  )
}
