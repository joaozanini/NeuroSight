import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { AUDIT_PAGE_SIZE, auditApi, auditKeys } from '../../api/audit'
import type { AuditFilterOptions, AuditItem, AuditQuery } from '../../api/audit'
import { ButtonContent } from '../../components/Button/Button'
import { buttonClassName } from '../../components/Button/buttonLook'
import Pagination from '../../components/Pagination/Pagination'
import Select from '../../components/Select/Select'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextLink from '../../components/TextLink/TextLink'
import { formatDate, formatTime, sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import AuditDetailModal from './AuditDetailModal'
import { labelOf } from './auditLabels'
import styles from './AuditPage.module.css'

const PERIODS = [
  { value: 'hoje', label: 'Hoje', days: 1 },
  { value: '7d', label: 'Últimos 7 dias', days: 7 },
  { value: '30d', label: 'Últimos 30 dias', days: 30 },
  { value: '90d', label: 'Últimos 90 dias', days: 90 },
  { value: 'tudo', label: 'Todo o período', days: 0 },
]
const DEFAULT_PERIOD = '7d'

// Início do período no fuso de quem olha: "Últimos 7 dias" = hoje e os 6 dias anteriores.
export function periodStart(period: string, now = new Date()): string | undefined {
  const days = PERIODS.find((p) => p.value === period)?.days ?? 7
  if (!days) return undefined
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - (days - 1)).toISOString()
}

// W22: registros de auditoria com filtros, CSV e o detalhe (W23). Só leitura.
export default function AuditPage() {
  usePageTitle('Auditoria')
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const period = params.get('periodo') ?? DEFAULT_PERIOD
  const page = Math.max(1, Number(params.get('pagina')) || 1)
  const query: AuditQuery = {
    since: periodStart(period),
    user_id: params.get('usuario') ?? undefined,
    action: params.get('acao') ?? undefined,
    entity_type: params.get('item') ?? undefined,
  }
  const [openId, setOpenId] = useState<number | null>(null)

  const options = useQuery({ queryKey: auditKeys.filters, queryFn: ({ signal }) => auditApi.filters(signal), staleTime: 5 * 60_000 })
  const entries = useQuery({
    queryKey: auditKeys.list(query, page),
    queryFn: ({ signal }) => auditApi.list(query, page, signal),
    placeholderData: keepPreviousData,
  })

  function setFilter(key: string, value: string) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value && !(key === 'periodo' && value === DEFAULT_PERIOD)) next.set(key, value)
        else next.delete(key)
        next.delete('pagina')
        return next
      },
      { replace: true },
    )
  }

  function setPage(value: number) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value > 1) next.set('pagina', String(value))
        else next.delete('pagina')
        return next
      },
      { replace: true },
    )
  }

  const opts: AuditFilterOptions | undefined = options.data
  const columns: Column<AuditItem>[] = [
    {
      key: 'when',
      header: 'Data e hora',
      width: '13%',
      render: (e) => (
        <>
          <div>{formatDate(e.created_at)}</div>
          <div className={styles.secondary}>{formatTime(e.created_at)}</div>
        </>
      ),
    },
    { key: 'user', header: 'Usuário', width: '13%', render: (e) => e.user_name ?? 'Sistema' },
    { key: 'action', header: 'Ação', width: '17%', render: (e) => labelOf(opts?.actions, e.action) },
    {
      key: 'item',
      header: 'Item afetado',
      render: (e) => (
        <>
          <div className={styles.itemType}>{labelOf(opts?.entity_types, e.entity_type)}</div>
          <div>{e.entity_label}</div>
        </>
      ),
    },
    { key: 'ip', header: 'IP', width: '10%', render: (e) => <span className={styles.secondary}>{e.ip ?? '—'}</span> },
    {
      key: 'details',
      header: <span className="sr-only">Detalhes</span>,
      align: 'right',
      width: '9%',
      render: (e) => (
        <TextLink onClick={() => setOpenId(e.id)} aria-label={`Detalhes do registro de ${formatDate(e.created_at)} às ${formatTime(e.created_at)}`}>
          Detalhes
        </TextLink>
      ),
    },
  ]

  return (
    <>
      <div className={styles.toolbar}>
        <Select
          label="Período"
          hideLabel
          options={PERIODS.map(({ value, label }) => ({ value, label }))}
          value={period}
          onChange={(e) => setFilter('periodo', e.target.value)}
          fieldClassName={styles.period}
        />
        <Select
          label="Usuário"
          hideLabel
          options={[{ value: '', label: 'Todos os usuários' }, ...(opts?.users ?? [])]}
          value={query.user_id ?? ''}
          onChange={(e) => setFilter('usuario', e.target.value)}
          fieldClassName={styles.user}
        />
        <Select
          label="Ação"
          hideLabel
          options={[{ value: '', label: 'Todas as ações' }, ...(opts?.actions ?? [])]}
          value={query.action ?? ''}
          onChange={(e) => setFilter('acao', e.target.value)}
          fieldClassName={styles.action}
        />
        <Select
          label="Tipo de item"
          hideLabel
          options={[{ value: '', label: 'Todos os itens' }, ...(opts?.entity_types ?? [])]}
          value={query.entity_type ?? ''}
          onChange={(e) => setFilter('item', e.target.value)}
          fieldClassName={styles.item}
        />
        <a
          href={auditApi.exportUrl(query)}
          download
          className={`${buttonClassName({ variant: 'secondary' }, true)} ${styles.export}`}
          onClick={() => window.setTimeout(() => queryClient.invalidateQueries({ queryKey: auditKeys.all }), 1500)}
        >
          <ButtonContent icon={Download}>Exportar CSV</ButtonContent>
        </a>
      </div>

      <Table
        caption="Registros de auditoria"
        columns={columns}
        rows={entries.data?.items ?? []}
        rowKey={(e) => e.id}
        loading={entries.isPending}
        empty={entries.isError ? sentence(entries.error.message) : 'Nenhum registro no período e com esses filtros.'}
      />
      <Pagination
        page={page}
        pageSize={AUDIT_PAGE_SIZE}
        total={entries.data?.total ?? 0}
        noun="registros"
        note="Os registros são só leitura: ninguém pode editar ou apagar."
        onPageChange={setPage}
      />

      <AuditDetailModal entryId={openId} options={opts} onClose={() => setOpenId(null)} />
    </>
  )
}
