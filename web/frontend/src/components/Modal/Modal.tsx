import { useEffect, useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode, RefObject } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cx } from '../../lib/cx'
import styles from './Modal.module.css'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  subtitle?: ReactNode
  // sm: 640 px (W18); md: 720 px (W23); lg: 960 px (W10).
  size?: 'sm' | 'md' | 'lg'
  // Botões do rodapé, à direita.
  footer?: ReactNode
  // Texto do rodapé, à esquerda ("A mudança fica registrada na auditoria.").
  footerNote?: ReactNode
  // false enquanto algo não pode ser interrompido (ex.: envio em andamento).
  dismissible?: boolean
  initialFocus?: RefObject<HTMLElement | null>
  className?: string
  children?: ReactNode
}

export default function Modal({
  open,
  onClose,
  title,
  subtitle,
  size = 'md',
  footer,
  footerNote,
  dismissible = true,
  initialFocus,
  className,
  children,
}: ModalProps) {
  const titleId = useId()
  const subtitleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)

  // Foco entra no modal ao abrir e volta para quem o abriu ao fechar; a página de trás não rola.
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const target = initialFocus?.current ?? dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE) ?? dialogRef.current
    target?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [open, initialFocus])

  if (!open) return null

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape' && dismissible) {
      event.stopPropagation()
      onClose()
      return
    }
    if (event.key !== 'Tab' || !dialogRef.current) return
    const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (items.length === 0) {
      event.preventDefault()
      return
    }
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return createPortal(
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && dismissible) onClose()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        tabIndex={-1}
        className={cx(styles.dialog, styles[size], className)}
        onKeyDown={onKeyDown}
      >
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {subtitle && (
            <p id={subtitleId} className={styles.subtitle}>
              {subtitle}
            </p>
          )}
          {dismissible && (
            <button type="button" className={styles.close} onClick={onClose} aria-label="Fechar">
              <X size={24} aria-hidden />
            </button>
          )}
        </header>
        <div className={styles.body}>{children}</div>
        {(footer || footerNote) && (
          <footer className={styles.footer}>
            <div className={styles.note}>{footerNote}</div>
            {footer && <div className={styles.actions}>{footer}</div>}
          </footer>
        )}
      </div>
    </div>,
    document.body,
  )
}
