import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../../api/client'
import { patientsApi, patientsKeys } from '../../../api/patients'
import type { Sex } from '../../../api/patients'
import { prepareSessionPath, sessionsApi, sessionsKeys } from '../../../api/sessions'
import { stimuliKeys } from '../../../api/stimuli'
import Button from '../../../components/Button/Button'
import Card from '../../../components/Card/Card'
import FormAlert from '../../../components/FormAlert/FormAlert'
import StimulusThumbnail from '../../../components/StimulusThumbnail/StimulusThumbnail'
import TextLink from '../../../components/TextLink/TextLink'
import { useToast } from '../../../components/Toast/toastContext'
import { formatDate, sentence } from '../../../lib/format'
import { reviewSummary } from '../sequence'
import WizardFooter from './WizardFooter'
import { entries, toInput } from './wizardState'
import type { WizardState } from './wizardState'
import styles from './ReviewStep.module.css'

// Miniaturas à mostra na revisão; o resto vira "+N".
const THUMBS = 8

function bornText(sex: Sex | undefined, birthDate: string): string {
  const word = sex === 'female' ? 'Nascida em' : sex === 'male' ? 'Nascido em' : 'Nascimento em'
  return `${word} ${formatDate(birthDate)}`
}

interface ReviewStepProps {
  state: WizardState
  // Volta para a etapa (0 a 2) do bloco escolhido.
  onEdit: (step: number) => void
  onBack: () => void
}

// Etapa 4 da W13: revisão por bloco, com Editar; Salvar ou Salvar e preparar.
export default function ReviewStep({ state, onEdit, onBack }: ReviewStepProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [saving, setSaving] = useState<'save' | 'prepare' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const patient = state.patient!
  // O sexo (para "Nascida em") vem do cadastro completo.
  const detail = useQuery({
    queryKey: patientsKeys.detail(patient.id),
    queryFn: ({ signal }) => patientsApi.get(patient.id, signal),
  })
  const extra = state.items.length - THUMBS

  async function save(then: 'save' | 'prepare') {
    setSaving(then)
    setError(null)
    try {
      const session = await sessionsApi.create(toInput(state))
      queryClient.invalidateQueries({ queryKey: sessionsKeys.all })
      queryClient.invalidateQueries({ queryKey: patientsKeys.all })
      queryClient.invalidateQueries({ queryKey: stimuliKeys.all })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      toast.success('Sessão salva com o status Configurada.')
      navigate(then === 'prepare' ? prepareSessionPath(session.id) : `/sessoes/${session.id}`)
    } catch (e) {
      setError(e instanceof ApiError ? sentence(e.message) : 'Não foi possível salvar a sessão.')
      setSaving(null)
    }
  }

  return (
    <>
      <Card padding="none" className={styles.card}>
        <section className={styles.block} aria-labelledby="revisao-paciente">
          <h2 id="revisao-paciente" className={styles.blockTitle}>
            Paciente
          </h2>
          <div>
            <p className={styles.value}>
              {patient.code}, {patient.name}
            </p>
            <p className={styles.muted}>{bornText(detail.data?.sex, patient.birth_date)}</p>
          </div>
          <TextLink onClick={() => onEdit(0)} aria-label="Editar o paciente">
            Editar
          </TextLink>
        </section>

        <section className={styles.block} aria-labelledby="revisao-informacoes">
          <h2 id="revisao-informacoes" className={styles.blockTitle}>
            Informações
          </h2>
          <dl className={styles.info}>
            <dt>Título</dt>
            <dd>{state.title}</dd>
            <dt>Objetivo</dt>
            <dd>{state.objective}</dd>
            {state.notes.trim() && (
              <>
                <dt>Observações</dt>
                <dd>{state.notes.trim()}</dd>
              </>
            )}
            <dt>Gravação</dt>
            <dd>{state.record ? 'Sim, a sessão será gravada' : 'Não, a sessão não será gravada'}</dd>
          </dl>
          <TextLink onClick={() => onEdit(1)} aria-label="Editar as informações">
            Editar
          </TextLink>
        </section>

        <section className={styles.block} aria-labelledby="revisao-estimulos">
          <h2 id="revisao-estimulos" className={styles.blockTitle}>
            Estímulos
          </h2>
          <div>
            <p className={styles.value}>{reviewSummary(entries(state.items))}</p>
            <ul className={styles.thumbs} aria-label="Sequência">
              {state.items.slice(0, THUMBS).map((item, index) => (
                <li key={item.stimulus_id} title={`${index + 1}. ${item.name}`}>
                  <StimulusThumbnail src={item.thumbnail_url} kind={item.kind} className={styles.thumb} />
                  <span className="sr-only">
                    {index + 1}. {item.name}
                  </span>
                </li>
              ))}
              {extra > 0 && (
                <li className={styles.extra}>
                  +{extra}
                  <span className="sr-only"> {extra === 1 ? 'estímulo' : 'estímulos'}</span>
                </li>
              )}
            </ul>
          </div>
          <TextLink onClick={() => onEdit(2)} aria-label="Editar os estímulos">
            Editar
          </TextLink>
        </section>

        <p className={styles.note}>
          A sessão fica com o status Configurada até ser executada. Você pode prepará-la agora ou depois, pela lista de sessões.
        </p>
      </Card>
      {error && <FormAlert className={styles.alert}>{error}</FormAlert>}
      <WizardFooter
        start={
          <Button variant="secondary" onClick={onBack} disabled={saving !== null}>
            Voltar
          </Button>
        }
        end={
          <>
            <Button variant="secondary" onClick={() => save('save')} loading={saving === 'save'} disabled={saving === 'prepare'}>
              Salvar
            </Button>
            <Button onClick={() => save('prepare')} loading={saving === 'prepare'} disabled={saving === 'save'}>
              Salvar e preparar
            </Button>
          </>
        }
      />
    </>
  )
}
