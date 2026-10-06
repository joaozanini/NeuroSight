import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { hasPermission, useCurrentUser } from '../../../api/auth'
import { patientsApi, patientsKeys } from '../../../api/patients'
import type { PatientRow } from '../../../api/patients'
import Button from '../../../components/Button/Button'
import LinkButton from '../../../components/Button/LinkButton'
import Card from '../../../components/Card/Card'
import SearchInput from '../../../components/SearchInput/SearchInput'
import Spinner from '../../../components/Spinner/Spinner'
import TextLink from '../../../components/TextLink/TextLink'
import { cx } from '../../../lib/cx'
import { formatDate, formatNumber, plural, sentence } from '../../../lib/format'
import { useDebouncedValue } from '../../../lib/useDebouncedValue'
import WizardFooter from './WizardFooter'
import type { WizardPatient } from './wizardState'
import shared from './Wizard.module.css'
import styles from './PatientStep.module.css'

// Quantos pacientes a etapa mostra de cada vez (os de movimento mais recente); a busca acha os outros.
const SHOWN = 5

interface PatientStepProps {
  selected: WizardPatient | null
  // Aviso no topo (ex.: de qual sessão a cópia veio).
  notice: string | null
  onSelect: (patient: WizardPatient) => void
  onContinue: () => void
}

function sessionsText(count: number): string {
  return count === 0 ? 'Nenhuma sessão ainda' : plural(count, 'sessão', 'sessões')
}

// Etapa 1 da W13: "Quem vai participar?". Só pacientes ativos recebem sessões novas.
export default function PatientStep({ selected, notice, onSelect, onContinue }: PatientStepProps) {
  const me = useCurrentUser()
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const q = useDebouncedValue(search).trim()
  const filters = { q, page: 1 }
  const patients = useQuery({
    queryKey: patientsKeys.list(filters, SHOWN),
    queryFn: ({ signal }) => patientsApi.list(filters, signal, SHOWN),
    placeholderData: keepPreviousData,
  })

  const rows: WizardPatient[] = patients.data?.items ?? []
  // O escolhido continua à vista mesmo fora dos primeiros (ao voltar da etapa 2).
  const shown = selected && !q && !rows.some((p) => p.id === selected.id) ? [selected, ...rows.slice(0, SHOWN - 1)] : rows
  const hidden = (patients.data?.total ?? 0) - rows.length

  function choose(patient: PatientRow | WizardPatient) {
    setError(null)
    onSelect({ id: patient.id, code: patient.code, name: patient.name, birth_date: patient.birth_date, sessions_count: patient.sessions_count })
  }

  function next() {
    if (!selected) {
      setError('Escolha o paciente para continuar.')
      return
    }
    onContinue()
  }

  let list
  if (patients.isPending) {
    list = <Spinner label="Carregando os pacientes" />
  } else if (patients.isError) {
    list = <p className={styles.empty}>{sentence(patients.error.message)}</p>
  } else if (shown.length === 0) {
    list = <p className={styles.empty}>{q ? 'Nenhum paciente ativo encontrado com essa busca.' : 'Nenhum paciente ativo cadastrado ainda.'}</p>
  } else {
    list = (
      <div role="radiogroup" aria-label="Paciente" className={styles.list}>
        {shown.map((p) => {
          const checked = selected?.id === p.id
          return (
            <label key={p.id} className={cx(styles.option, checked && styles.checked)}>
              <input type="radio" name="paciente" value={p.id} checked={checked} onChange={() => choose(p)} className={styles.radio} />
              <span className={styles.code}>{p.code}</span>
              <span className={styles.name}>{p.name}</span>
              <span className={styles.birth}>
                <span className="sr-only">Nascimento: </span>
                {formatDate(p.birth_date)}
              </span>
              <span className={styles.sessions}>{sessionsText(p.sessions_count)}</span>
            </label>
          )
        })}
      </div>
    )
  }

  return (
    <>
      <Card padding="none" className={shared.card}>
        <h2 className={shared.heading}>Quem vai participar?</h2>
        <p className={shared.lead}>Escolha o paciente. A sessão fica vinculada ao cadastro dele.</p>
        {notice && <p className={shared.notice}>{notice}</p>}
        <SearchInput
          placeholder="Buscar por nome ou código"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          fieldClassName={styles.search}
        />
        {list}
        {hidden > 0 && !patients.isError && (
          <p className={styles.more}>
            {hidden === 1 ? 'Mais 1 paciente.' : `Mais ${formatNumber(hidden)} pacientes.`} Busque pelo nome ou código para
            encontrar outro.
          </p>
        )}
        {error && (
          <p className={shared.error} role="alert">
            {error}
          </p>
        )}
        {hasPermission(me, 'patients.edit') && (
          <p className={styles.newPatient}>
            Paciente novo? <TextLink to="/pacientes/novo">Cadastrar paciente</TextLink>
          </p>
        )}
      </Card>
      <WizardFooter
        start={
          <LinkButton variant="secondary" to="/sessoes">
            Cancelar
          </LinkButton>
        }
        end={<Button onClick={next}>Continuar</Button>}
      />
    </>
  )
}
