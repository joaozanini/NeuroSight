import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastOptions {
  // Em milissegundos; 0 mantém o aviso até a pessoa fechar.
  duration?: number
}

export interface ToastApi {
  show: (kind: ToastKind, message: ReactNode, options?: ToastOptions) => number
  success: (message: ReactNode, options?: ToastOptions) => number
  error: (message: ReactNode, options?: ToastOptions) => number
  info: (message: ReactNode, options?: ToastOptions) => number
  dismiss: (id: number) => void
}

export const ToastContext = createContext<ToastApi | null>(null)

// Avisos rápidos ("Paciente cadastrado.", "Não foi possível salvar."). Precisa do ToastProvider.
export function useToast(): ToastApi {
  const api = useContext(ToastContext)
  if (!api) throw new Error('useToast precisa estar dentro de <ToastProvider>')
  return api
}
