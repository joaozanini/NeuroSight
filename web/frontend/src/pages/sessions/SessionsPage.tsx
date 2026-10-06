import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { SESSIONS_PAGE_SIZE, controlSessionPath, prepareSessionPath, sessionsApi, sessionsKeys } from '../../api/sessions'
import type { SessionFilters, SessionRow } from '../../api/sessions'
import StatusBadge from '../../components/Badge/StatusBadge'
import LinkButton from '../../components/Button/LinkButton'
import PageHeader from '../../components/PageHeader/PageHeader'
import Pagination from '../../components/Pagination/Pagination'
import SearchInput from '../../components/SearchInput/SearchInput'
import Select from '../../components/Select/Select'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextLink from '../../components/TextLink/TextLink'
import { formatDate, sentence } from '../../lib/format'
import { PERIOD_OPTIONS, periodStart } from '../../lib/periods'
import { SESSION_STATUS } from '../../lib/status'
import type { SessionStatus } from '../../lib/status'
import { useDebouncedValue } from '../../lib/useDebouncedValue'
import { usePageTitle } from '../../lib/usePageTitle'
import { useUrlFilters } from '../../lib/useUrlFilters'
import VisibilityLabel from './VisibilityLabel'
import styles from './SessionsPage.module.css'

const DEFAULT_PERIOD = '30d'
const STATUS_OPTIONS = [
  { value: '', label: 'Todos os status' },
  ...(Object.keys(SESSION_STATUS) as SessionStatus[]).map((s) => ({ value: s, label: SESSION_STATUS[s].label })),
]

// W12: as sessões da pessoa e as liberadas para ela, com busca e filtros de status, responsável e
// período (na URL, para a lista voltar igual). A ação de cada linha segue o status.
export default function SessionsPage() {
  usePageTitle('Sessões')
  const me = useCurrentUser()
  const canRun = hasPermission(me, 'sessions.run')
  const [params, updateParams] = useUrlFilters()
  const period = params.get('periodo') ?? DEFAULT_PERIOD
  const status = (params.get('status') ?? '') as SessionStatus | ''
  const filters: SessionFilters = {
    q: params.get('q') ?? '',
    status: status in SESSION_STATUS ? status : '',
    owner_id: params.get('responsavel') ?? '',
    since: periodStart(period),
    page: Math.max(1, Number(params.get('pagina')) || 1),
  }
  const [search, setSearch] = useState(filters.q ?? '')
  const debouncedSearch = useDebouncedValue(search)

  useEffect(() => {
    if (debouncedSearch.trim() !== (filters.q ?? '')) updateParams({ q: debouncedSearch.trim(), pagina: null })
    // Só reage ao texto digitado.
  }, [debouncedSearch])

  const sessions = useQuery({
    queryKey: sessionsKeys.list(filters),
    queryFn: ({ signal }) => sessionsApi.list(filters, signal),
    placeholderData: keepPreviousData,
  })
  const owners = useQuery({ queryKey: sessionsKeys.owners, queryFn: ({ signal }) => sessionsApi.owners(signal) })

  function action(s: SessionRow) {
    const mine = canRun && s.owner_id === me.id
    if (mine && s.status === 'running') return <TextLink to={controlSessionPath(s.id)}>Abrir controle</TextLink>
    if (mine && s.status === 'configured') return <TextLink to={prepareSessionPath(s.id)}>Preparar</TextLink>
    return <TextLink to={`/sessoes/${s.id}`}>Abrir</TextLink>
  }

  const columns: Column<SessionRow>[] = [
    {
      key: 'session',
      header: 'Sessão',
      width: '26%',
      render: (s) => (
        <span className={styles.session}>
          <TextLink to={`/sessoes/${s.id}`} underline={false} className={styles.title}>
            {s.title}
          </TextLink>
          <span className={styles.patient}>Paciente {s.patient_code}</span>
        </span>
      ),
    },
    { key: 'owner', header: 'Responsável', width: '13%', render: (s) => s.owner_name },
    { key: 'date', header: 'Data', width: '12%', render: (s) => formatDate(s.date) },
    { key: 'status', header: 'Status', width: '18%', className: styles.nowrap, render: (s) => <StatusBadge kind="session" status={s.status} /> },
    {
      key: 'visibility',
      header: 'Visibilidade',
      width: '16%',
      render: (s) => <VisibilityLabel visibility={s.visibility} className={styles.visibility} />,
    },
    { key: 'actions', header: 'Ações', align: 'right', className: styles.nowrap, render: action },
  ]

  const ownerOptions = [
    { value: '', label: 'Todos os responsáveis' },
    ...(owners.data ?? []).map((o) => ({ value: o.id, label: o.name })),
  ]
  // Responsável da URL que ainda não chegou na lista (ou não tem mais sessões visíveis).
  if (filters.owner_id && !ownerOptions.some((o) => o.value === filters.owner_id)) {
    ownerOptions.push({ value: filters.owner_id, label: 'Responsável escolhido' })
  }

  const filtered = Boolean(filters.q || filters.status || filters.owner_id) || period !== 'tudo'
  let empty = 'Nenhuma sessão ainda.'
  if (sessions.isError) empty = sentence(sessions.error.message)
  else if (filtered) empty = 'Nenhuma sessão encontrada com esses filtros.'

  return (
    <>
      <PageHeader
        title="Sessões"
        subtitle="Suas sessões e as que outros pesquisadores liberaram para você."
        actions={
          canRun && (
            <LinkButton to="/sessoes/nova" icon={Plus}>
              Nova sessão
            </LinkButton>
          )
        }
      />
      <div className={styles.toolbar}>
        <SearchInput
          placeholder="Buscar por título ou paciente"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          fieldClassName={styles.search}
        />
        <Select
          label="Status"
          hideLabel
          options={STATUS_OPTIONS}
          value={filters.status}
          onChange={(e) => updateParams({ status: e.target.value, pagina: null })}
          fieldClassName={styles.status}
        />
        <Select
          label="Responsável"
          hideLabel
          options={ownerOptions}
          value={filters.owner_id}
          onChange={(e) => updateParams({ responsavel: e.target.value, pagina: null })}
          fieldClassName={styles.owner}
        />
        <Select
          label="Período"
          hideLabel
          options={PERIOD_OPTIONS}
          value={period}
          onChange={(e) => updateParams({ periodo: e.target.value === DEFAULT_PERIOD ? null : e.target.value, pagina: null })}
          fieldClassName={styles.period}
        />
      </div>
      <Table
        caption="Sessões"
        columns={columns}
        rows={sessions.data?.items ?? []}
        rowKey={(s) => s.id}
        loading={sessions.isPending}
        empty={empty}
      />
      <Pagination
        page={filters.page ?? 1}
        pageSize={SESSIONS_PAGE_SIZE}
        total={sessions.data?.total ?? 0}
        onPageChange={(page) => updateParams({ pagina: page })}
      />
    </>
  )
}
