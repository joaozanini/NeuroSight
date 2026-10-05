import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { cx } from '../../lib/cx'
import { ToastContext } from './toastContext'
import type { ToastApi, ToastKind, ToastOptions } from './toastContext'
import styles from './Toast.module.css'

interface ToastItem {
  id: number
  kind: ToastKind
  message: ReactNode
  duration: number
}

const DEFAULT_DURATION: Record<ToastKind, number> = { success: 5000, info: 5000, error: 8000 }
const ICONS = { success: CircleCheck, error: CircleAlert, info: Info }

function Toast({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const Icon = ICONS[item.kind]
  useEffect(() => {
    if (!item.duration) return
    const timer = window.setTimeout(() => onDismiss(item.id), item.duration)
    return () => window.clearTimeout(timer)
  }, [item.id, item.duration, onDismiss])

  return (
    <div className={cx(styles.toast, styles[item.kind])} role={item.kind === 'error' ? 'alert' : 'status'}>
      <Icon size={20} className={styles.icon} aria-hidden />
      <div className={styles.message}>{item.message}</div>
      <button type="button" className={styles.close} onClick={() => onDismiss(item.id)} aria-label="Fechar aviso">
        <X size={18} aria-hidden />
      </button>
    </div>
  )
}

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((t) => t.id !== id))
  }, [])

  const api = useMemo<ToastApi>(() => {
    const show = (kind: ToastKind, message: ReactNode, options?: ToastOptions) => {
      const id = nextId.current++
      const duration = options?.duration ?? DEFAULT_DURATION[kind]
      setItems((current) => [...current.slice(-3), { id, kind, message, duration }])
      return id
    }
    return {
      show,
      success: (message, options) => show('success', message, options),
      error: (message, options) => show('error', message, options),
      info: (message, options) => show('info', message, options),
      dismiss,
    }
  }, [dismiss])

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div className={styles.region} aria-label="Avisos">
          {items.map((item) => (
            <Toast key={item.id} item={item} onDismiss={dismiss} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}
