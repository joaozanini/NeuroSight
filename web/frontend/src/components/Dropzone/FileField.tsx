import { useId, useRef } from 'react'
import type { ReactNode } from 'react'
import { FileText, Upload } from 'lucide-react'
import { cx } from '../../lib/cx'
import { formatBytes } from '../../lib/format'
import Button from '../Button/Button'
import { describedBy } from '../Field/describedBy'
import { useFileDrop } from './useFileDrop'
import styles from './Dropzone.module.css'

interface FileFieldProps {
  id?: string
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
  accept?: string
  // Arquivo já anexado (nome e tamanho), se houver.
  fileName?: string
  fileSize?: number
  emptyText?: string
  buttonLabel?: string
  replaceLabel?: string
  onFile: (file: File) => void
  disabled?: boolean
  className?: string
}

// Anexo de um arquivo só, em linha com os campos (W07 "Anexar PDF" / "Trocar arquivo").
export default function FileField({
  id,
  label,
  hint,
  error,
  accept,
  fileName,
  fileSize,
  emptyText = 'Nenhum arquivo anexado',
  buttonLabel = 'Anexar arquivo',
  replaceLabel = 'Trocar arquivo',
  onFile,
  disabled = false,
  className,
}: FileFieldProps) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const inputRef = useRef<HTMLInputElement>(null)
  const { dragging, dropProps } = useFileDrop((files) => onFile(files[0]), disabled)
  const attached = Boolean(fileName)

  return (
    <div className={cx(styles.fileFieldWrap, className)}>
      {label && (
        <p id={`${fieldId}-label`} className={styles.fileLabel}>
          {label}
        </p>
      )}
      <div
        className={cx(styles.fileField, attached && styles.attached, dragging && styles.dragging, error ? styles.invalid : undefined)}
        {...dropProps}
      >
        <FileText size={20} className={styles.fileIcon} aria-hidden />
        <span className={cx(styles.fileName, !attached && styles.empty)}>
          {attached ? `${fileName}${fileSize !== undefined ? ` (${formatBytes(fileSize)})` : ''}` : emptyText}
        </span>
        <Button
          variant="secondary"
          size="sm"
          icon={attached ? undefined : Upload}
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          aria-describedby={describedBy(fieldId, { hint, error })}
          aria-labelledby={label ? `${fieldId}-label ${fieldId}-button` : undefined}
          id={`${fieldId}-button`}
        >
          {attached ? replaceLabel : buttonLabel}
        </Button>
        <input
          ref={inputRef}
          id={fieldId}
          type="file"
          accept={accept}
          hidden
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) onFile(file)
          }}
        />
      </div>
      {error ? (
        <p id={`${fieldId}-error`} className={styles.fileError}>
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${fieldId}-hint`} className={styles.fileHint}>
            {hint}
          </p>
        )
      )}
    </div>
  )
}
