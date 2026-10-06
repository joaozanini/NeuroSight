import { useEffect, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useCurrentUser } from '../../api/auth'
import type { Role } from '../../api/auth'
import { ApiError } from '../../api/client'
import { ROLE_LABELS, USERS_PAGE_SIZE, usersApi, usersKeys } from '../../api/users'
import type { LinkResult, UserFilters, UserSummary } from '../../api/users'
import Badge from '../../components/Badge/Badge'
import StatusBadge from '../../components/Badge/StatusBadge'
import Button from '../../components/Button/Button'
import LinkButton from '../../components/Button/LinkButton'
import Pagination from '../../components/Pagination/Pagination'
import SearchInput from '../../components/SearchInput/SearchInput'
import Select from '../../components/Select/Select'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextLink from '../../components/TextLink/TextLink'
import { useToast } from '../../components/Toast/toastContext'
import { formatRelative, sentence } from '../../lib/format'
import type { UserStatus } from '../../lib/status'
import { useDebouncedValue } from '../../lib/useDebouncedValue'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { usePageTitle } from '../../lib/usePageTitle'
import LinkModal from './LinkModal'
import styles from './UsersPage.module.css'

const ROLE_OPTIONS = [
  { value: '', label: 'Todos os perfis' },
  { value: 'admin', label: 'Admin' },
  { value: 'researcher', label: 'Pesquisador' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'Todos os status' },
  { value: 'active', label: 'Ativo' },
  { value: 'invited', label: 'Convite pendente' },
  { value: 'inactive', label: 'Inativo' },
]

interface PendingLink {
  kind: 'invite' | 'reset'
  userName: string
  result: LinkResult
}

// W19: usuários com busca, filtros de perfil e status e as ações de cada linha. Os filtros ficam
// na URL, para a lista voltar igual depois de editar alguém.
export default function UsersPage() {
  usePageTitle('Usuários')
  const me = useCurrentUser()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [params, updateParams] = useUrlFilters()
  const filters: UserFilters = {
    q: params.get('q') ?? '',
    role: (params.get('perfil') ?? '') as Role | '',
    status: (params.get('status') ?? '') as UserStatus | '',
    page: Math.max(1, Number(params.get('pagina')) || 1),
  }
  const [search, setSearch] = useState(filters.q ?? '')
  const debouncedSearch = useDebouncedValue(search)
  const [pendingLink, setPendingLink] = useState<PendingLink | null>(null)

  useEffect(() => {
    if (debouncedSearch.trim() !== (filters.q ?? '')) updateParams({ q: debouncedSearch.trim(), pagina: null })
    // Só reage ao texto digitado.
  }, [debouncedSearch])

  const users = useQuery({
    queryKey: usersKeys.list(filters),
    queryFn: ({ signal }) => usersApi.list(filters, signal),
    placeholderData: keepPreviousData,
  })

  function afterChange() {
    queryClient.invalidateQueries({ queryKey: usersKeys.all })
    queryClient.invalidateQueries({ queryKey: ['audit'] })
  }

  function showError(error: unknown) {
    toast.error(error instanceof ApiError ? sentence(error.message) : 'Não foi possível concluir a ação.')
  }

  const setStatus = useMutation({
    mutationFn: ({ user, status }: { user: UserSummary; status: 'active' | 'inactive' }) => usersApi.update(user.id, { status }),
    onSuccess: (updated) => {
      afterChange()
      if (updated.status === 'inactive') toast.success(`Acesso de ${updated.name} desativado.`)
      else if (updated.status === 'invited') toast.info(`${updated.name} voltou para o convite pendente. Reenvie o convite para liberar o acesso.`)
      else toast.success(`Acesso de ${updated.name} reativado.`)
    },
    onError: showError,
  })

  const resendInvite = useMutation({
    mutationFn: (user: UserSummary) => usersApi.resendInvite(user.id),
    onSuccess: (result, user) => {
      afterChange()
      if (result.email_sent) toast.success(`Convite reenviado para ${user.email}.`)
      else setPendingLink({ kind: 'invite', userName: user.name, result })
    },
    onError: showError,
  })

  const busyId = setStatus.isPending ? setStatus.variables?.user.id : resendInvite.isPending ? resendInvite.variables?.id : undefined

  const columns: Column<UserSummary>[] = [
    {
      key: 'name',
      header: 'Nome',
      render: (u) => (
        <div>
          <div className={styles.nameRow}>
            <span className={styles.name}>{u.name}</span>
            {u.id === me.id && (
              <Badge tone="info" size="sm">
                Você
              </Badge>
            )}
          </div>
          <div className={styles.email}>{u.email}</div>
        </div>
      ),
    },
    { key: 'role', header: 'Perfil', width: '16%', render: (u) => ROLE_LABELS[u.role] },
    { key: 'status', header: 'Status', width: '19%', render: (u) => <StatusBadge kind="user" status={u.status} /> },
    {
      key: 'last',
      header: 'Último acesso',
      width: '18%',
      render: (u) => <span className={styles.muted}>{u.last_login_at ? formatRelative(u.last_login_at) : 'Nunca acessou'}</span>,
    },
    {
      key: 'actions',
      header: 'Ações',
      align: 'right',
      render: (u) => (
        <div className={styles.actions}>
          <TextLink to={`/admin/usuarios/${u.id}`}>Editar</TextLink>
          {u.id !== me.id && u.status === 'active' && (
            <Button variant="text-danger" disabled={busyId === u.id} onClick={() => setStatus.mutate({ user: u, status: 'inactive' })}>
              Desativar
            </Button>
          )}
          {u.status === 'invited' && (
            <Button variant="text" disabled={busyId === u.id} onClick={() => resendInvite.mutate(u)}>
              Reenviar convite
            </Button>
          )}
          {u.status === 'inactive' && (
            <Button variant="text" disabled={busyId === u.id} onClick={() => setStatus.mutate({ user: u, status: 'active' })}>
              Ativar
            </Button>
          )}
        </div>
      ),
    },
  ]

  const data = users.data
  return (
    <>
      <div className={styles.toolbar}>
        <SearchInput
          placeholder="Buscar por nome ou e-mail"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          fieldClassName={styles.search}
        />
        <Select
          label="Perfil"
          hideLabel
          options={ROLE_OPTIONS}
          value={filters.role}
          onChange={(e) => updateParams({ perfil: e.target.value, pagina: null })}
          fieldClassName={styles.roleFilter}
        />
        <Select
          label="Status"
          hideLabel
          options={STATUS_OPTIONS}
          value={filters.status}
          onChange={(e) => updateParams({ status: e.target.value, pagina: null })}
          fieldClassName={styles.statusFilter}
        />
        <LinkButton to="/admin/usuarios/novo" icon={Plus} className={styles.newButton}>
          Novo usuário
        </LinkButton>
      </div>

      <Table
        caption="Usuários do sistema"
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(u) => u.id}
        loading={users.isPending}
        empty={users.isError ? sentence(users.error.message) : 'Nenhum usuário encontrado com esses filtros.'}
      />
      <Pagination
        page={filters.page ?? 1}
        pageSize={USERS_PAGE_SIZE}
        total={data?.total ?? 0}
        noun="usuários"
        note="Usuários não são excluídos, só desativados, para manter o histórico da auditoria."
        onPageChange={(page) => updateParams({ pagina: page })}
      />

      <LinkModal
        kind={pendingLink?.kind ?? 'invite'}
        userName={pendingLink?.userName ?? ''}
        result={pendingLink?.result ?? null}
        onClose={() => setPendingLink(null)}
      />
    </>
  )
}
