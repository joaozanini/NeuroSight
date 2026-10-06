import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { PATIENTS_PAGE_SIZE, patientsApi, patientsKeys } from '../../api/patients'
import type { PatientFilters, PatientPage, PatientRow } from '../../api/patients'
import Badge from '../../components/Badge/Badge'
import LinkButton from '../../components/Button/LinkButton'
import Checkbox from '../../components/Checkbox/Checkbox'
import PageHeader from '../../components/PageHeader/PageHeader'
import Pagination from '../../components/Pagination/Pagination'
import SearchInput from '../../components/SearchInput/SearchInput'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextLink from '../../components/TextLink/TextLink'
import { formatDate, formatNumber, plural, sentence } from '../../lib/format'
import { useDebouncedValue } from '../../lib/useDebouncedValue'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { usePageTitle } from '../../lib/usePageTitle'
import { newSessionPath } from './patientPaths'
import styles from './PatientsPage.module.css'

function subtitle(page: PatientPage | undefined, showingInactive: boolean): string {
  // Espaço reservado enquanto carrega, para o cabeçalho não pular.
  if (!page) return '\u00a0'
  const { active, inactive } = page.counts
  if (active === 0 && inactive === 0) return 'Nenhum paciente cadastrado ainda.'
  const base = plural(active, 'paciente cadastrado', 'pacientes cadastrados')
  return showingInactive && inactive > 0 ? `${base} e ${formatNumber(inactive)} ${inactive === 1 ? 'inativo' : 'inativos'}.` : `${base}.`
}

// W06: pacientes com busca por nome ou código, "Mostrar inativos" e 8 por página. Os filtros
// ficam na URL, para a lista voltar igual depois de abrir ou editar alguém.
export default function PatientsPage() {
  usePageTitle('Pacientes')
  const me = useCurrentUser()
  const canEdit = hasPermission(me, 'patients.edit')
  const canStartSession = hasPermission(me, 'sessions.run')
  const [params, updateParams] = useUrlFilters()
  const filters: PatientFilters = {
    q: params.get('q') ?? '',
    include_inactive: params.get('inativos') === '1',
    page: Math.max(1, Number(params.get('pagina')) || 1),
  }
  const [search, setSearch] = useState(filters.q ?? '')
  const debouncedSearch = useDebouncedValue(search)

  useEffect(() => {
    if (debouncedSearch.trim() !== (filters.q ?? '')) updateParams({ q: debouncedSearch.trim(), pagina: null })
    // Só reage ao texto digitado.
  }, [debouncedSearch])

  const patients = useQuery({
    queryKey: patientsKeys.list(filters),
    queryFn: ({ signal }) => patientsApi.list(filters, signal),
    placeholderData: keepPreviousData,
  })
  const data = patients.data

  const columns: Column<PatientRow>[] = [
    { key: 'code', header: 'Código', width: '11%', render: (p) => <span className={styles.code}>{p.code}</span> },
    {
      key: 'name',
      header: 'Nome',
      width: '21%',
      render: (p) => (
        <span className={styles.nameRow}>
          <TextLink to={`/pacientes/${p.id}`} underline={false} className={styles.name}>
            {p.name}
          </TextLink>
          {p.status === 'inactive' && (
            <Badge tone="neutral" size="sm">
              Inativo
            </Badge>
          )}
        </span>
      ),
    },
    { key: 'birth', header: 'Data de nascimento', width: '19%', render: (p) => formatDate(p.birth_date) },
    { key: 'sessions', header: 'Sessões', width: '9%', align: 'right', render: (p) => formatNumber(p.sessions_count) },
    {
      key: 'last',
      header: 'Última sessão',
      width: '18%',
      render: (p) => (p.last_session_at ? formatDate(p.last_session_at) : <span className={styles.muted}>—</span>),
    },
    {
      key: 'actions',
      header: 'Ações',
      align: 'right',
      render: (p) => (
        <span className={styles.actions}>
          {canEdit && <TextLink to={`/pacientes/${p.id}/editar`}>Editar</TextLink>}
          {canStartSession && p.status === 'active' && <TextLink to={newSessionPath(p.id)}>Nova sessão</TextLink>}
        </span>
      ),
    },
  ]

  const searching = Boolean(filters.q)
  let empty = 'Nenhum paciente cadastrado ainda.'
  if (patients.isError) empty = sentence(patients.error.message)
  else if (searching) empty = 'Nenhum paciente encontrado com essa busca.'
  else if (data && data.counts.active === 0 && data.counts.inactive > 0 && !filters.include_inactive)
    empty = 'Nenhum paciente ativo. Marque “Mostrar inativos” para ver os inativos.'

  return (
    <>
      <PageHeader
        title="Pacientes"
        subtitle={subtitle(data, Boolean(filters.include_inactive))}
        actions={
          canEdit && (
            <LinkButton to="/pacientes/novo" icon={Plus}>
              Novo paciente
            </LinkButton>
          )
        }
      />
      <div className={styles.toolbar}>
        <SearchInput
          placeholder="Buscar por nome ou código"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          fieldClassName={styles.search}
        />
        <Checkbox
          label="Mostrar inativos"
          checked={Boolean(filters.include_inactive)}
          onChange={(e) => updateParams({ inativos: e.target.checked ? '1' : null, pagina: null })}
          className={styles.inactive}
        />
      </div>
      <Table
        caption="Pacientes cadastrados"
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(p) => p.id}
        loading={patients.isPending}
        empty={empty}
      />
      <Pagination
        page={filters.page ?? 1}
        pageSize={PATIENTS_PAGE_SIZE}
        total={data?.total ?? 0}
        onPageChange={(page) => updateParams({ pagina: page })}
      />
    </>
  )
}
