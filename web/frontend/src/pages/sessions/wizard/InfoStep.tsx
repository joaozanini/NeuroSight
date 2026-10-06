import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Button from '../../../components/Button/Button'
import Card from '../../../components/Card/Card'
import Checkbox from '../../../components/Checkbox/Checkbox'
import TextField from '../../../components/TextField/TextField'
import Textarea from '../../../components/Textarea/Textarea'
import TextLink from '../../../components/TextLink/TextLink'
import WizardFooter from './WizardFooter'
import type { WizardState } from './wizardState'
import shared from './Wizard.module.css'
import styles from './InfoStep.module.css'

export const infoSchema = z.object({
  title: z.string().trim().min(1, 'Informe o título da sessão.').max(120, 'Use no máximo 120 caracteres.'),
  objective: z.string().trim().min(1, 'Descreva o objetivo da sessão.').max(2000, 'Use no máximo 2.000 caracteres.'),
  notes: z.string().max(2000, 'Use no máximo 2.000 caracteres.'),
  record: z.boolean(),
})

export type InfoValues = z.infer<typeof infoSchema>

interface InfoStepProps {
  state: WizardState
  onChange: (changes: Partial<WizardState>) => void
  onChangePatient: () => void
  onBack: () => void
  onContinue: () => void
}

// Etapa 2 da W13: título, objetivo, observações e "Gravar a sessão".
export default function InfoStep({ state, onChange, onChangePatient, onBack, onContinue }: InfoStepProps) {
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<InfoValues>({
    resolver: zodResolver(infoSchema),
    defaultValues: { title: state.title, objective: state.objective, notes: state.notes, record: state.record },
  })

  // Voltar ou trocar o paciente guardam o que já foi digitado, mesmo incompleto.
  function keep(then: () => void) {
    onChange(getValues())
    then()
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => {
        onChange(values)
        onContinue()
      })}
    >
      <Card padding="none" className={shared.card}>
        <h2 className={shared.heading}>Informações da sessão</h2>
        <p className={shared.lead}>Descreva o experimento para quem for consultar os dados depois.</p>
        <div className={styles.fields}>
          {state.patient && (
            <p className={styles.patient}>
              <span>
                <strong>Paciente:</strong> {state.patient.code}, {state.patient.name}
              </span>
              <TextLink onClick={() => keep(onChangePatient)}>Trocar</TextLink>
            </p>
          )}
          <TextField label="Título" autoComplete="off" error={errors.title?.message} {...register('title')} />
          <Textarea label="Objetivo" rows={3} error={errors.objective?.message} {...register('objective')} />
          <Textarea label="Observações" rows={2} placeholder="Opcional" error={errors.notes?.message} {...register('notes')} />
          <Checkbox
            strong
            label="Gravar a sessão"
            description="A gravação mostra o que o paciente viu no óculos e fica junto com os dados de rastreamento."
            {...register('record')}
          />
        </div>
      </Card>
      <WizardFooter
        start={
          <Button variant="secondary" onClick={() => keep(onBack)}>
            Voltar
          </Button>
        }
        end={<Button type="submit">Continuar</Button>}
      />
    </form>
  )
}
