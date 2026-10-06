import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { patientsApi, patientsKeys } from '../../api/patients'
import { sessionsApi, sessionsKeys } from '../../api/sessions'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import Spinner from '../../components/Spinner/Spinner'
import Stepper from '../../components/Stepper/Stepper'
import { sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import InfoStep from './wizard/InfoStep'
import PatientStep from './wizard/PatientStep'
import ReviewStep from './wizard/ReviewStep'
import StimuliStep from './wizard/StimuliStep'
import { EMPTY_WIZARD, STEPS, fromSession } from './wizard/wizardState'
import type { WizardState } from './wizard/wizardState'
import styles from './NewSessionPage.module.css'

const BACK = { to: '/sessoes', label: 'Sessões' }

// W13: assistente de nova sessão. Com ?paciente=<id> (W06, W08) já abre nas Informações com o
// paciente escolhido; com ?duplicar=<id> (W16) traz as informações e a sequência da sessão copiada
// e pede o paciente novo.
export default function NewSessionPage() {
  usePageTitle('Nova sessão')
  const [params] = useSearchParams()
  const patientId = params.get('paciente')
  const sourceId = params.get('duplicar')

  const patient = useQuery({
    queryKey: patientsKeys.detail(patientId ?? ''),
    queryFn: ({ signal }) => patientsApi.get(patientId!, signal),
    enabled: Boolean(patientId),
  })
  const source = useQuery({
    queryKey: sessionsKeys.detail(sourceId ?? ''),
    queryFn: ({ signal }) => sessionsApi.get(sourceId!, signal),
    enabled: Boolean(sourceId),
  })

  if ((patientId && patient.isPending) || (sourceId && source.isPending)) {
    return (
      <>
        <PageHeader title="Nova sessão" back={BACK} />
        <Spinner size={28} label="Carregando" />
      </>
    )
  }
  if (sourceId && source.isError) {
    return (
      <>
        <PageHeader title="Nova sessão" back={BACK} />
        <FormAlert>{sentence(source.error.message)}</FormAlert>
      </>
    )
  }

  let initial: WizardState = EMPTY_WIZARD
  let skipped = 0
  if (source.data) ({ state: initial, skipped } = fromSession(source.data))
  // O paciente da URL só vale se ainda estiver ativo; senão a pessoa escolhe outro na etapa 1.
  const chosen = patient.data?.status === 'active' ? patient.data : null
  if (chosen) {
    initial = {
      ...initial,
      patient: { id: chosen.id, code: chosen.code, name: chosen.name, birth_date: chosen.birth_date, sessions_count: chosen.sessions_count },
    }
  }
  return <Wizard key={`${patientId}:${sourceId}`} initial={initial} startAt={chosen ? 1 : 0} skippedArchived={skipped} />
}

function Wizard({ initial, startAt, skippedArchived }: { initial: WizardState; startAt: number; skippedArchived: number }) {
  const [state, setState] = useState(initial)
  const [step, setStep] = useState(startAt)
  const headingRef = useRef<HTMLDivElement>(null)
  const firstRender = useRef(true)

  // Cada etapa começa do topo, com o foco no conteúdo novo (para quem usa teclado ou leitor de tela).
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    window.scrollTo({ top: 0 })
    headingRef.current?.focus()
  }, [step])

  function update(changes: Partial<WizardState>) {
    setState((current) => ({ ...current, ...changes }))
  }

  let notice: string | null = null
  if (state.duplicatedFrom) {
    notice = `Copiando “${state.duplicatedFrom.title}” (paciente ${state.duplicatedFrom.patientCode}). Escolha o paciente da nova sessão.`
    if (skippedArchived > 0) {
      notice += ` ${skippedArchived === 1 ? 'Um estímulo arquivado ficou' : `${skippedArchived} estímulos arquivados ficaram`} de fora da sequência.`
    }
  }

  return (
    <>
      <PageHeader title="Nova sessão" back={BACK} />
      <Stepper steps={STEPS} current={step} className={styles.stepper} />
      <div ref={headingRef} tabIndex={-1} className={styles.step} aria-label={`Etapa ${step + 1} de ${STEPS.length}: ${STEPS[step]}`}>
        {step === 0 && (
          <PatientStep
            selected={state.patient}
            notice={notice}
            onSelect={(patient) => update({ patient })}
            onContinue={() => setStep(1)}
          />
        )}
        {step === 1 && (
          <InfoStep
            state={state}
            onChange={update}
            onChangePatient={() => setStep(0)}
            onBack={() => setStep(0)}
            onContinue={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <StimuliStep items={state.items} onChange={(items) => update({ items })} onBack={() => setStep(1)} onContinue={() => setStep(3)} />
        )}
        {step === 3 && <ReviewStep state={state} onEdit={setStep} onBack={() => setStep(2)} />}
      </div>
    </>
  )
}
