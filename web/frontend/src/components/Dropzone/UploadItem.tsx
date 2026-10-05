import { File, FileX } from 'lucide-react'
import { cx } from '../../lib/cx'
import { formatBytes, formatPercent } from '../../lib/format'
import Button from '../Button/Button'
import CheckCircleFilled from '../icons/CheckCircleFilled'
import ProgressBar from '../ProgressBar/ProgressBar'
import styles from './UploadItem.module.css'

export type UploadStatus = 'uploading' | 'done' | 'error'

interface UploadItemProps {
  name: string
  // Tamanho em bytes.
  size?: number
  status: UploadStatus
  // Fração enviada (0 a 1) enquanto status = uploading.
  progress?: number
  error?: string
  thumbnailUrl?: string
  selected?: boolean
  // Com onSelect a linha vira um botão (W10: escolher o arquivo para editar nome e etiquetas).
  onSelect?: () => void
  onRemove?: () => void
}

function statusLine({ status, size, progress = 0, error }: Pick<UploadItemProps, 'status' | 'size' | 'progress' | 'error'>) {
  if (status === 'error') return error ?? 'Não foi possível enviar.'
  if (status === 'done') return size !== undefined ? `Enviado, ${formatBytes(size)}` : 'Enviado'
  const pct = formatPercent(progress)
  return size !== undefined ? `Enviando, ${pct} de ${formatBytes(size)}` : `Enviando, ${pct}`
}

// Linha de um arquivo da lista de envio (W10): miniatura, nome e progresso ou erro.
export default function UploadItem({
  name,
  size,
  status,
  progress = 0,
  error,
  thumbnailUrl,
  selected = false,
  onSelect,
  onRemove,
}: UploadItemProps) {
  const Fallback = status === 'error' ? FileX : File
  const content = (
    <>
      <span className={styles.thumb}>
        {thumbnailUrl && status !== 'error' ? (
          <img src={thumbnailUrl} alt="" />
        ) : (
          <Fallback size={22} className={status === 'error' ? styles.thumbIconError : styles.thumbIcon} aria-hidden />
        )}
      </span>
      <span className={styles.info}>
        <span className={styles.name}>{name}</span>
        {status === 'uploading' && <ProgressBar value={progress} label={`Envio de ${name}`} className={styles.bar} />}
        <span className={cx(styles.status, styles[status])}>
          {status === 'done' && <CheckCircleFilled size={18} className={styles.doneIcon} />}
          {statusLine({ status, size, progress, error })}
        </span>
      </span>
    </>
  )

  return (
    <div className={cx(styles.item, selected && styles.selected, status === 'error' && styles.failed)}>
      {onSelect ? (
        <button type="button" className={styles.main} onClick={onSelect} aria-pressed={selected}>
          {content}
        </button>
      ) : (
        <div className={styles.main}>{content}</div>
      )}
      {onRemove && (
        <Button variant="text-danger" className={styles.remove} onClick={onRemove} aria-label={`Remover ${name}`}>
          Remover
        </Button>
      )}
    </div>
  )
}
