import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { dashboardApi, dashboardKeys } from '../../api/dashboard'
import type { AttentionItem, AuditLine, Dashboard, RecentSession } from '../../api/dashboard'
import { controlSessionPath } from '../../api/sessions'
import StatusBadge from '../../components/Badge/StatusBadge'
import LinkButton from '../../components/Button/LinkButton'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import Spinner from '../../components/Spinner/Spinner'
import StatCard from '../../components/StatCard/StatCard'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextLink from '../../components/TextLink/TextLink'
import { formatDate, formatNumber, formatRelative, formatTime, plural, sentence } from '../../lib/format'
import { usePageTitle } from '../../lib/usePageTitle'
import {
  AWAITING_HIGHLIGHT, attentionSubtitle, attentionWhen, countDelta, formatCollection, percentDelta,
} from './homeText'
import styles from './HomePage.module.css'

// Os números mudam sem o navegador saber (o óculos encerra, os dados chegam).
const REFRESH_MS = 30_000

// W04: o resumo de quem entra. O admin vê o laboratório (usuários, sessões, auditoria); o
// pesquisador, as próprias sessões. As ações do topo seguem as permissões.
export default function HomePage() {
  usePageTitle('Início')
  const me = useCurrentUser()
  const dashboard = useQuery({
    queryKey: dashboardKeys.dashboard,
    queryFn: ({ signal }) => dashboardApi.get(signal),
    staleTime: 0,
    refetchInterval: REFRESH_MS,
  })
  const firstName = me.name.trim().split(/\s+/)[0]

  const actions = (
    <>
      {hasPermission(me, 'patients.edit') && (
        <LinkButton to="/pacientes/novo" variant="secondary">
          Novo paciente
        </LinkButton>
      )}
      {hasPermission(me, 'stimuli.edit') && (
        <LinkButton to="/estimulos?enviar=1" variant="secondary">
          Enviar estímulos
        </LinkButton>
      )}
      {hasPermission(me, 'sessions.run') && (
        <LinkButton to="/sessoes/nova" icon={Plus}>
          Nova sessão
        </LinkButton>
      )}
    </>
  )

  if (!dashboard.data) {
    return (
      <>
        <PageHeader title={`Olá, ${firstName}`} actions={actions} />
        {dashboard.isError ? (
          <FormAlert>{sentence(dashboard.error.message)}</FormAlert>
        ) : (
          <Spinner size={28} label="Carregando o início" />
        )}
      </>
    )
  }

  const d = dashboard.data
  return (
    <>
      <PageHeader title={`Olá, ${firstName}`} subtitle={attentionSubtitle(d.badge, d.view)} actions={actions} />
      <Kpis d={d} />
      <Attention d={d} />
      {d.audit_entries && <AuditSection entries={d.audit_entries} />}
      <RecentSection d={d} />
    </>
  )
}

function Kpis({ d }: { d: Dashboard }) {
  const admin = d.view === 'admin'
  const sessionsDelta = percentDelta(d.sessions)
  const collectionDelta = d.collection_seconds ? percentDelta(d.collection_seconds) : undefined
  const awaiting = d.awaiting
  return (
    <div className={styles.kpis}>
      {admin && d.users && (
        <StatCard
          label="Usuários ativos"
          value={formatNumber(d.users.active)}
          series={d.users.series}
          footer={d.users.invited ? plural(d.users.invited, 'convite pendente', 'convites pendentes') : 'nenhum convite pendente'}
          delta={d.users.added ? { text: `+${formatNumber(d.users.added)}`, direction: 'up' } : undefined}
        />
      )}
      <StatCard
        label={admin ? `Sessões em ${d.month}` : 'Sessões no mês'}
        value={formatNumber(d.sessions.value)}
        series={d.sessions.series}
        footer={sessionsDelta ? `desde ${d.previous_month}` : 'neste mês'}
        delta={sessionsDelta}
      />
      {!admin && d.patients && (
        <StatCard
          label="Pacientes acompanhados"
          value={formatNumber(d.patients.value)}
          series={d.patients.series}
          footer="neste mês"
          delta={countDelta(d.patients.value, d.patients.previous)}
        />
      )}
      <StatCard
        label="Aguardando dados"
        value={formatNumber(awaiting.value)}
        tone="warning"
        series={awaiting.series}
        footer={awaiting.latest_title ?? 'nenhuma no momento'}
        highlight={awaiting.latest_data_status ? AWAITING_HIGHLIGHT[awaiting.latest_data_status] : undefined}
      />
      {admin && d.audit && (
        <StatCard
          label="Registros na auditoria hoje"
          value={formatNumber(d.audit.today)}
          series={d.audit.series}
          footer={d.audit.last_at ? `o último às ${formatTime(d.audit.last_at)}` : 'nenhum hoje'}
          delta={countDelta(d.audit.today, d.audit.yesterday)}
        />
      )}
      {!admin && d.collection_seconds && (
        <StatCard
          label="Tempo de coleta no mês"
          value={formatCollection(d.collection_seconds.value)}
          series={d.collection_seconds.series}
          footer={collectionDelta ? `desde ${d.previous_month}` : 'neste mês'}
          delta={collectionDelta}
        />
      )}
    </div>
  )
}

function Attention({ d }: { d: Dashboard }) {
  return (
    <section className={styles.section} aria-labelledby="atencao">
      <div className={styles.sectionHead}>
        <h2 id="atencao" className={styles.sectionTitle}>
          Precisam de atenção
        </h2>
      </div>
      <div className={styles.card}>
        {d.attention.length === 0 ? (
          <p className={styles.empty}>Nenhuma sessão em andamento ou aguardando dados.</p>
        ) : (
          <ul className={styles.attention}>
            {d.attention.map((item) => (
              <AttentionRow key={item.id} item={item} showOwner={d.view === 'admin'} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function AttentionRow({ item, showOwner }: { item: AttentionItem; showOwner: boolean }) {
  const control = item.status === 'running' && item.can_run
  return (
    <li className={styles.attentionRow}>
      <span className={styles.attentionStatus}>
        <StatusBadge kind="session" status={item.status} />
      </span>
      <span className={styles.attentionSession}>
        <span className={styles.attentionTitle}>{item.title}</span>
        <span className={styles.muted}>
          Paciente {item.patient_code}
          {showOwner && `, responsável: ${item.owner_name}`}
        </span>
      </span>
      <span className={styles.attentionWhen}>{attentionWhen(item)}</span>
      <span className={styles.attentionAction}>
        {control ? (
          <TextLink to={controlSessionPath(item.id)}>Abrir controle</TextLink>
        ) : (
          <TextLink to={`/sessoes/${item.id}`}>
            Ver sessão<span className="sr-only"> {item.title}</span>
          </TextLink>
        )}
      </span>
    </li>
  )
}

const AUDIT_COLUMNS: Column<AuditLine>[] = [
  { key: 'when', header: 'Quando', width: '17%', className: `${styles.muted} ${styles.nowrap}`, render: (e) => formatRelative(e.created_at) },
  { key: 'user', header: 'Usuário', width: '20%', render: (e) => e.user_name ?? 'Sistema' },
  { key: 'action', header: 'Ação', render: (e) => e.text },
]

function AuditSection({ entries }: { entries: AuditLine[] }) {
  return (
    <section className={styles.section} aria-labelledby="auditoria">
      <div className={styles.sectionHead}>
        <h2 id="auditoria" className={styles.sectionTitle}>
          Últimas ações da auditoria
        </h2>
        <TextLink to="/admin/auditoria">Ver auditoria</TextLink>
      </div>
      <Table
        columns={AUDIT_COLUMNS}
        rows={entries}
        rowKey={(e) => e.id}
        caption="Últimas ações da auditoria"
        empty="Nenhum registro ainda."
      />
    </section>
  )
}

function sessionLink(s: RecentSession) {
  return (
    <TextLink to={`/sessoes/${s.id}`} underline={false} className={styles.sessionLink}>
      {s.title}
    </TextLink>
  )
}

const status = (s: RecentSession) => <StatusBadge kind="session" status={s.status} />

// Admin: com o responsável. Pesquisador: com a quantidade de estímulos.
const ADMIN_COLUMNS: Column<RecentSession>[] = [
  { key: 'session', header: 'Sessão', width: '34%', render: sessionLink },
  { key: 'owner', header: 'Responsável', width: '17%', render: (s) => s.owner_name },
  { key: 'patient', header: 'Paciente', width: '12%', render: (s) => s.patient_code },
  { key: 'date', header: 'Data', width: '16%', render: (s) => formatDate(s.date) },
  { key: 'status', header: 'Status', className: styles.nowrap, render: status },
]

const RESEARCHER_COLUMNS: Column<RecentSession>[] = [
  { key: 'session', header: 'Sessão', width: '35%', render: sessionLink },
  { key: 'patient', header: 'Paciente', width: '13%', render: (s) => s.patient_code },
  { key: 'date', header: 'Data', width: '20%', render: (s) => formatDate(s.date) },
  { key: 'stimuli', header: 'Estímulos', width: '10%', align: 'right', render: (s) => formatNumber(s.stimuli_count) },
  { key: 'status', header: 'Status', className: styles.statusAfterNumber, render: status },
]

function RecentSection({ d }: { d: Dashboard }) {
  const admin = d.view === 'admin'
  return (
    <section className={styles.section} aria-labelledby="recentes">
      <div className={styles.sectionHead}>
        <h2 id="recentes" className={styles.sectionTitle}>
          {admin ? 'Sessões recentes' : 'Suas sessões recentes'}
        </h2>
        <TextLink to="/sessoes">Ver todas as sessões</TextLink>
      </div>
      <Table
        columns={admin ? ADMIN_COLUMNS : RESEARCHER_COLUMNS}
        rows={d.recent}
        rowKey={(s) => s.id}
        caption={admin ? 'Sessões recentes' : 'Suas sessões recentes'}
        empty="Nenhuma sessão ainda."
      />
    </section>
  )
}
