import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Controller, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { ApiError } from '../../api/client'
import { SEX_LABELS, VISION_LABELS, patientsApi, patientsKeys } from '../../api/patients'
import type { PatientDetail, PatientInput, Sex, VisionCorrection } from '../../api/patients'
import Button from '../../components/Button/Button'
import Checkbox from '../../components/Checkbox/Checkbox'
import DateField from '../../components/DateField/DateField'
import FileField from '../../components/Dropzone/FileField'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import RadioCard from '../../components/RadioCard/RadioCard'
import RadioCardGroup from '../../components/RadioCard/RadioCardGroup'
import Spinner from '../../components/Spinner/Spinner'
import TextField from '../../components/TextField/TextField'
import Textarea from '../../components/Textarea/Textarea'
import { useToast } from '../../components/Toast/toastContext'
import { isoToBr, parseBrDate, todayIso } from '../../lib/dates'
import { sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import styles from './PatientFormPage.module.css'

const SEXES = Object.keys(SEX_LABELS) as Sex[]
const VISIONS = Object.keys(VISION_LABELS) as VisionCorrection[]
const MAX_PDF_MB = 20
const CODE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/

function dateIssue(text: string, what: string): string | null {
  const iso = parseBrDate(text)
  if (!iso || iso < '1900-01-01') return 'Informe a data no formato dd/mm/aaaa.'
  if (iso > todayIso()) return `A data ${what} não pode ser no futuro.`
  return null
}

const schema = z
  .object({
    code: z
      .string()
      .trim()
      .min(1, 'Informe o código do participante.')
      .max(20, 'Use no máximo 20 caracteres.')
      .regex(CODE_PATTERN, 'Use letras, números e hífen (ex.: P-016).'),
    name: z.string().trim().min(1, 'Informe o nome completo.').max(120, 'Use no máximo 120 caracteres.'),
    birth_date: z.string(),
    sex: z.string().refine((v) => SEXES.includes(v as Sex), 'Escolha uma opção.'),
    vision_correction: z.string().refine((v) => VISIONS.includes(v as VisionCorrection), 'Escolha uma opção.'),
    consent_signed: z.boolean(),
    consent_date: z.string(),
    notes: z.string().max(2000, 'Use no máximo 2.000 caracteres.'),
  })
  .superRefine((values, ctx) => {
    const birth = values.birth_date ? dateIssue(values.birth_date, 'de nascimento') : 'Informe a data de nascimento.'
    if (birth) ctx.addIssue({ code: 'custom', path: ['birth_date'], message: birth })
    if (values.consent_signed) {
      const signed = values.consent_date ? dateIssue(values.consent_date, 'da assinatura') : 'Informe a data da assinatura.'
      if (signed) ctx.addIssue({ code: 'custom', path: ['consent_date'], message: signed })
    }
  })

type PatientValues = z.infer<typeof schema>

function toInput(values: PatientValues): PatientInput {
  return {
    code: values.code.trim().toUpperCase(),
    name: values.name.trim(),
    birth_date: parseBrDate(values.birth_date)!,
    sex: values.sex as Sex,
    vision_correction: values.vision_correction as VisionCorrection,
    consent_signed: values.consent_signed,
    consent_date: values.consent_signed ? parseBrDate(values.consent_date) : null,
    notes: values.notes.trim(),
  }
}

function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

// W07: novo paciente (com o código sugerido) e edição. O PDF do TCLE sobe junto com o formulário.
export default function PatientFormPage() {
  const { patientId } = useParams()
  usePageTitle(patientId ? 'Editar paciente' : 'Novo paciente')
  const patient = useQuery({
    queryKey: patientsKeys.detail(patientId ?? ''),
    queryFn: ({ signal }) => patientsApi.get(patientId!, signal),
    enabled: Boolean(patientId),
  })
  const nextCode = useQuery({
    queryKey: patientsKeys.nextCode,
    queryFn: ({ signal }) => patientsApi.nextCode(signal),
    enabled: !patientId,
    staleTime: 0,
    gcTime: 0,
  })

  if (patientId) {
    const back = { to: `/pacientes/${patientId}`, label: patient.data?.name ?? 'Paciente' }
    if (patient.isPending) return <Loading title="Editar paciente" back={back} />
    if (patient.isError) return <Failure title="Editar paciente" back={back} message={patient.error.message} />
    return <PatientForm key={patient.data.id} patient={patient.data} />
  }
  if (nextCode.isPending) return <Loading title="Novo paciente" back={{ to: '/pacientes', label: 'Pacientes' }} />
  // Sem a sugestão (erro), o código fica em branco para a pessoa digitar.
  return <PatientForm suggestedCode={nextCode.data?.code ?? ''} />
}

function Loading({ title, back }: { title: string; back: { to: string; label: string } }) {
  return (
    <>
      <PageHeader title={title} back={back} />
      <Spinner size={28} label="Carregando" />
    </>
  )
}

function Failure({ title, back, message }: { title: string; back: { to: string; label: string }; message: string }) {
  return (
    <>
      <PageHeader title={title} back={back} />
      <FormAlert>{sentence(message)}</FormAlert>
    </>
  )
}

function PatientForm({ patient, suggestedCode = '' }: { patient?: PatientDetail; suggestedCode?: string }) {
  const editing = Boolean(patient)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [formError, setFormError] = useState<string | null>(null)
  const [consentFile, setConsentFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)

  const {
    register,
    control,
    handleSubmit,
    setError,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<PatientValues>({
    resolver: zodResolver(schema),
    defaultValues: patient
      ? {
          code: patient.code,
          name: patient.name,
          birth_date: isoToBr(patient.birth_date),
          sex: patient.sex,
          vision_correction: patient.vision_correction,
          consent_signed: patient.consent_signed,
          consent_date: isoToBr(patient.consent_date),
          notes: patient.notes ?? '',
        }
      : { code: suggestedCode, name: '', birth_date: '', sex: '', vision_correction: '', consent_signed: false, consent_date: '', notes: '' },
  })
  const signed = watch('consent_signed')
  const back = patient ? { to: `/pacientes/${patient.id}`, label: patient.name } : { to: '/pacientes', label: 'Pacientes' }

  // Sem assinatura não há data nem PDF; anexar o PDF ou digitar a data marca o termo como assinado.
  function markSigned() {
    if (!signed) setValue('consent_signed', true)
  }

  function onSignedChange(checked: boolean) {
    setValue('consent_signed', checked, { shouldValidate: Boolean(errors.consent_date) })
    if (!checked) {
      setValue('consent_date', '', { shouldValidate: Boolean(errors.consent_date) })
      setConsentFile(null)
      setFileError(null)
    }
  }

  function onFile(file: File) {
    if (!isPdf(file)) {
      setFileError('Anexe o termo em PDF.')
      return
    }
    if (file.size > MAX_PDF_MB * 1024 * 1024) {
      setFileError(`O PDF passa de ${MAX_PDF_MB} MB.`)
      return
    }
    setFileError(null)
    setConsentFile(file)
    markSigned()
  }

  // O que o campo do termo mostra: o arquivo novo, ou o que já está salvo enquanto o termo continuar assinado.
  const attached = consentFile
    ? { name: consentFile.name, size: consentFile.size }
    : signed && patient?.consent_file
      ? patient.consent_file
      : null

  async function onSubmit(values: PatientValues) {
    setFormError(null)
    // Um arquivo recusado nem chegou a ser anexado: o cadastro segue sem ele.
    setFileError(null)
    const input = toInput(values)
    try {
      const saved = patient ? await patientsApi.update(patient.id, input, consentFile) : await patientsApi.create(input, consentFile)
      queryClient.invalidateQueries({ queryKey: patientsKeys.all })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      toast.success(patient ? 'Alterações salvas.' : `Paciente ${saved.code} cadastrado.`)
      navigate(`/pacientes/${saved.id}`)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setError('code', { message: sentence(error.message) })
      } else if (error instanceof ApiError && (error.status === 413 || error.status === 415)) {
        setFileError(sentence(error.message))
      } else {
        setFormError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar.')
      }
    }
  }

  return (
    <>
      <PageHeader
        title={editing ? 'Editar paciente' : 'Novo paciente'}
        subtitle={editing ? 'As alterações ficam registradas na auditoria.' : undefined}
        back={back}
      />
      <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
        <section className={styles.section} aria-labelledby="identificacao">
          <h2 id="identificacao" className={styles.sectionTitle}>
            Identificação
          </h2>
          <div>
            <div className={styles.row}>
              <TextField
                label="Código do participante"
                autoComplete="off"
                className={styles.code}
                error={errors.code?.message}
                aria-describedby="codigo-ajuda"
                {...register('code')}
              />
              <TextField label="Nome completo" autoComplete="off" error={errors.name?.message} {...register('name')} />
            </div>
            <p id="codigo-ajuda" className={styles.rowHint}>
              O código identifica o paciente nas análises e exportações, sem expor o nome.
            </p>
          </div>
          <div className={styles.row}>
            <Controller
              control={control}
              name="birth_date"
              render={({ field }) => (
                <DateField
                  label="Data de nascimento"
                  error={errors.birth_date?.message}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  name={field.name}
                  ref={field.ref}
                />
              )}
            />
            <RadioCardGroup legend="Sexo" error={errors.sex?.message}>
              {SEXES.map((sex) => (
                <RadioCard key={sex} appearance="control" value={sex} label={SEX_LABELS[sex]} {...register('sex')} />
              ))}
            </RadioCardGroup>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="experimento">
          <h2 id="experimento" className={styles.sectionTitle}>
            Informações para o experimento
          </h2>
          <RadioCardGroup legend="Usa óculos de grau ou lentes de contato?" error={errors.vision_correction?.message}>
            {VISIONS.map((vision) => (
              <RadioCard
                key={vision}
                appearance="control"
                value={vision}
                label={VISION_LABELS[vision]}
                {...register('vision_correction')}
              />
            ))}
          </RadioCardGroup>

          <fieldset className={styles.consent}>
            <legend className={styles.legend}>Termo de consentimento (TCLE)</legend>
            <Checkbox
              label="Termo assinado pelo paciente"
              checked={signed}
              onChange={(e) => onSignedChange(e.target.checked)}
              className={styles.signed}
            />
            <div className={styles.consentRow}>
              <Controller
                control={control}
                name="consent_date"
                render={({ field }) => (
                  <DateField
                    label="Data da assinatura"
                    error={errors.consent_date?.message}
                    value={field.value}
                    onChange={(value) => {
                      field.onChange(value)
                      if (value) markSigned()
                    }}
                    onBlur={field.onBlur}
                    name={field.name}
                    ref={field.ref}
                  />
                )}
              />
              <FileField
                accept=".pdf,application/pdf"
                buttonLabel="Anexar PDF"
                fileName={attached?.name}
                fileSize={attached?.size}
                error={fileError}
                onFile={onFile}
                className={styles.file}
              />
            </div>
          </fieldset>

          <Textarea label="Observações" rows={5} error={errors.notes?.message} {...register('notes')} />
        </section>

        {formError && <FormAlert>{formError}</FormAlert>}
        <div className={styles.buttons}>
          <Button variant="secondary" onClick={() => navigate(back.to)}>
            Cancelar
          </Button>
          <Button type="submit" loading={isSubmitting}>
            {editing ? 'Salvar alterações' : 'Cadastrar paciente'}
          </Button>
        </div>
      </form>
    </>
  )
}
