import { useState } from 'react'
import { Film, Image as ImageIcon, Play } from 'lucide-react'
import { cx } from '../../lib/cx'
import { formatMediaDuration } from '../../lib/format'
import styles from './StimulusThumbnail.module.css'

interface StimulusThumbnailProps {
  src?: string | null
  kind: 'image' | 'video'
  // Duração do vídeo em segundos, no selo "▶ 0:45".
  duration?: number | null
  // Esmaecida, para o estímulo arquivado.
  muted?: boolean
  className?: string
}

// Miniatura do estímulo (protótipo "Componente · Miniatura do estímulo"): 16:10, a imagem cobre a
// área e os vídeos levam o selo de duração. Sem imagem (ou se ela falhar), fica o ícone do tipo.
export default function StimulusThumbnail({ src, kind, duration, muted = false, className }: StimulusThumbnailProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const Fallback = kind === 'video' ? Film : ImageIcon
  return (
    <div className={cx(styles.thumb, muted && styles.muted, className)}>
      {src && src !== failedSrc ? (
        <img src={src} alt="" loading="lazy" decoding="async" onError={() => setFailedSrc(src)} />
      ) : (
        <Fallback size={28} strokeWidth={1.5} className={styles.fallback} aria-hidden />
      )}
      {kind === 'video' && duration != null && (
        <span className={styles.duration}>
          <Play size={11} fill="currentColor" strokeWidth={0} aria-hidden />
          <span className="sr-only">Duração </span>
          {formatMediaDuration(duration)}
        </span>
      )}
    </div>
  )
}
