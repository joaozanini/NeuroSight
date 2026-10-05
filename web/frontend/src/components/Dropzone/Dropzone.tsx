import { useRef } from 'react'
import { Upload } from 'lucide-react'
import { cx } from '../../lib/cx'
import Button from '../Button/Button'
import { useFileDrop } from './useFileDrop'
import styles from './Dropzone.module.css'

interface DropzoneProps {
  // Recebe TODOS os arquivos soltos ou escolhidos; a tela decide o que aceitar (ver matchesAccept),
  // para poder listar os recusados com "Formato não aceito".
  onFiles: (files: File[]) => void
  accept?: string
  multiple?: boolean
  title?: string
  description?: string
  buttonLabel?: string
  disabled?: boolean
  className?: string
}

// Área de arrastar e soltar com o botão "Escolher arquivos" (W10).
export default function Dropzone({
  onFiles,
  accept,
  multiple = true,
  title = 'Arraste os arquivos para cá',
  description,
  buttonLabel = 'Escolher arquivos',
  disabled = false,
  className,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const { dragging, dropProps } = useFileDrop(onFiles, disabled)

  return (
    <div className={cx(styles.zone, dragging && styles.dragging, disabled && styles.disabled, className)} {...dropProps}>
      <Upload size={30} strokeWidth={1.75} className={styles.icon} aria-hidden />
      <div className={styles.text}>
        <p className={styles.title}>{title}</p>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      <Button variant="secondary" onClick={() => inputRef.current?.click()} disabled={disabled}>
        {buttonLabel}
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          event.target.value = '' // permite escolher o mesmo arquivo de novo
          if (files.length) onFiles(files)
        }}
      />
    </div>
  )
}
