import { useQuery } from '@tanstack/react-query'
import { CircleAlert, FileCode, Hourglass, Video } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { liveApi, liveKeys } from '../../api/live'
import { downloadUrl } from '../../api/sessions'
import type { DownloadKind, ExposureRow, SessionDetail } from '../../api/sessions'
import AnchorButton from '../../components/Button/AnchorButton'
import Badge from '../../components/Badge/Badge'
import Card from '../../components/Card/Card'
import Spinner from '../../components/Spinner/Spinner'
import StimulusThumbnail from '../../components/StimulusThumbnail/StimulusThumbnail'
import Table from '../../components/Table/Table'
import type { Column } from '../../components/Table/Table'
import TextLink from '../../components/TextLink/TextLink'
import { formatBytes, formatClock, formatDuration, formatSeconds, sentence } from '../../lib/format'
import styles from './SessionData.module.css'

// A parte da W16 que vem dos dados coletados: estímulos exibidos, marcações e arquivos. Antes de os
// dados chegarem (ou se o processamento falhar), um aviso no lugar.

// Estímulos distintos que apareceram ("12 exibidos" no resumo).
export function exhibitedCount(exposures: ExposureRow[]): number {
  return new Set(exposures.map((e) => e.position)).size
}

// "5,0 s"; a partir de um minuto, "1 min 20 s".
function screenTime(seconds: number): string {
  return seconds < 60 ? formatSeconds(seconds) : formatDuration(seconds)
}

const EXPOSURE_COLUMNS: Column<ExposureRow>[] = [
  { key: 'position', header: 'Nº', width: '72px', align: 'center', render: (e) => e.position },
  {
    key: 'stimulus',
    header: 'Estímulo',
    render: (e) => (
      <span className={styles.stimulus}>
        <StimulusThumbnail src={e.thumbnail_url} kind={e.kind} muted={e.archived} className={styles.thumb} />
        <TextLink to={`/estimulos/${e.stimulus_id}`} underline={false} className={styles.stimulusName}>
          {e.name}
        </TextLink>
        {e.archived && (
          <Badge tone="neutral" size="sm">
            Arquivado
          </Badge>
        )}
      </span>
    ),
  },
  { key: 'start', header: 'Início', width: '96px', align: 'right', render: (e) => formatClock(e.on_t) },
  { key: 'time', header: 'Tempo de tela', width: '180px', align: 'right', render: (e) => screenTime(e.screen_seconds) },
]

export function ExposuresCard({ session }: { session: SessionDetail }) {
  return (
    <Card padding="none" className={styles.exposures} aria-labelledby="estimulos-exibidos">
      <header className={styles.exposuresHeader}>
        <h2 id="estimulos-exibidos" className={styles.heading}>
          Estímulos exibidos
        </h2>
        <span className={styles.order}>Na ordem em que apareceram</span>
      </header>
      <Table
        bare
        caption="Estímulos exibidos, na ordem em que apareceram"
        columns={EXPOSURE_COLUMNS}
        rows={session.exposures}
        rowKey={(e) => e.seq}
        empty="Nenhum estímulo chegou a ser exibido."
        className={styles.exposuresTable}
      />
    </Card>
  )
}

export function MarkersCard({ sessionId }: { sessionId: string }) {
  const markers = useQuery({
    queryKey: liveKeys.markers(sessionId),
    queryFn: ({ signal }) => liveApi.markers(sessionId, signal),
  })
  let body
  if (markers.isPending) body = <Spinner label="Carregando as marcações" />
  else if (markers.isError) body = <p className={styles.muted}>{sentence(markers.error.message)}</p>
  else if (markers.data.length === 0) body = <p className={styles.muted}>Nenhuma marcação nesta sessão.</p>
  else {
    body = (
      <ul className={styles.markers}>
        {markers.data.map((m) => (
          <li key={m.id}>
            <span className={styles.markerTime}>{formatClock(m.t)}</span>
            <span className={styles.markerText}>{m.text}</span>
          </li>
        ))}
      </ul>
    )
  }
  return (
    <Card title="Marcações" aria-label="Marcações" className={styles.side}>
      {body}
    </Card>
  )
}

interface FileRowProps {
  icon: LucideIcon
  title: string
  detail: string
  download?: { href: string; label: string }
}

function FileRow({ icon: Icon, title, detail, download }: FileRowProps) {
  return (
    <li className={styles.file}>
      <Icon size={22} strokeWidth={1.6} className={styles.fileIcon} aria-hidden />
      <div className={styles.fileText}>
        <span className={styles.fileTitle}>{title}</span>
        <span className={styles.fileDetail}>{detail}</span>
      </div>
      {download && (
        <AnchorButton variant="secondary" size="sm" href={download.href} download aria-label={download.label}>
          Baixar
        </AnchorButton>
      )}
    </li>
  )
}

export function FilesCard({ session }: { session: SessionDetail }) {
  const files = session.files
  if (!files) return null
  const link = (kind: DownloadKind, label: string) =>
    session.can_export ? { href: downloadUrl(session.id, kind), label } : undefined
  const recording = files.recording
  let recordingDetail = 'Sessão sem gravação'
  if (recording.status === 'ready') recordingDetail = `MP4, ${formatBytes(recording.size_bytes ?? 0)}`
  else if (recording.status === 'failed') recordingDetail = 'Não foi possível montar o vídeo'
  return (
    <Card title="Arquivos" aria-label="Arquivos" className={styles.side}>
      <ul className={styles.files}>
        <FileRow
          icon={FileCode}
          title="Dados de rastreamento"
          detail={`JSON, ${formatBytes(files.tracking_bytes)}`}
          download={link('tracking', 'Baixar os dados de rastreamento (JSON)')}
        />
        <FileRow
          icon={Video}
          title="Gravação da sessão"
          detail={recordingDetail}
          download={recording.status === 'ready' ? link('recording', 'Baixar a gravação da sessão (MP4)') : undefined}
        />
      </ul>
    </Card>
  )
}

// Aviso sobre os dados de uma sessão já executada que ainda não estão prontos.
export function DataNotice({ session }: { session: SessionDetail }) {
  let text: string
  let Icon: LucideIcon = Hourglass
  // Recém-encerrada, antes de o servidor responder de novo, o detalhe ainda não diz nada dos dados.
  if (session.data_status === 'waiting' || (session.data_status === 'none' && session.status === 'awaiting_data')) {
    text = 'O óculos ainda está enviando os dados desta sessão. Os estímulos exibidos, as marcações e os arquivos aparecem aqui quando o envio terminar.'
  } else if (session.data_status === 'processing') {
    text = 'Os dados chegaram e estão sendo processados. Esta página se atualiza sozinha.'
  } else if (session.data_status === 'failed') {
    Icon = CircleAlert
    text = `Não foi possível processar os dados desta sessão: ${sentence(session.data_error ?? 'erro desconhecido')} O servidor tenta de novo quando reiniciar.`
  } else {
    text = 'Esta sessão não tem dados coletados.'
  }
  return (
    <p className={styles.notice} data-tone={session.data_status === 'failed' ? 'danger' : 'info'} role="status">
      <Icon size={20} className={styles.noticeIcon} aria-hidden />
      <span>{text}</span>
    </p>
  )
}
